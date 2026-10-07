"""Shared helpers: API fetch, station parsing, database connection."""

import os
import unicodedata
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

API_URL = "https://rest.publibike.ch/v1/public/all/stations"
USER_AGENT = "publibike-zurich-research/0.1 (personal data project; github.com/Jakobps1704/publibike_projekt)"

# A response is treated as an outage if it contains fewer than this share of the tracked stations.
MIN_SHARE_TRACKED = 0.8


def fetch_stations() -> list[dict]:
    """Return the raw station records from the all/stations endpoint (docs/api.md §3b)."""
    resp = requests.get(API_URL, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    velospot = resp.json()["velospot"]
    status = velospot.get("responseStatus", {}).get("STATUS")
    if status != "SUCCESS":
        raise RuntimeError(f"API responseStatus is {status!r}, expected 'SUCCESS'")
    return velospot["responseData"]


def is_zurich(record: dict) -> bool:
    """Tracking rule: the station name contains "Zürich" (docs/decisions.md)."""
    name = unicodedata.normalize("NFC", record.get("station_name") or "")
    return "zürich" in name.casefold()


def parse_station(record: dict) -> dict:
    """Map an API record to the columns of the stations table. Raises on missing or malformed fields."""
    return {
        "station_number": int(record["stationNumber"]),
        "velospot_id": record["station_id"],
        "name": record["station_name"].strip(),
        "address": (record.get("station_address") or "").strip() or None,
        "lat": float(record["lat"]),
        "lon": float(record["lng"]),
    }


def connect() -> psycopg.Connection:
    """Connect using DATABASE_URL from the environment or .env in the repo root."""
    load_dotenv(ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (see .env.example)")
    try:
        return psycopg.connect(url)
    except psycopg.Error as exc:
        # The driver's message can echo parts of the URL, including the password.
        raise SystemExit(f"Could not connect ({type(exc).__name__}). Check DATABASE_URL.") from None
