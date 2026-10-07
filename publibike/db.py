"""Database connection.

Two connection strings, both read from the environment or a .env file:
- ANALYSIS_DATABASE_URL: read-only user `publibike_reader`. Used by `publibike.data`, safe to share.
- DATABASE_URL: the admin user. Used only by the collector scripts; never share it.
"""

import os
from pathlib import Path

import psycopg
from dotenv import find_dotenv, load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    load_dotenv(find_dotenv(usecwd=True))  # .env in the current folder or a parent (e.g. next to a notebook)
    load_dotenv(REPO_ROOT / ".env")        # .env in the repo root, when working in a clone


def connect(admin: bool = False) -> psycopg.Connection:
    """Open a connection. Read-only by default; `admin=True` is for the collector scripts."""
    _load_env()
    var = "DATABASE_URL" if admin else "ANALYSIS_DATABASE_URL"
    url = os.environ.get(var)
    if not url:
        raise SystemExit(f"{var} is not set. Put it in a .env file or the environment (see docs/data_access.md).")
    try:
        return psycopg.connect(url)
    except psycopg.Error as exc:
        # The driver's message can echo parts of the URL, including the password.
        raise SystemExit(f"Could not connect ({type(exc).__name__}). Check {var}.") from None
