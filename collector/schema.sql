-- Database schema. Idempotent: safe to run again via `python collector/setup_db.py`.
-- All timestamps are UTC (timestamptz). Source: rest.publibike.ch/v1/public/all/stations (docs/api.md §3b).

-- One row per collector run, including failed or implausible ones,
-- so gaps in station_status can be told apart from "no data".
create table if not exists polls (
    poll_id       bigint generated always as identity primary key,
    polled_at     timestamptz not null,        -- actual run time, not the scheduled one
    http_status   smallint,
    n_stations    smallint,                    -- stations in the API response
    n_tracked     smallint,                    -- tracked stations found and written
    ok            boolean not null,            -- false = error or implausible response; no status rows written
    error         text
);

-- Stations we care about (Zürich). The collector only writes status for rows with tracked = true.
-- Maintained by collector/sync_stations.py, not by the collector.
create table if not exists stations (
    station_number integer primary key,        -- API stationNumber
    velospot_id    text not null,              -- API station_id (opaque), needed for the per-station details URL
    name           text not null,
    address        text,
    lat            double precision not null,
    lon            double precision not null,
    tracked        boolean not null default true,
    first_seen     timestamptz not null default now(),
    last_seen      timestamptz not null default now()  -- last time the sync saw it in the API
);

-- Station states, from the API's mapIcon without ".png" (e.g. stationAvailableWithBike, stationOutOfOrder).
create table if not exists station_states (
    state_id       smallint generated always as identity primary key,
    name           text not null unique
);

-- Counts per tracked station, one row every ok poll.
create table if not exists station_status (
    station_number integer  not null references stations,
    poll_id        bigint   not null references polls,
    bikes          smallint not null,           -- totalNonElectricalBike
    ebikes         smallint not null,           -- totalElectricalBike
    state_id       smallint not null references station_states,
    primary key (station_number, poll_id)
);

-- Supabase exposes the public schema via its REST API. RLS with no policies blocks that;
-- our scripts connect to Postgres directly and are not affected.
alter table polls          enable row level security;
alter table stations       enable row level security;
alter table station_states enable row level security;
alter table station_status enable row level security;

-- Views for analysis. security_invoker makes them respect the caller's RLS; without it a view runs
-- as its owner and would expose the tables through Supabase's REST API.

-- One row per station and ok poll, with names instead of ids.
create or replace view v_status with (security_invoker = true) as
select p.polled_at,
       ss.poll_id,
       ss.station_number,
       s.name               as station_name,
       ss.bikes,
       ss.ebikes,
       ss.bikes + ss.ebikes as total,
       st.name              as state
from station_status ss
join polls          p  using (poll_id)
join stations       s  using (station_number)
join station_states st using (state_id);

-- Every collector run, with the time since the previous run (gaps = skipped or delayed runs).
create or replace view v_polls with (security_invoker = true) as
select poll_id, polled_at, ok, http_status, n_stations, n_tracked, error,
       polled_at - lag(polled_at) over (order by polled_at) as gap
from polls;
