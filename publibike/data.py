"""Analysis helpers: query the PubliBike database into pandas DataFrames.

    from publibike import data
    data.status("2026-10-01", "2026-10-08")

All functions use the read-only connection (ANALYSIS_DATABASE_URL). Times come back in Europe/Zurich.
Dates or times without a timezone are read as Zürich local time; `end` is exclusive.
See docs/data_access.md.
"""

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from publibike.db import REPO_ROOT, connect

TZ = "Europe/Zurich"
POLLS_PER_DAY = 24 * 12  # one poll every 5 minutes

TimeLike = str | date | datetime | pd.Timestamp | None


# --- generic ---------------------------------------------------------------------------------

def query(sql: str, params: dict | tuple | None = None) -> pd.DataFrame:
    """Run any read-only SQL and return the result. Timestamps are converted to Zürich time.

    Use %s or %(name)s placeholders for values: query("select * from v_status where poll_id = %s", (42,))
    """
    return _localize(_raw_query(sql, params))


# --- tables ------------------------------------------------------------------------------------

def stations(include_untracked: bool = False) -> pd.DataFrame:
    """Station list: number, name, address, coordinates, tracked flag, first/last seen."""
    where = "" if include_untracked else "where tracked"
    return query(f"""
        select station_number, name, address, lat, lon, tracked, first_seen, last_seen
        from stations {where} order by name
    """)


def latest() -> pd.DataFrame:
    """Counts of every tracked station at the most recent successful poll."""
    return query("""
        select * from v_status
        where poll_id = (select max(poll_id) from polls where ok)
        order by station_name
    """)


def polls(start: TimeLike = None, end: TimeLike = None) -> pd.DataFrame:
    """Collector runs (also failed ones) with the gap since the previous run."""
    start_utc, end_utc = _to_utc(start), _to_utc(end)
    return query("""
        select * from v_polls
        where (%(start)s::timestamptz is null or polled_at >= %(start)s)
          and (%(end)s::timestamptz   is null or polled_at <  %(end)s)
        order by polled_at
    """, {"start": start_utc, "end": end_utc})


