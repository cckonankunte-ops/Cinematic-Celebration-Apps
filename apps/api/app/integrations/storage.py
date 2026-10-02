"""Cloudflare R2 (S3-compatible) storage integration.

Public reads: gallery/add-on images are served from a public bucket on a custom
CDN domain. We only build the public URL from the object key — NO presigned URLs
for public reads. Presigned PUT URLs are used for admin uploads only.
"""

from __future__ import annotations

import boto3

from app.core.config import settings


def public_url(object_key: str) -> str:
    """Return the public CDN URL for an R2 object key."""
    domain = settings.IMG_CDN_DOMAIN.rstrip("/")
    key = object_key.lstrip("/")
    return f"https://{domain}/{key}"


def _s3_client():  # pragma: no cover - requires real R2 credentials
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    )


def create_upload_url(object_key: str, expires_in: int = 900) -> str:  # pragma: no cover
    """Return a short-lived presigned PUT URL for an admin upload to the public bucket."""
    client = _s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.R2_PUBLIC_BUCKET, "Key": object_key},
        ExpiresIn=expires_in,
    )
