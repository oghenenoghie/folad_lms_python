"""Secure, synchronous persistence boundary for CBT source uploads.

This module validates actual bytes before private storage and creates only
an \`uploaded\` ledger row. It deliberately does not enqueue Celery work:
production import-worker readiness is a separate deployment gate.
"""
import csv
import hashlib
import io
import re
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import PurePosixPath

from django.db import IntegrityError, transaction

from apps.cbt.models import CBTImportJob


MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5000
MAX_XLSX_MEMBERS = 1000
MAX_XLSX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_XLSX_MEMBER_BYTES = 20 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
_REQUIRED_HEADERS = {"text", "correct"}
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class InvalidSourceUpload(ValueError):
    """The supplied source is unsupported, malformed, or unsafe."""


class ImportIdempotencyConflict(ValueError):
    """An idempotency key was reused for a different upload or target."""


@dataclass(frozen=True)
class ValidatedSource:
    content: bytes
    filename: str
    source_format: str
    sha256: str


def _safe_filename(filename: str, extension: str) -> str:
    # Treat both slash styles as path separators; never persist a client path.
    basename = (filename or "questions").replace("\\", "/").split("/")[-1]
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    stem = _SAFE_FILENAME.sub("-", stem).strip(".-_")[:220] or "questions"
    return f"{stem}.{extension}"


def _validate_headers(headers) -> list[str]:
    normalized = [str(value).strip().lower() if value is not None else "" for value in headers]
    if not normalized or any(not value for value in normalized):
        raise InvalidSourceUpload("the first row must contain non-empty column headers")
    if len(set(normalized)) != len(normalized):
        raise InvalidSourceUpload("column headers must be unique")
    missing = _REQUIRED_HEADERS - set(normalized)
    if missing:
        raise InvalidSourceUpload(f"missing required column(s): {', '.join(sorted(missing))}")
    return normalized


def _validate_csv(content: bytes) -> None:
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidSourceUpload("CSV must use UTF-8 encoding") from exc
    if "\x00" in decoded:
        raise InvalidSourceUpload("CSV contains binary or NUL characters")
    try:
        reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
        headers = _validate_headers(next(reader, []))
        for row_number, row in enumerate(reader, start=2):
            if row_number > MAX_ROWS + 1:
                raise InvalidSourceUpload(f"CSV exceeds the {MAX_ROWS:,}-row import limit")
            if len(row) > len(headers):
                raise InvalidSourceUpload(f"row {row_number} contains more columns than the header")
    except csv.Error as exc:
        raise InvalidSourceUpload("CSV contains malformed data") from exc


def _validate_xlsx(content: bytes) -> None:
    if not content.startswith(b"PK\x03\x04"):
        raise InvalidSourceUpload("file content does not match an XLSX workbook")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if not members or len(members) > MAX_XLSX_MEMBERS:
                raise InvalidSourceUpload("XLSX archive has an unsafe number of entries")
            total_uncompressed = 0
            names = set()
            for member in members:
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in member.filename:
                    raise InvalidSourceUpload("XLSX archive contains an unsafe path")
                if member.filename in names:
                    raise InvalidSourceUpload("XLSX archive contains duplicate entries")
                names.add(member.filename)
                if member.flag_bits & 0x1:
                    raise InvalidSourceUpload("encrypted XLSX archives are not supported")
                if member.file_size > MAX_XLSX_MEMBER_BYTES:
                    raise InvalidSourceUpload("an XLSX archive entry exceeds the safety limit")
                total_uncompressed += member.file_size
                if member.file_size and member.compress_size == 0:
                    raise InvalidSourceUpload("XLSX archive has an invalid compression ratio")
                if member.compress_size and member.file_size / member.compress_size > MAX_COMPRESSION_RATIO:
                    raise InvalidSourceUpload("XLSX archive compression ratio exceeds the safety limit")
            if total_uncompressed > MAX_XLSX_UNCOMPRESSED_BYTES:
                raise InvalidSourceUpload("XLSX archive expands beyond the 50 MB safety limit")
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise InvalidSourceUpload("file is not a valid XLSX workbook")
            if "xl/vbaProject.bin" in names:
                raise InvalidSourceUpload("macro-enabled workbooks are not supported")
            bad_member = archive.testzip()
            if bad_member:
                raise InvalidSourceUpload("XLSX archive failed its integrity check")
    except InvalidSourceUpload:
        raise
    except (zipfile.BadZipFile, OSError, RuntimeError, EOFError, zlib.error) as exc:
        raise InvalidSourceUpload("could not read XLSX workbook; verify that it is a valid .xlsx file") from exc

    try:
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        try:
            sheet = workbook.active
            rows = sheet.iter_rows(values_only=True)
            headers = _validate_headers(next(rows, ()))
            for row_number, row in enumerate(rows, start=2):
                if row_number > MAX_ROWS + 1:
                    raise InvalidSourceUpload(f"worksheet exceeds the {MAX_ROWS:,}-row import limit")
                if len(row) > len(headers) and any(value is not None for value in row[len(headers):]):
                    raise InvalidSourceUpload(f"row {row_number} contains data beyond the header columns")
        finally:
            workbook.close()
    except InvalidSourceUpload:
        raise
    except Exception as exc:
        raise InvalidSourceUpload("could not parse XLSX workbook") from exc