def health(days: float = 1) -> pd.Series:
    """Is the collector running well? Summary of the last `days` days of polls."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    df = polls(start=since)
    now = pd.Timestamp.now(tz=TZ)
    gaps = df["gap"].dropna() if len(df) else pd.Series(dtype="timedelta64[ns]")
    return pd.Series({
        "period_days": days,
        "runs": len(df),
        "ok": int(df["ok"].sum()) if len(df) else 0,
        "failed": int((~df["ok"]).sum()) if len(df) else 0,
        "expected_runs": round(days * POLLS_PER_DAY),
        "coverage": round(df["ok"].sum() / (days * POLLS_PER_DAY), 3) if len(df) else 0.0,
        "median_gap": gaps.median() if len(gaps) else None,
        "max_gap": gaps.max() if len(gaps) else None,
        "gaps_over_10min": int((gaps > pd.Timedelta(minutes=10)).sum()),
        "last_poll": df["polled_at"].max() if len(df) else None,
        "minutes_since_last_poll": round((now - df["polled_at"].max()).total_seconds() / 60, 1) if len(df) else None,
        "last_error": df.loc[~df["ok"], "error"].iloc[-1] if len(df) and (~df["ok"]).any() else None,
    })


# --- time series -------------------------------------------------------------------------------

def status(start: TimeLike = None, end: TimeLike = None, stations: list[int] | None = None,
           cache: bool = True) -> pd.DataFrame:
    """Counts per station and poll: polled_at, station_number, station_name, bikes, ebikes, total, state.

    `start` defaults to the first poll, `end` to now. `stations` is a list of station numbers.
    Completed days are cached as Parquet files (see cache_dir()) and downloaded only once, which
    keeps us within Supabase's monthly download limit. Pass cache=False to always query the database.
    """
    end_utc = _to_utc(end) or datetime.now(timezone.utc)
    start_utc = _to_utc(start) or _first_poll()
    if start_utc is None or start_utc >= end_utc:
        return _empty_status()

    # Days (UTC) that are over, with a margin for runs still being written, can be cached for good.
    complete_before = (datetime.now(timezone.utc) - timedelta(minutes=15)).date()
    days = [start_utc.date() + timedelta(n) for n in range((end_utc.date() - start_utc.date()).days + 1)]

    frames, missing = [], []
    for day in days:
        path = _cache_file(day)
        if cache and day < complete_before and path.exists():
            frames.append(_status_dtypes(pd.read_parquet(path)))
        else:
            missing.append(day)

    for run in _contiguous(missing):
        fetched = _raw_query("""
            select polled_at, poll_id, station_number, bikes, ebikes, state
            from v_status where polled_at >= %s and polled_at < %s
        """, (_day_start(run[0]), _day_start(run[-1] + timedelta(1))))
        fetched = _status_dtypes(fetched)
        for day in run:
            part = fetched[fetched["polled_at"].dt.date == day]
            if cache and day < complete_before:
                _cache_file(day).parent.mkdir(parents=True, exist_ok=True)
                part.to_parquet(_cache_file(day), index=False)
            frames.append(part)

    df = pd.concat(frames, ignore_index=True) if frames else _empty_status()
    df = df[(df["polled_at"] >= pd.Timestamp(start_utc)) & (df["polled_at"] < pd.Timestamp(end_utc))]
    if stations is not None:
        df = df[df["station_number"].isin(stations)]

    names = _raw_query("select station_number, name as station_name from stations")
    df = df.merge(names, on="station_number", how="left")
    df["total"] = (df["bikes"] + df["ebikes"]).astype("int16")
    df["polled_at"] = df["polled_at"].dt.tz_convert(TZ)
    cols = ["polled_at", "poll_id", "station_number", "station_name", "bikes", "ebikes", "total", "state"]
    return df[cols].sort_values(["polled_at", "station_number"], ignore_index=True)


def hourly(start: TimeLike, end: TimeLike = None, stations: list[int] | None = None) -> pd.DataFrame:
    """Hourly averages per station, computed in the database (small download, no cache needed).

    Columns: hour (Zürich time), station_number, station_name, bikes, ebikes, total (means),
    min_total, share_empty (share of polls with no bike at all), n_polls.
    """
    return query("""
        select date_trunc('hour', polled_at, 'Europe/Zurich') as hour,
               station_number, station_name,
               avg(bikes)::float  as bikes,
               avg(ebikes)::float as ebikes,
               avg(total)::float  as total,
               min(total)         as min_total,
               avg((total = 0)::int)::float as share_empty,
               count(*)           as n_polls
        from v_status
        where polled_at >= %(start)s and polled_at < %(end)s
          and (%(stations)s::int[] is null or station_number = any(%(stations)s::int[]))
        group by 1, 2, 3
        order by 1, 2
    """, {"start": _to_utc(start), "end": _to_utc(end) or datetime.now(timezone.utc), "stations": stations})


# --- cache ---------------------------------------------------------------------------------------

def cache_dir() -> Path:
    """Where status() keeps its Parquet files: $PUBLIBIKE_CACHE_DIR, else data/cache in the repo
    (when working in a clone), else ./publibike_cache."""
    if os.environ.get("PUBLIBIKE_CACHE_DIR"):
        return Path(os.environ["PUBLIBIKE_CACHE_DIR"])
    if (REPO_ROOT / "collector").is_dir():
        return REPO_ROOT / "data" / "cache"
    return Path.cwd() / "publibike_cache"


def clear_cache() -> None:
    """Delete the cached status files; the next status() call downloads them again."""
    for path in cache_dir().glob("status_*.parquet"):
        path.unlink()


# --- internals -----------------------------------------------------------------------------------

def _raw_query(sql: str, params=None) -> pd.DataFrame:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        columns = [col.name for col in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=columns)


def _localize(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if isinstance(df[col].dtype, pd.DatetimeTZDtype):
            df[col] = df[col].dt.tz_convert(TZ)
    return df


def _to_utc(value: TimeLike) -> datetime | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(TZ)
    return ts.tz_convert("UTC").to_pydatetime()


def _first_poll() -> datetime | None:
    first = _raw_query("select min(polled_at) as first from polls").iloc[0, 0]
    return None if pd.isna(first) else pd.Timestamp(first).tz_convert("UTC").to_pydatetime()


def _day_start(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def _contiguous(days: list[date]) -> list[list[date]]:
    runs: list[list[date]] = []
    for day in days:
        if runs and day - runs[-1][-1] == timedelta(1):
            runs[-1].append(day)
        else:
            runs.append([day])
    return runs


def _cache_file(day: date) -> Path:
    return cache_dir() / f"status_{day.isoformat()}.parquet"


def _status_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    # One fixed resolution: pandas turns a concat of mixed resolutions (e.g. from empty Parquet files) into object.
    df["polled_at"] = pd.to_datetime(df["polled_at"], utc=True).dt.as_unit("us")
    return df.astype({"poll_id": "int64", "station_number": "int32", "bikes": "int16",
                      "ebikes": "int16", "state": "string"})


def _empty_status() -> pd.DataFrame:
    empty = pd.DataFrame({"polled_at": pd.Series(dtype="datetime64[ns, UTC]"), "poll_id": [],
                          "station_number": [], "bikes": [], "ebikes": [], "state": []})
    return _status_dtypes(empty)
