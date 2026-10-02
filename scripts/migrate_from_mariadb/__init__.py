"""One-off MariaDB -> PostgreSQL migration scripts for Cinematic Celebration.

These scripts are standalone and are intentionally kept OUT of the FastAPI app
package. They are run manually, in order, on the migration machine:

    precheck.py  -> extract.py -> upload_images.py -> transform.py
                 -> load.py    -> validate.py

Only ``transform.py`` holds pure, importable, unit-testable logic (no DB or
network calls). The remaining modules talk to MariaDB, PostgreSQL, or R2.

See README.md for the full run order, prerequisites, and the documented
migration decisions (the "DECIDE" choices).
"""
