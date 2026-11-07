"""Cloudflare R2 (S3-compatible) storage integration.

Public reads: gallery/add-on images are served from a public bucket on a custom
CDN domain. We only build the public URL from the object key — NO presigned URLs
for public reads. Presigned PUT URLs are used for admin uploads only.

Local-dev fallback (NON-PRODUCTION ONLY): when R2 is not configured in a dev /
Codespace environment, uploads are stored on local disk and served by the API
so the catalog/themes UI works without R2. Guarded by
``settings.local_uploads_enabled`` (never true in production).
"""

from __future__ import annotations

import boto3
from botocore.config import Config

from app.core.config import settings

# R2 presigned URLs must use Signature Version 4 (SigV4). The boto3 default can
# fall back to the legacy SigV2 query format (AWSAccessKeyId/Signature), which
# R2 rejects on the browser CORS preflight (OPTIONS -> 401). SigV4 +
# path-style addressing produces a presigned PUT URL R2 accepts cross-origin.
_R2_CONFIG = Config(signature_version="s3v4", s3={"addressing_style": "path"})


def public_url(object_key: str) -> str:
    """Return the public URL for an object key (R2 CDN, or local-dev serve)."""
    key = object_key.lstrip("/")
    if settings.local_uploads_enabled:
        base = settings.LOCAL_UPLOAD_BASE_URL.rstrip("/")
        return f"{base}/api/v1/dev-uploads/{key}"
    domain = settings.IMG_CDN_DOMAIN.rstrip("/")
    return f"https://{domain}/{key}"


def _s3_client():  # pragma: no cover - requires real R2 credentials
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=_R2_CONFIG,
    )


def create_upload_url(object_key: str, expires_in: int = 900) -> str:
    """Return an upload (PUT) URL for the given object key.

    Real R2: a short-lived presigned PUT URL to the public bucket.
    Local-dev fallback: the API's own dev-upload endpoint for this key.
    """
    key = object_key.lstrip("/")
    if settings.local_uploads_enabled:
        base = settings.LOCAL_UPLOAD_BASE_URL.rstrip("/")
        return f"{base}/api/v1/dev-uploads/{key}"
    client = _s3_client()  # pragma: no cover - requires real R2 credentials
    return client.generate_presigned_url(  # pragma: no cover
        "put_object",
        Params={"Bucket": settings.R2_PUBLIC_BUCKET, "Key": object_key},
        ExpiresIn=expires_in,
    )
