"""Create or update the database schema from schema.sql.

Reads DATABASE_URL (admin) from the environment or from .env in the repo root.
"""

from pathlib import Path

from publibike.db import connect

SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def main() -> None:
    with connect(admin=True) as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        tables = conn.execute(
            "select table_name from information_schema.tables "
            "where table_schema = 'public' order by table_name"
        ).fetchall()

    print("Schema applied. Tables and views in public:", ", ".join(t[0] for t in tables))


if __name__ == "__main__":
    main()
