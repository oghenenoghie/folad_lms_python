"""Deterministic row extraction for private CBT CSV/XLSX source files.

This layer only extracts source rows into a canonical, JSON-safe shape. It
does not validate question semantics, write database rows, or dispatch work.
"""
import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from apps.cbt.services.source_upload_service import MAX_ROWS


_REQUIRED_HEADERS = {"text", "correct"}


class SourceExtractionError(ValueError):
    """A previously uploaded source cannot be extracted safely."""


@dataclass(frozen=True)
class ExtractedImportRow:
    sequence: int
    source_locator: dict[str, Any]
    payload: dict[str, Any]
    source_fingerprint: str


def _headers(values) -> list[str]:
    headers = [str(value).strip().lower() if value is not None else "" for value in values]
    while headers and not headers[-1]:
        headers.pop()
    if not headers or any(not header for header in headers):
        raise SourceExtractionError("source header row contains an empty column name")
    if len(headers) != len(set(headers)):
        raise SourceExtractionError("source header row contains duplicate column names")
    missing = _REQUIRED_HEADERS - set(headers)
    if missing:
        raise SourceExtractionError(
            f"source is missing required column(s): {', '.join(sorted(missing))}"
        )
    return headers


def _cell_value(value: Any) -> Any:
    """Convert spreadsheet-native values into stable JSON-safe primitives."""
    if value is None:
        return ""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _fingerprint(*, locator: dict[str, Any], payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        {"locator": locator, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_rows(headers, rows, *, locator_key: str, sheet_name: str | None = None):
    extracted = []
    for source_row, values in rows:
        if source_row > MAX_ROWS + 1:
            raise SourceExtractionError(f"source exceeds the {MAX_ROWS:,}-row import limit")
        values = list(values)
        if len(values) > len(headers) and any(value not in (None, "") for value in values[len(headers):]):
            raise SourceExtractionError(
                f"source row {source_row} contains data beyond the header columns"
            )
        values = values[:len(headers)]
        values.extend([""] * (len(headers) - len(values)))
        payload = {header: _cell_value(value) for header, value in zip(headers, values)}
        if not any(value != "" for value in payload.values()):
            continue
        locator = {locator_key: source_row}
        if sheet_name is not None:
            locator["sheet"] = sheet_name
        extracted.append(
            ExtractedImportRow(
                sequence=len(extracted) + 1,
                source_locator=locator,
                payload=payload,
                source_fingerprint=_fingerprint(locator=locator, payload=payload),
            )
        )
    return extracted


def extract_source_rows(*, content: bytes, source_format: str) -> list[ExtractedImportRow]:
    """Extract non-empty question rows from validated CSV or XLSX bytes.

    Header names are normalised to lowercase; cell values are preserved
    (with dates and decimals converted to stable strings). Original row
    numbers are retained even when blank rows are skipped.
    """
    if not content:
        raise SourceExtractionError("source file is empty")

    if source_format == "csv":
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SourceExtractionError("CSV must use UTF-8 encoding") from exc
        if "\x00" in decoded:
            raise SourceExtractionError("CSV contains binary or NUL characters")
        try:
            reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
            headers = _headers(next(reader, []))
            rows = ((row_number, row) for row_number, row in enumerate(reader, start=2))
            return _build_rows(headers, rows, locator_key="row")
        except csv.Error as exc:
            raise SourceExtractionError("CSV contains malformed data") from exc

    if source_format == "xlsx":
        try:
            from openpyxl import load_workbook

            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            try:
                sheet = workbook.active
                iterator = sheet.iter_rows(values_only=True)
                headers = _headers(next(iterator, ()))
                rows = ((row_number, row) for row_number, row in enumerate(iterator, start=2))
                return _build_rows(headers, rows, locator_key="row", sheet_name=sheet.title)
            finally:
                workbook.close()
        except SourceExtractionError:
            raise
        except Exception as exc:
            raise SourceExtractionError("could not extract rows from XLSX workbook") from exc

    raise SourceExtractionError("only CSV and XLSX sources can be extracted")
