"""Keep the stations table in line with the API. Runs once a day (and manually).

- Stations whose name contains "Zürich" are inserted or updated and tracked.
- Known stations that no longer match, or are missing from the API, are set to tracked = false.
  Rows are never deleted, because station_status rows reference them.
- If the response looks like an outage (no matches, or far fewer than currently tracked),
  nothing is changed and the script exits with an error.
"""

from publibike.api import MIN_SHARE_TRACKED, fetch_stations, is_zurich, parse_station
from publibike.db import connect

FIELDS = ("velospot_id", "name", "address", "lat", "lon")
COORD_TOLERANCE = 1e-6  # degrees, ~10 cm


def main() -> None:
    records = fetch_stations()

    with connect(admin=True) as conn:
        existing = {
            row[0]: dict(zip(("tracked", *FIELDS), row[1:]))
            for row in conn.execute(
                "select station_number, tracked, velospot_id, name, address, lat, lon from stations"
            )
        }

        # Matching stations, plus known stations that are still in the API (to refresh last_seen).
        seen: dict[int, dict] = {}
        for record in records:
            if not (is_zurich(record) or _number(record) in existing):
                continue
            try:
                station = parse_station(record)
            except (KeyError, TypeError, ValueError) as exc:
                print(f"WARNING: skipping malformed record {record.get('stationNumber')!r}: {exc!r}")
                continue
            station["tracked"] = is_zurich(record)
            seen[station["station_number"]] = station

        n_tracked_before = sum(s["tracked"] for s in existing.values())
        n_tracked_after = sum(s["tracked"] for s in seen.values())
        if n_tracked_after == 0 or n_tracked_after < MIN_SHARE_TRACKED * n_tracked_before:
            raise SystemExit(
                f"Implausible response: {len(records)} stations, {n_tracked_after} match "
                f"(currently tracked: {n_tracked_before}). No changes made."
            )

        new, changed, retracked, untracked = [], [], [], []
        for num, station in seen.items():
            old = existing.get(num)
            if old is None:
                new.append(num)
                continue
            if old["velospot_id"] != station["velospot_id"]:
                # Tells us over time whether stationNumber is a stable key (docs/api.md §4).
                print(f"WARNING: station {num} changed velospot_id "
                      f"{old['velospot_id']} -> {station['velospot_id']}")
            diff = [f for f in FIELDS if _differs(f, old[f], station[f])]
            if diff:
                changed.append((num, diff))
            if station["tracked"] and not old["tracked"]:
                retracked.append(num)
            elif old["tracked"] and not station["tracked"]:
                untracked.append(num)

        missing = [num for num, old in existing.items() if old["tracked"] and num not in seen]
        untracked += missing

        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into stations (station_number, velospot_id, name, address, lat, lon, tracked)
                values (%(station_number)s, %(velospot_id)s, %(name)s, %(address)s, %(lat)s, %(lon)s, %(tracked)s)
                on conflict (station_number) do update set
                    velospot_id = excluded.velospot_id,
                    name        = excluded.name,
                    address     = excluded.address,
                    lat         = excluded.lat,
                    lon         = excluded.lon,
                    tracked     = excluded.tracked,
                    last_seen   = now()
                """,
                list(seen.values()),
            )
            if missing:
                cur.execute(
                    "update stations set tracked = false where station_number = any(%s)",
                    (missing,),
                )

    print(f"API: {len(records)} stations. Tracked: {n_tracked_before} -> {n_tracked_after}.")
    print(f"New: {len(new)}, changed: {len(changed)}, re-tracked: {len(retracked)}, "
          f"untracked: {len(untracked)} (missing from API: {len(missing)}).")
    for num, diff in changed:
        print(f"  changed {num}: {', '.join(diff)}")
    for label, nums in (("re-tracked", retracked), ("untracked", untracked)):
        if nums:
            print(f"  {label}: {', '.join(map(str, sorted(nums)))}")


def _differs(field: str, old, new) -> bool:
    if field in ("lat", "lon"):
        # Floats read back through the pooler are rounded; ignore anything below ~10 cm.
        return abs(old - new) > COORD_TOLERANCE
    return old != new


def _number(record: dict) -> int | None:
    try:
        return int(record["stationNumber"])
    except (KeyError, TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