def validate_source_upload(upload) -> ValidatedSource:
    """Read once, validate extension + bytes + spreadsheet structure, hash."""
    original_name = (getattr(upload, "name", "") or "").replace("\\", "/").split("/")[-1]
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in {"csv", "xlsx"}:
        raise InvalidSourceUpload("only .csv and .xlsx question sources are supported")
    content = upload.read(MAX_SOURCE_BYTES + 1)
    if not content:
        raise InvalidSourceUpload("uploaded file is empty")
    if len(content) > MAX_SOURCE_BYTES:
        raise InvalidSourceUpload("file exceeds the 10 MB import limit")
    if extension == "csv":
        _validate_csv(content)
    else:
        _validate_xlsx(content)
    return ValidatedSource(
        content=content,
        filename=_safe_filename(original_name, extension),
        source_format=extension,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _matches_existing(job, *, source, school, subject, class_level) -> bool:
    return (
        job.source_sha256 == source.sha256
        and job.source_size_bytes == len(source.content)
        and job.school_id == school.pk
        and job.subject_id == subject.pk
        and job.class_level_id == class_level.pk
    )


def create_source_import_job(
    *, organization, actor, school, subject, class_level, source: ValidatedSource, idempotency_key: str
):
    """Persist a private source and an uploaded job; return (job, created).

    The unique organization/idempotency constraint is the final concurrency
    guard. A losing concurrent request deletes its unreferenced object.
    """
    from apps.core.storage import delete_document, save_document

    key = idempotency_key.strip()
    if not key or len(key) > 128 or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key):
        raise InvalidSourceUpload("Idempotency-Key must be 8-128 safe characters")

    existing = CBTImportJob.objects.filter(organization=organization, idempotency_key=key).first()
    if existing:
        if not _matches_existing(existing, source=source, school=school, subject=subject, class_level=class_level):
            raise ImportIdempotencyConflict("Idempotency-Key was already used for a different upload or target")
        return existing, False

    stored_key = save_document(
        key_prefix=f"cbt-imports/{organization.public_id}/{key[:48]}",
        filename=f"{source.sha256[:16]}-{source.filename}",
        content=source.content,
        content_type=(
            "text/csv" if source.source_format == "csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    try:
        with transaction.atomic():
            job = CBTImportJob.objects.create(
                organization=organization,
                created_by=actor,
                school=school,
                subject=subject,
                class_level=class_level,
                source_name=source.filename,
                source_format=source.source_format,
                storage_key=stored_key,
                source_sha256=source.sha256,
                source_size_bytes=len(source.content),
                idempotency_key=key,
                status="uploaded",
            )
        return job, True
    except IntegrityError:
        delete_document(stored_key)
        winner = CBTImportJob.objects.filter(organization=organization, idempotency_key=key).first()
        if winner and _matches_existing(
            winner, source=source, school=school, subject=subject, class_level=class_level
        ):
            return winner, False
        if winner:
            raise ImportIdempotencyConflict(
                "Idempotency-Key was concurrently used for a different upload or target"
            )
        raise
    except Exception:
        delete_document(stored_key)
        raise
