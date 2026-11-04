"""Local-dev image upload/serve (NON-PRODUCTION ONLY).

A disk-backed stand-in for Cloudflare R2 so the admin catalog/themes UI can
upload and display images without R2 configured (e.g. in a Codespace). The
router is only mounted when ``settings.local_uploads_enabled`` is true, which is
never the case in production. Files are written under ``LOCAL_UPLOAD_DIR`` and
served back by key.

Object keys look like ``plans/13/gallery/ab12-photo.jpg`` or
``cakes/xx-photo.jpg``; we store them under the upload dir preserving that path.
Keys are sanitised to stay within the upload dir (no traversal).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationFailedError

router = APIRouter(prefix="/api/v1/dev-uploads", tags=["dev-uploads"])

# Allowed image content types (best-effort; this is a dev convenience).
_ALLOWED_PREFIX = "image/"


def _safe_path(key: str) -> Path:
    """Resolve an object key to a path strictly inside the upload dir."""
    base = Path(settings.LOCAL_UPLOAD_DIR).resolve()
    target = (base / key).resolve()
    if base not in target.parents and target != base:
        # Path traversal attempt (e.g. ../../etc/passwd).
        raise ValidationFailedError("Invalid upload key.")
    return target


@router.put("/{key:path}", status_code=201)
async def put_dev_upload(key: str, request: Request) -> Response:
    """Store raw image bytes for an object key on local disk (dev only)."""
    content_type = request.headers.get("content-type", "")
    if content_type and not content_type.startswith(_ALLOWED_PREFIX):
        # Allow empty content-type (some clients omit it) but reject non-images.
        raise ValidationFailedError("Only image uploads are allowed.")
    body = await request.body()
    if not body:
        raise ValidationFailedError("Empty upload.")
    path = _safe_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return Response(status_code=201)


@router.get("/{key:path}")
def get_dev_upload(key: str) -> FileResponse:
    """Serve a previously uploaded dev image by its object key."""
    path = _safe_path(key)
    if not path.is_file():
        raise NotFoundError("Image not found.")
    return FileResponse(path)
