"""Upload old image blobs/files to the public Cloudflare R2 bucket.

The old schema stores images in longtext columns (`cake.image`,
`special_decor.image`, `combos.image`) and a `plan.galleryimages` JSON array.
Those values may be:

- a local filesystem path (resolved against IMG_SOURCE_DIR),
- a URL/path reference (used to derive a stable object key), or
- a base64 data URI ("data:<mime>;base64,...").

Assumptions (documented): a value that looks like a data URI is decoded and
uploaded; otherwise the value is treated as a path/URL — if a matching local
file exists under IMG_SOURCE_DIR it is uploaded, else only an object key is
derived (no bytes uploaded) so load.py still has a key to store. The network
upload paths are marked ``pragma: no cover``.

Usage:
    python -m scripts.migrate_from_mariadb.upload_images
"""

from __future__ import annotations

import base64
import os
import posixpath
import re
from typing import Any

from .config import MigrationConfig, load_config

_DATA_URI_RE = re.compile(r"^data:(?P<mime>[\w/\-.+]+)?;base64,(?P<payload>.+)$", re.DOTALL)
_MIME_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def is_data_uri(value: str) -> bool:
    """Return True if the string is a base64 data URI."""
    return bool(_DATA_URI_RE.match(value or ""))


def derive_object_key(reference: str, *, prefix: str, kind: str, item_id: Any) -> str:
    """Derive a stable R2 object key for a reference.

    For path/URL references the basename is reused; otherwise a key based on the
    kind and item id is synthesized. The optional bucket prefix is prepended.
    """
    base = ""
    if reference and not is_data_uri(reference):
        base = posixpath.basename(reference.replace("\\", "/").split("?")[0])
    if not base:
        base = f"{item_id}.jpg"
    key = f"{kind}/{item_id}/{base}"
    if prefix:
        key = f"{prefix.rstrip('/')}/{key}"
    return key


def _decode_data_uri(value: str) -> tuple[bytes, str]:
    """Decode a base64 data URI into (bytes, file-extension)."""
    match = _DATA_URI_RE.match(value)
    assert match is not None  # guarded by is_data_uri
    payload = base64.b64decode(match.group("payload"))
    ext = _MIME_EXT.get(match.group("mime") or "", ".bin")
    return payload, ext


def _r2_client(config: MigrationConfig):  # pragma: no cover - requires network
    """Build a boto3 S3 client pointed at the R2 endpoint."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=config.r2.endpoint_url,
        aws_access_key_id=config.r2.access_key_id,
        aws_secret_access_key=config.r2.secret_access_key,
    )


def upload_reference(  # pragma: no cover - network / filesystem side effects
    client: Any,
    config: MigrationConfig,
    reference: str,
    *,
    kind: str,
    item_id: Any,
) -> str:
    """Upload one image reference to R2 and return its stored object key.

    Returns an object key even when no bytes are uploaded (path/URL with no
    local file), so downstream records always have a key to store.
    """
    bucket = config.r2.public_bucket
    if is_data_uri(reference):
        payload, ext = _decode_data_uri(reference)
        key = derive_object_key(f"{item_id}{ext}", prefix=config.r2.public_prefix,
                                kind=kind, item_id=item_id)
        client.put_object(Bucket=bucket, Key=key, Body=payload)
        return key

    key = derive_object_key(reference, prefix=config.r2.public_prefix,
                            kind=kind, item_id=item_id)
    local_path = os.path.join(config.r2.image_source_dir, os.path.basename(reference)) \
        if config.r2.image_source_dir else ""
    if local_path and os.path.isfile(local_path):
        client.upload_file(local_path, bucket, key)
    else:
        print(f"  no local file for {kind} {item_id}; key only: {key}")
    return key


def run(config: MigrationConfig) -> dict[str, str]:  # pragma: no cover - network
    """Upload catalog images referenced in the extracted JSON; return key map.

    The returned mapping is keyed by "<kind>:<item_id>" -> object_key and is
    consumed by load.py to replace the raw image references with R2 keys.
    """
    import json

    client = _r2_client(config)
    key_map: dict[str, str] = {}
    for kind, table, column in (
        ("cakes", "cake", "image"),
        ("decor", "special_decor", "image"),
        ("combos", "combos", "image"),
    ):
        path = os.path.join(config.data_dir, f"{table}.json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            rows = json.load(handle)
        for row in rows:
            ref = row.get(column)
            if not ref:
                continue
            key = upload_reference(client, config, ref, kind=kind, item_id=row["id"])
            key_map[f"{kind}:{row['id']}"] = key
    print(f"uploaded/derived {len(key_map)} image keys")
    return key_map


def main() -> None:  # pragma: no cover - CLI entry
    """CLI entry point: upload all catalog images using environment config."""
    run(load_config())


if __name__ == "__main__":  # pragma: no cover
    main()
