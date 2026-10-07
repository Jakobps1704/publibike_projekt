"""Fetch one snapshot and store the counts of every tracked station. Runs every 5 minutes.

Every run writes a `polls` row, also when the fetch fails or the response looks like an outage,
so gaps in station_status can be told apart from "no data". Status rows are written only for ok polls.
Fetch problems are recorded in the database and the script exits 0; it exits non-zero only when
the database itself can't be reached or written.
"""

from datetime import datetime, timezone

import requests

from publibike.api import MIN_SHARE_TRACKED, fetch_stations
from publibike.db import connect


def main() -> None:
    polled_at = datetime.now(timezone.utc)
    poll = {"polled_at": polled_at, "http_status": None, "n_stations": None,
            "n_tracked": None, "ok": False, "error": None}
    rows: list[dict] = []

    try:
        records = fetch_stations()
        poll["http_status"] = 200
        poll["n_stations"] = len(records)
    except requests.HTTPError as exc:
        poll["http_status"] = exc.response.status_code
        poll["error"] = f"HTTP {exc.response.status_code}"
        records = None
    except Exception as exc:  # network error, bad JSON, unexpected shape
        poll["error"] = f"{type(exc).__name__}: {exc}"[:500]
        records = None

    with connect(admin=True) as conn:
        tracked = {row[0] for row in conn.execute("select station_number from stations where tracked")}

        if records is not None:
            rows, skipped = parse_counts(records, tracked)
            poll["n_tracked"] = len(rows)
            if not tracked:
                poll["error"] = "No tracked stations; run sync_stations.py first"
            elif len(rows) < MIN_SHARE_TRACKED * len(tracked):
                poll["error"] = f"Implausible response: {len(rows)} of {len(tracked)} tracked stations"
            else:
                poll["ok"] = True
                if skipped:
                    poll["error"] = f"Skipped {skipped} malformed tracked records"

        poll_id = conn.execute(
            """
            insert into polls (polled_at, http_status, n_stations, n_tracked, ok, error)
            values (%(polled_at)s, %(http_status)s, %(n_stations)s, %(n_tracked)s, %(ok)s, %(error)s)
            returning poll_id
            """,
            poll,
        ).fetchone()[0]

        if poll["ok"]:
            state_ids = ensure_states(conn, {r["state"] for r in rows})
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    insert into station_status (station_number, poll_id, bikes, ebikes, state_id)
                    values (%s, %s, %s, %s, %s)
                    """,
                    [(r["station_number"], poll_id, r["bikes"], r["ebikes"], state_ids[r["state"]])
                     for r in rows],
                )

    status = "ok" if poll["ok"] else "NOT OK"
    print(f"Poll {poll_id} at {polled_at:%Y-%m-%d %H:%M:%S} UTC: {status}. "
          f"API stations: {poll['n_stations']}, tracked written: {len(rows) if poll['ok'] else 0}"
          f"/{len(tracked)}." + (f" {poll['error']}" if poll["error"] else ""))


def parse_counts(records: list[dict], tracked: set[int]) -> tuple[list[dict], int]:
    """Return the counts of the tracked stations in the response, and the number of malformed ones skipped."""
    rows, skipped = [], 0
    for record in records:
        try:
            number = int(record["stationNumber"])
        except (KeyError, TypeError, ValueError):
            continue
        if number not in tracked:
            continue
        try:
            rows.append({
                "station_number": number,
                "bikes": int(record["totalNonElectricalBike"]),
                "ebikes": int(record["totalElectricalBike"]),
                "state": record["mapIcon"].removesuffix(".png"),
            })
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            print(f"WARNING: skipping malformed record for station {number}: {exc!r}")
            skipped += 1
    return rows, skipped


def ensure_states(conn, names: set[str]) -> dict[str, int]:
    """Make sure every state name has a row in station_states, and return name -> state_id."""
    with conn.cursor() as cur:
        cur.executemany(
            "insert into station_states (name) values (%s) on conflict (name) do nothing",
            [(name,) for name in sorted(names)],
        )
    return dict(conn.execute("select name, state_id from station_states"))


if __name__ == "__main__":
    main()
