# Decisions

The current decisions, with short reasons. This file holds the **current state** of each decision, not a history.

**How Claude maintains this file**
- **Changed decision:** edit the entry in place. If the old choice is worth remembering, add a short "previously X, because Y" note.
- **Dropped decision:** delete the entry.
- **New decision:** add it under the right section.
- Keep each entry to 1–3 lines. Put detail in other docs and link to it. Git history keeps the rest.
- **Status tags:** none = decided. `(tentative)` = Claude chose it, or it is only probable; confirm before building heavily on it. `(open)` = undecided; list the options briefly.

---

## Scope
- **Python only**, for all code.
- **General and open.** Support many tests and observations, not one fixed question. Collect broadly enough for future questions, but don't build analysis infrastructure ahead of need.

## Data collection
- **Poll every 5 min.** Gentler on the API and on storage than the 1-minute minimum. Limitation: anything that happens within one 5-minute window is missed, such as a bike taken and returned between two polls.
- **Track station counts only:** bikes, e-bikes and state per station over time.
- **Vehicle tracking deferred** (decided 2026-10-08). The per-bike event log (*appeared* / *left* by vehicle id, with battery) is postponed so the first version stays simple. It can be added later from the custom API, but no vehicle history will exist from before then.
- **Schema:** `polls` (every run, including failed ones), `stations`, `station_status` and `station_states`. See `collector/schema.sql`.
- **A `station_status` row every poll** for now. It is simpler to query than change-only, but fills the 500 MB in roughly 3 months, so switch to change-only or aggregate before then.
- **Source: `rest.publibike.ch/v1/public/all/stations`**, `velospot` key. It is the only endpoint with data. Previously the documented custom API `/public/partner/stations`, which now returns empty lists. See `docs/api.md` §3b.
- **Station key: `stationNumber`** as an integer (`stations.station_number`). The opaque `station_id` is stored as `velospot_id`, because the per-station details URL needs it. Whether the key stays stable is unverified, so the sync logs any `velospot_id` change.
- **Zurich only, via the `stations` table.** Tracked stations are the rows with `tracked = true`, and the collector ignores every other station in the response.
  - **Rule:** the station name contains "Zürich" (case-insensitive). This is simpler than a geographic boundary. It matches 293 stations, including the agglomeration (see `docs/api.md` §3b).
  - **`collector/sync_stations.py`** maintains the list, daily on GitHub Actions (03:17 UTC) plus manual runs:
    - It inserts new matches and updates metadata and `last_seen` in place, with no history.
    - It sets `tracked = false` for stations that no longer match or are missing from the API, and back to `true` when they return. It never deletes rows.
    - It changes nothing if the response looks like an outage: no matches, or under 80% of the currently tracked stations.
  - The sync must run before the collector's first run.
- **Schema setup via Python** `(tentative)` (`collector/setup_db.py` with `DATABASE_URL`), not the Supabase CLI or connector. It uses the same connection the collector needs, with no extra tooling.

## Infrastructure
- **Storage: Supabase free tier (Postgres).** Limits:
  - 500 MB database per project. This is the binding limit. Station counts take about 5–6 MB/day, so archive or aggregate before the limit is reached.
  - 5 GB egress (+ 5 GB cached egress) per month.
  - Max 2 active projects.
  - The project **pauses after 1 week of inactivity**. Regular collector writes prevent this, but a stalled collector for 7 days means pausing.
- **Collector runs on GitHub Actions cron (`*/5 * * * *`).**
  - Runs are often delayed or skipped, so always store each run's actual timestamp rather than the scheduled one.
  - Supabase credentials go in GitHub Actions secrets.
  - The repo should be **public**. A private repo gets 2,000 free minutes/month, and 5-minute polling uses about 8,600 runs at 1 billed minute each.
  - In a public repo, scheduled workflows are disabled after 60 days without repo activity, so the collector needs a keep-alive or a periodic commit.
