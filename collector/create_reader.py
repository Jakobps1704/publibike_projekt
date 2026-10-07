"""Create or update the read-only database user `publibike_reader` for analysis and sharing.

- Grants SELECT on all tables and views (also future ones) and adds RLS read policies for it.
- Sets a 60 s statement timeout so a runaway query can't hog the free-tier database.
- On first run, or with --rotate, generates a new password and writes ANALYSIS_DATABASE_URL to .env.
  The password is never printed.

Run with the admin DATABASE_URL:  python collector/create_reader.py [--rotate]
"""

import os
import secrets
import string
import sys
from urllib.parse import quote, urlsplit, urlunsplit

from psycopg import sql

from publibike.db import REPO_ROOT, _load_env, connect

ROLE = "publibike_reader"
TABLES = ("polls", "stations", "station_states", "station_status")
ENV_KEY = "ANALYSIS_DATABASE_URL"


def main() -> None:
    rotate = "--rotate" in sys.argv[1:]
    role = sql.Identifier(ROLE)

    with connect(admin=True) as conn:
        exists = conn.execute("select 1 from pg_roles where rolname = %s", (ROLE,)).fetchone()
        password = None
        if not exists or rotate:
            password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
            verb = sql.SQL("alter" if exists else "create")
            conn.execute(sql.SQL("{} role {} with login password {}").format(verb, role, sql.Literal(password)))

        conn.execute(sql.SQL("alter role {} set statement_timeout = '60s'").format(role))
        conn.execute(sql.SQL("grant usage on schema public to {}").format(role))
        conn.execute(sql.SQL("grant select on all tables in schema public to {}").format(role))
        conn.execute(sql.SQL("alter default privileges in schema public grant select on tables to {}").format(role))
        for table in TABLES:
            policy = sql.Identifier(f"{ROLE}_read")
            conn.execute(sql.SQL("drop policy if exists {} on {}").format(policy, sql.Identifier(table)))
            conn.execute(sql.SQL("create policy {} on {} for select to {} using (true)")
                         .format(policy, sql.Identifier(table), role))

    if password:
        write_env(reader_url(password))
        print(f"Role {ROLE} {'password rotated' if exists else 'created'}; {ENV_KEY} written to .env.")
    else:
        print(f"Role {ROLE} exists; grants and policies refreshed (password unchanged, use --rotate to change it).")


def reader_url(password: str) -> str:
    """Build the reader's URL from the admin DATABASE_URL: same host and database, different user."""
    _load_env()
    admin = urlsplit(os.environ["DATABASE_URL"])
    # The Supabase pooler expects "<role>.<project-ref>" as user name.
    admin_user = admin.username or ""
    user = f"{ROLE}.{admin_user.split('.', 1)[1]}" if "." in admin_user else ROLE
    netloc = f"{user}:{quote(password, safe='')}@{admin.hostname}" + (f":{admin.port}" if admin.port else "")
    return urlunsplit((admin.scheme, netloc, admin.path, admin.query, admin.fragment))


def write_env(url: str) -> None:
    """Set ENV_KEY in the repo's .env, replacing an existing line and keeping all others."""
    path = REPO_ROOT / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if not line.startswith(f"{ENV_KEY}=")]
    lines.append(f"{ENV_KEY}={url}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
