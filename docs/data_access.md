# Data access

How to query the PubliBike Zürich database: with the Python helpers (easiest) or with plain SQL.

## What's in the database

A collector polls PubliBike every 5 minutes and stores the number of bikes and e-bikes at every station in the Zürich region (293 stations: every station whose name contains "Zürich", including the agglomeration). Collection started on 2026-10-08.

| Table / view | One row per | Columns |
|---|---|---|
| `v_status` (view) | station × successful poll | `polled_at`, `poll_id`, `station_number`, `station_name`, `bikes`, `ebikes`, `total`, `state` |
| `v_polls` (view) | collector run, also failed ones | `poll_id`, `polled_at`, `ok`, `http_status`, `n_stations`, `n_tracked`, `error`, `gap` (time since the previous run) |
| `stations` | station | `station_number`, `name`, `address`, `lat`, `lon`, `tracked`, `first_seen`, `last_seen` |
| `station_status`, `polls`, `station_states` | | The raw tables behind the views. Prefer the views. |

Things to know:
- **Time:** the database stores UTC. The Python helpers return Europe/Zurich time.
- **Gaps:** polls run on GitHub Actions, which often delays or skips runs. Check `v_polls.gap` or `data.health()` before assuming a regular 5-minute grid.
- **Failed polls** (API down, implausible response) appear in `v_polls` with `ok = false` and have no rows in `v_status`.
- **`bikes`** are regular bikes, **`ebikes`** are e-bikes. `total = bikes + ebikes`. E-bikes with a flat battery are still counted.
- **`state`** comes from the map icon of the PubliBike app: `stationAvailableWithBike`, `stationAvailableNoBike`, `stationOutOfOrder`, and others.
- The data source is an undocumented PubliBike/Velospot endpoint without a stated license. Ask before publishing derived data.

## Getting access

You need a **read-only connection string**. Ask Jakob for it. Keep it private: don't commit it, and don't paste it into issues or public notebooks. It can only read, and every query is stopped after 60 seconds.

Put it in a file named `.env` in the folder you work in (or a parent folder):

```
ANALYSIS_DATABASE_URL=postgresql://publibike_reader.<project>:<password>@<host>:5432/postgres
```

## Python

### Install

Python 3.11 or newer:

```bash
pip install "publibike[analysis] @ git+https://github.com/Jakobps1704/publibike_projekt.git"
```

When working in a clone of the repo, use `pip install -e ".[analysis]"` instead.

### Quickstart

```python
from publibike import data

data.health()                                     # is the collector running? coverage, gaps, last poll
data.stations()                                   # the 293 tracked stations
data.latest()                                     # current counts at every station

df = data.status("2026-10-08", "2026-10-15")      # every poll in that week (Zürich time, end exclusive)
df = data.status("2026-10-08", stations=[490061, 490307])

hourly = data.hourly("2026-10-08")                # hourly means per station, computed in the database
hourly.groupby(hourly["hour"].dt.hour)["share_empty"].mean()   # how often stations are empty, by hour of day

data.query("select station_name, min(total) from v_status group by 1")   # any SQL
```

### Functions

All return pandas DataFrames. Dates or times without a timezone are read as Zürich time.

| Function | Returns |
|---|---|
| `status(start=None, end=None, stations=None, cache=True)` | One row per station and poll. Defaults to everything since collection started. |
| `hourly(start, end=None, stations=None)` | Hourly mean `bikes` / `ebikes` / `total`, `min_total`, `share_empty` (share of polls with no bike at all), `n_polls` |
| `latest()` | Counts at the most recent successful poll |
| `stations(include_untracked=False)` | Station metadata |
| `polls(start=None, end=None)` | Collector runs, including failed ones, with `gap` |
| `health(days=1)` | Summary: runs, failures, coverage, largest gap, minutes since the last poll |
| `query(sql, params=None)` | Any read-only SQL; use `%s` placeholders for values |
| `cache_dir()`, `clear_cache()` | Where `status()` caches downloaded days, and how to reset it |

### Download limits and the cache

The database runs on Supabase's free tier, which allows **5 GB of downloads per month for everyone together**. One full download of `station_status` grows by about 6 MB per day of collection.

- `status()` saves every finished day as a Parquet file and downloads it only once. Later calls read the files. The cache is `data/cache/` in a repo clone, otherwise `./publibike_cache/`, or wherever `PUBLIBIKE_CACHE_DIR` points.
- For aggregates (averages per hour or per station), use `hourly()` or `query()` with `group by`. The database computes them and sends back only the result.
- Avoid `query("select * from v_status")` in loops or notebooks that you re-run often.

## SQL clients

The same connection string works in any Postgres client, such as DBeaver, TablePlus, `psql` or Excel/Power BI via ODBC. Query the views:

```sql
select date_trunc('hour', polled_at, 'Europe/Zurich') as hour,
       avg(total) as avg_bikes
from v_status
where station_name = 'Albisriederplatz - Zürich'
group by 1 order by 1;
```

## For the maintainer

- The read-only user is `publibike_reader`. `python collector/create_reader.py` creates it and writes `ANALYSIS_DATABASE_URL` to `.env`. Use `--rotate` for a new password, e.g. if the string leaked. The old string stops working at once.
- New tables and views get read access automatically. New tables also need an RLS policy: re-run `create_reader.py` after adding one to `create_reader.TABLES`.
