"""Apply a .sql bootstrap file to MySQL, honouring the ``DELIMITER`` directive.

The MySQL command-line client understands ``DELIMITER``; a driver does not, so
this helper splits the file into statements itself before sending them.

Usage:
    python scripts/apply_sql.py database/03_procedures.sql
    python scripts/apply_sql.py database/01_tables.sql database/02_triggers.sql

Connection settings are read from the environment first, then from
``backend/.env`` so the script matches whatever the API uses.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pymysql

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_connection_settings() -> dict[str, object]:
    env = load_env_file(PROJECT_ROOT / "backend" / ".env")

    def pick(name: str, default: str) -> str:
        return os.environ.get(name) or env.get(name) or default

    return {
        "host": pick("MYSQL_HOST", "127.0.0.1"),
        "port": int(pick("MYSQL_PORT", "3306")),
        "user": pick("MYSQL_USER", "root"),
        "password": pick("MYSQL_PASSWORD", ""),
        "charset": "utf8mb4",
        "autocommit": True,
    }


def split_statements(sql_text: str) -> list[str]:
    """Split a script into statements, tracking custom delimiters."""
    delimiter = ";"
    statements: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        statement = "\n".join(buffer).strip()
        if statement:
            statements.append(statement)
        buffer.clear()

    for raw_line in sql_text.splitlines():
        line = raw_line.strip()
        if line.startswith("--") or not line:
            continue
        if line.upper().startswith("DELIMITER "):
            flush()
            delimiter = line.split(None, 1)[1].strip()
            continue

        buffer.append(raw_line)
        joined = "\n".join(buffer).rstrip()
        if joined.endswith(delimiter):
            joined = joined[: -len(delimiter)].rstrip()
            buffer.clear()
            if joined:
                statements.append(joined)

    flush()
    return statements


def apply_file(connection: pymysql.connections.Connection, path: Path) -> int:
    script = path.read_text(encoding="utf-8")
    statements = split_statements(script)
    with connection.cursor() as cursor:
        cursor.execute("USE gymfitness")
        for statement in statements:
            cursor.execute(statement)
    return len(statements)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    settings = build_connection_settings()
    connection = pymysql.connect(**settings)  # type: ignore[arg-type]
    try:
        for argument in argv[1:]:
            target = Path(argument)
            if not target.is_absolute():
                target = PROJECT_ROOT / target
            if not target.exists():
                print(f"FAIL  {target} (not found)")
                return 1
            count = apply_file(connection, target)
            print(f"OK    {target.name} ({count} statements)")
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
