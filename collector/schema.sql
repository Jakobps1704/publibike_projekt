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
