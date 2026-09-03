"""Provider-agnostic object storage (§14 ARCHITECTURE.md: "a StorageBackend
protocol abstracts S3 / Cloudflare R2 / MinIO — the provider is
configuration, never hard-coded"). `STORAGE_BACKEND="s3"` (the production
default) talks to S3 directly via boto3. Any other value
(`STORAGE_BACKEND="local"`, set in config.settings.test and available for
local dev) falls back to Django's own `default_storage` (FileSystemStorage),
so this needs no cloud credentials to exercise locally or in the test suite.

Two storage shapes for two different needs:
- `save_file()` — generate-once-use-soon: returns a URL immediately (a
  presigned one for S3, valid an hour), for content like a Celery-generated
  report-card/receipt PDF that's fetched shortly after it's ready.
- `save_document()` + `get_presigned_download_url()` — store-once-access-
  later: returns the storage key (not a URL) at save time, so a fresh
  presigned URL can be computed at each future request rather than
  persisting one that will eventually expire. Used by apps.documents and
  apps.assignments for user-uploaded files.

`get_file_bytes()` is the odd one out — reads actual content back for a
key rather than a URL, for callers that need to hand a library real
bytes (e.g. embedding an image in a server-rendered PDF).
"""
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

_MAGIC_BYTES: dict[str, bytes] = {
    "application/pdf": b"%PDF",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}

ALLOWED_UPLOAD_CONTENT_TYPES = frozenset(
    {"application/pdf", "image/png", "image/jpeg", "text/plain"}
)

DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class InvalidUpload(ValueError):
    pass


def validate_upload(
    *, content: bytes, content_type: str, max_size_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
) -> None:
    """§14's upload path: "validate MIME + magic bytes + size limit". Magic-
    byte sniffing only covers types with a fixed signature (not `text/plain`,
    which has none) — that's a real check, not a rubber stamp, for the
    types it does cover.
    """
    if content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise InvalidUpload(f"unsupported content type: {content_type!r}")
    if not content:
        raise InvalidUpload("uploaded file is empty")
    if len(content) > max_size_bytes:
        raise InvalidUpload(f"file exceeds the {max_size_bytes}-byte limit")
    magic = _MAGIC_BYTES.get(content_type)
    if magic is not None and not content.startswith(magic):
        raise InvalidUpload("file content does not match its declared content type")


def save_file(*, key_prefix: str, filename: str, content: bytes, content_type: str) -> str:
    """Store `content` under a tenant-scoped key (callers should pass a
    prefix like f"report-cards/{organization_id}") and return a URL to
    retrieve it.
    """
    key = f"{key_prefix}/{uuid.uuid4()}-{filename}"
    if settings.STORAGE_BACKEND == "s3":
        _put_to_s3(key=key, content=content, content_type=content_type)
        return _presigned_s3_url(key)
    saved_path = default_storage.save(key, ContentFile(content))
    return default_storage.url(saved_path)


def save_document(*, key_prefix: str, filename: str, content: bytes, content_type: str) -> str:
    """Like save_file(), but returns the storage key itself rather than a
    URL — see the module docstring."""
    key = f"{key_prefix}/{uuid.uuid4()}-{filename}"
    if settings.STORAGE_BACKEND == "s3":
        _put_to_s3(key=key, content=content, content_type=content_type)
    else:
        default_storage.save(key, ContentFile(content))
    return key


def get_presigned_download_url(key: str) -> str:
    """Computed fresh at request time, never stored — per §14: "Downloads
    are served via short-lived presigned URLs generated only after an
    authorization + tenant-ownership check". Callers are responsible for
    that check before calling this.
    """
    if settings.STORAGE_BACKEND == "s3":
        return _presigned_s3_url(key)
    return default_storage.url(key)


def get_file_bytes(key: str) -> bytes | None:
    """Reads raw bytes back for a key saved via save_document() — the one
    thing neither save_file()/save_document() (return a URL or key, never
    content) nor get_presigned_download_url() (also a URL) can do.
    Needed wherever the caller has to hand a library actual bytes rather
    than a URL, e.g. embedding a student's photo in a ReportLab-rendered
    PDF via apps.report_cards.services.report_card_pdf_service.

    Returns None rather than raising for any read failure (missing key,
    unreachable backend, ...) — callers that only want to embed
    something-if-present shouldn't have their whole render fail over one
    unreadable file.
    """
    try:
        if settings.STORAGE_BACKEND == "s3":
            response = _s3_client().get_object(Bucket=settings.STORAGE_BUCKET_NAME, Key=key)
            return response["Body"].read()
        with default_storage.open(key, "rb") as f:
            return f.read()
    except Exception:
        return None


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT_URL,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        region_name=settings.STORAGE_REGION,
    )


def _put_to_s3(*, key: str, content: bytes, content_type: str) -> None:
    _s3_client().put_object(
        Bucket=settings.STORAGE_BUCKET_NAME, Key=key, Body=content, ContentType=content_type
    )


def _presigned_s3_url(key: str) -> str:
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.STORAGE_BUCKET_NAME, "Key": key},
        ExpiresIn=3600,
    )
