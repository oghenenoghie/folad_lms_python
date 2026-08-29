"""Provider-agnostic object storage (§14 ARCHITECTURE.md: "a StorageBackend
protocol abstracts S3 / Cloudflare R2 / MinIO — the provider is
configuration, never hard-coded"). `STORAGE_BACKEND="s3"` (the production
default) uploads via boto3 directly and returns a short-lived presigned
URL — "Downloads are served via short-lived presigned URLs" per the same
section. Any other value (`STORAGE_BACKEND="local"`, set in
config.settings.test and available for local dev) falls back to Django's
own `default_storage` (FileSystemStorage), so this needs no cloud
credentials to exercise locally or in the test suite.
"""
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def save_file(*, key_prefix: str, filename: str, content: bytes, content_type: str) -> str:
    """Store `content` under a tenant-scoped key (callers should pass a
    prefix like f"report-cards/{organization_id}") and return a URL to
    retrieve it.
    """
    key = f"{key_prefix}/{uuid.uuid4()}-{filename}"
    if settings.STORAGE_BACKEND == "s3":
        return _save_to_s3(key=key, content=content, content_type=content_type)
    saved_path = default_storage.save(key, ContentFile(content))
    return default_storage.url(saved_path)


def _save_to_s3(*, key: str, content: bytes, content_type: str) -> str:
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT_URL,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        region_name=settings.STORAGE_REGION,
    )
    client.put_object(
        Bucket=settings.STORAGE_BUCKET_NAME, Key=key, Body=content, ContentType=content_type
    )
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.STORAGE_BUCKET_NAME, "Key": key},
        ExpiresIn=3600,
    )
