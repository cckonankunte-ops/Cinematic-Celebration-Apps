"""Export the FastAPI OpenAPI schema to a JSON file.

The OpenAPI document is the contract the frontends consume (they generate
TypeScript types from it with openapi-typescript). Run:

    python -m scripts.export_openapi [output_path]

Defaults to ../../openapi.json at the repo api root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import create_app


def export(output_path: str | None = None) -> Path:
    """Write the OpenAPI JSON and return the path."""
    app = create_app()
    schema = app.openapi()
    default_path = Path(__file__).resolve().parent.parent / "openapi.json"
    out = Path(output_path) if output_path else default_path
    out.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
    return out


if __name__ == "__main__":
    target = export(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Wrote OpenAPI schema to {target}")
