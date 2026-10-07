"""PubliBike API: fetch the station snapshot and apply the tracking rule (docs/api.md §3b)."""

import unicodedata

import requests

API_URL = "https://rest.publibike.ch/v1/public/all/stations"
USER_AGENT = "publibike-zurich-research/0.1 (personal data project; github.com/Jakobps1704/publibike_projekt)"

# A response is treated as an outage if it contains fewer than this share of the tracked stations.
MIN_SHARE_TRACKED = 0.8


def fetch_stations() -> list[dict]:
    """Return the raw station records from the all/stations endpoint."""
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
