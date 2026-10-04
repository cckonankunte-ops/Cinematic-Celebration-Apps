"""Parse a phpMyAdmin / mysqldump .sql file into per-table JSON.

This replaces extract.py for the case where you have a .sql DUMP FILE instead
of a live MariaDB server. It parses every ``INSERT INTO `table` (cols) VALUES
(...),(...);`` statement into row dicts and writes ``<data_dir>/<table>.json``
using the OLD table names that transform.py / load.py expect
(booking, location, plan, slot, cake, combos, special_decor, occasion, users,
user_role, contact_form_leads).

After running this, run load.py to transform + insert into PostgreSQL.

Usage:
    python -m scripts.migrate_from_mariadb.dump_to_json path/to/dump.sql [data_dir]

Only tables we migrate are extracted; everything else in the dump is ignored.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# Old tables we care about (others in the dump are ignored).
WANTED_TABLES = frozenset(
    {
        "booking",
        "location",
        "plan",
        "slot",
        "cake",
        "combos",
        "special_decor",
        "occasion",
        "users",
        "user_role",
        "contact_form_leads",
    }
)


def _tokenize_values(segment: str) -> list[list[Any]]:
    """Parse a VALUES body ``(..),(..),..`` into a list of row value-lists.

    Handles single-quoted strings with '' and backslash escapes, NULL, ints,
    and floats. Returns Python values (str/int/float/None).
    """
    rows: list[list[Any]] = []
    i, n = 0, len(segment)
    while i < n:
        # Find the next '(' that opens a row.
        if segment[i] != "(":
            i += 1
            continue
        i += 1  # skip '('
        values: list[Any] = []
        current = ""
        in_string = False
        token_is_string = False
        while i < n:
            ch = segment[i]
            if in_string:
                if ch == "\\" and i + 1 < n:
                    current += segment[i + 1]
                    i += 2
                    continue
                if ch == "'":
                    # Doubled '' inside a string = literal single quote.
                    if i + 1 < n and segment[i + 1] == "'":
                        current += "'"
                        i += 2
                        continue
                    in_string = False
                    i += 1
                    continue
                current += ch
                i += 1
                continue
            # not in string
            if ch == "'":
                in_string = True
                token_is_string = True
                current = ""  # discard any whitespace before the opening quote
                i += 1
                continue
            if ch in ",)":
                values.append(_coerce(current, token_is_string))
                current = ""
                token_is_string = False
                i += 1
                if ch == ")":
                    break
                continue
            current += ch
            i += 1
        rows.append(values)
        # Skip whitespace/comma until the next '(' or end.
        while i < n and segment[i] not in "(;":
            i += 1
    return rows


def _coerce(raw: str, is_string: bool) -> Any:
    """Convert a raw token to a Python value."""
    if is_string:
        return raw
    token = raw.strip()
    if token == "" or token.upper() == "NULL":
        return None
    try:
        if "." in token or "e" in token.lower():
            return float(token)
        return int(token)
    except ValueError:
        return token


def _split_columns(col_segment: str) -> list[str]:
    """Parse the ``(`a`, `b`, ...)`` column list into column names."""
    return [c.strip().strip("`") for c in col_segment.split(",")]


def parse_dump(sql_text: str) -> dict[str, list[dict[str, Any]]]:
    """Parse all wanted INSERT statements into {table: [row dicts]}."""
    out: dict[str, list[dict[str, Any]]] = {t: [] for t in WANTED_TABLES}
    marker = "INSERT INTO `"
    pos = 0
    while True:
        start = sql_text.find(marker, pos)
        if start == -1:
            break
        # table name
        name_start = start + len(marker)
        name_end = sql_text.find("`", name_start)
        table = sql_text[name_start:name_end]
        # column list between the first '(' and the matching ')'
        paren_open = sql_text.find("(", name_end)
        paren_close = sql_text.find(")", paren_open)
        columns = _split_columns(sql_text[paren_open + 1 : paren_close])
        # VALUES ... up to the terminating ';'
        values_kw = sql_text.find("VALUES", paren_close)
        stmt_end = sql_text.find(";", values_kw)
        values_body = sql_text[values_kw + len("VALUES") : stmt_end]
        pos = stmt_end + 1
        if table not in WANTED_TABLES:
            continue
        for value_row in _tokenize_values(values_body):
            if len(value_row) != len(columns):
                # Skip malformed rows rather than corrupt the dataset.
                continue
            out[table].append(dict(zip(columns, value_row, strict=False)))
    return out


def main() -> None:
    """CLI: parse the dump file and write <data_dir>/<table>.json."""
    if len(sys.argv) < 2:
        print("usage: python -m scripts.migrate_from_mariadb.dump_to_json "
              "path/to/dump.sql [data_dir]")
        raise SystemExit(2)
    dump_path = sys.argv[1]
    data_dir = sys.argv[2] if len(sys.argv) > 2 else os.environ.get(
        "MIGRATION_DATA_DIR", "./_data"
    )
    with open(dump_path, encoding="utf-8", errors="replace") as handle:
        sql_text = handle.read()

    tables = parse_dump(sql_text)
    os.makedirs(data_dir, exist_ok=True)
    for table, rows in tables.items():
        path = os.path.join(data_dir, f"{table}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, ensure_ascii=False, default=str)
        print(f"{len(rows):>6} rows -> {path}")


if __name__ == "__main__":
    main()
