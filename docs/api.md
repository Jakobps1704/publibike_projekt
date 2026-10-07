# PubliBike API reference

Reference for the PubliBike data project. Compiled 2026-10-07 from the official docs and live calls.
Marked **[observed]** = seen in a live response. **[spec]** = from the docs/standard, not yet seen with real data.

---

## TL;DR

- PubliBike exposes **two public, unauthenticated, read-only sources**:
  1. **Custom REST API** (`/v1/public/...`), richer: per-vehicle ids, bike/e-bike type, e-bike battery level.
  2. **Official GBFS v2.3 feed** (`/v1/gbfs/v2/...`), standardised, licensed **CC-BY-4.0**: aggregate counts per station.
- Both are **current-state snapshots only**. No history, no trips. History must be built by polling and storing.
- Polling limit: **max once per minute** (custom API docs; GBFS `ttl` = 60 s).
- **Status 2026-10-07 ~22:00 UTC: every station endpoint returns an empty list** (both APIs). Unresolved. See "Known issues".

---

## 1. Custom REST API

- Base URL: `https://api.publibike.ch/v1`
- Docs (Swagger UI): https://api.publibike.ch/v1/static/api.html
- Raw OpenAPI spec: `https://api.publibike.ch/v1/v3/api-docs/public` → **401** [observed]. Only the rendered docs are readable.
- Auth: none documented. Calls return 200 without credentials [observed].
- Format: JSON. Names (state, type, network) are "translated", so language likely follows the `Accept-Language` header [spec, untested].
- License: docs say "Contact PubliBike AG for license information". Terms: https://www.publibike.ch/en/publibike/agb

### Endpoints

| Method + path | Purpose | Includes vehicles? | Docs guidance |
|---|---|---|---|
| `GET /public/stations` | All stations: id, position, state | No | For map markers |
| `GET /public/stations/{id}` | One station in detail | Yes | For a click on one station. 404 if not found |
| `GET /public/partner/stations` | All stations in detail | Yes | **The polling endpoint.** "Not more often than every minute" |

No query parameters on any endpoint. `{id}` is an int32 path parameter.

### Schemas

`*` = required.

**StationOverview** (array items of `/public/stations`)
| Field | Type | Notes |
|---|---|---|
| `id`* | int32 | Technical station id |
| `latitude`* | double | |
| `longitude`* | double | |
| `state`* | State | |

**StationDetails** (`/public/stations/{id}`)
StationOverview fields, plus:
| Field | Type | Notes |
|---|---|---|
| `name`* | string | Public station name |
| `address` | string | Street, without city |
| `zip` | string | |
| `city` | string | |
| `vehicles` | Vehicle[] | Vehicles **currently available** at the station |
| `network` | Network | |
| `sponsors` | Sponsor[] | |

**StationsForPartner** (`/public/partner/stations`)
`{ "stations"*: StationForPartner[] }`

**StationForPartner**
StationDetails fields, plus:
| Field | Type | Notes |
|---|---|---|
| `is_virtual_station` | boolean | GBFS meaning: no physical docks, defined by geolocation |
| `capacity` | int32 | Max bikes. Docs: "not a hard limit", for display only |

**State**
| Field | Type | Notes |
|---|---|---|
| `id`* | int32 | Enum, docs example: `{1: active, 2: inactive, ...}`. Full list undocumented |
| `name`* | string | Translated label |

**Vehicle**
| Field | Type | Notes |
|---|---|---|
| `id`* | int32 | Technical vehicle id. Stable per bike, so it can be tracked across snapshots |
| `name`* | string | Number printed on the bike |
| `ebike_battery_level` | double, 0–100 | Percent. **Missing** = not an e-bike **or** level unknown |
| `type`* | Type | |

**Type**: `id`* int32, `name`* string (translated). Id values are undocumented; presumably bike / e-bike (see GBFS `vehicle_types`).

**Network**
| Field | Type | Notes |
|---|---|---|
| `id`* | int32 | Docs label it "Technical station id", a copy-paste error. It is the network id |
| `name`* | string | Translated |
| `background_img` | string | App image URL, language-specific |
| `logo_img` | string | |
| `sponsors` | Sponsor[] | |

**Sponsor**: `id` int32, `name` string, `image` string (logo URL), `url` string. All optional.

---

## 2. GBFS v2.3 feed (official, standardised)

- Discovery: `https://api.publibike.ch/v1/gbfs/v2/gbfs.json` [observed]
- Version `2.3`, `ttl` 60 s, language `en` only [observed].
- License: **CC-BY-4.0** (per MobilityDatabase listing, `system_id` `publibike`).
- Spec: https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md

Every response has the envelope `{ "data": {...}, "last_updated": <unix s>, "ttl": 60, "version": "2.3" }`.

### Feeds published

| Feed | URL | Status 2026-10-07 |
|---|---|---|
| `system_information` | `.../v1/gbfs/v2/en/system_information` | Populated |
| `station_information` | `.../v1/gbfs/v2/en/station_information` | `stations: []`, `last_updated` fresh |
| `station_status` | `.../v1/gbfs/v2/en/station_status` | `stations: []`, **`last_updated` 2026-09-05 15:14 UTC** (stale ~1 month) |
| `vehicle_types` | `.../v1/gbfs/v2/en/vehicle_types` | Populated |

**Not published:** `free_bike_status`, `system_regions`, `system_pricing_plans`, `system_alerts`, `geofencing_zones`. So there are no per-vehicle positions and no pricing.

### `system_information` [observed]
```json
{"name":"PubliBike","system_id":"publibike","language":"en","timezone":"Europe/Zurich",
 "email":"customerservice@publibike.ch","url":"https://publibike.ch"}
```

### `vehicle_types` [observed]
| `vehicle_type_id` | `name` | `form_factor` | `propulsion_type` | `max_range_meters` | `return_constraint` |
|---|---|---|---|---|---|
| `bike` | Bike | bicycle | human | – | any_station |
| `ebike` | E-Bike | bicycle | electric_assist | 85000 | any_station |

### `station_information`, `data.stations[]` [spec, not yet seen]
Standard GBFS 2.3 fields. Expect at least: `station_id` (string), `name`, `lat`, `lon`; probably `address`, `post_code`, `capacity`, `is_virtual_station`. Ids likely match the custom API's station `id`, but this is unverified.

### `station_status`, `data.stations[]` [spec, not yet seen]
| Field | Meaning |
|---|---|
| `station_id` | Joins to `station_information` |
| `num_bikes_available` | Rentable vehicles of all types |
| `vehicle_types_available[]` | `{vehicle_type_id, count}`, i.e. split into bike / ebike |
| `num_bikes_disabled` | Optional |
| `num_docks_available` | Required for physical stations |
| `is_installed`, `is_renting`, `is_returning` | Booleans |
| `last_reported` | Unix s, when the station last reported |

---

## 3. Which source to use

| Need | Custom API | GBFS |
|---|---|---|
| Bikes / e-bikes available per station | Yes, count `vehicles` by `type` | Yes, `vehicle_types_available` |
| Station capacity, fill ratio | Yes | Yes |
| Individual bike ids (infer moves between stations) | **Yes** | No |
| E-bike battery level (rideable vs. flat) | **Yes** | No |
| Station `last_reported` (detect stale stations) | No | **Yes** |
| Clear open-data license | No (contact PubliBike) | **Yes, CC-BY-4.0** |
| Standard schema, existing tooling | No | Yes |

Current plan, once data flows: poll `/public/partner/stations` every 1–5 min, store raw JSON snapshots plus a flattened table (timestamp, station, vehicle id, type, battery). Use GBFS as a fallback and as the license-clean source.

---

## 4. Known issues and open questions

- **Empty data (2026-10-07 ~22:00 UTC).** `/public/stations` → `[]`, `/public/partner/stations` → `{"stations":[]}`, `/public/stations/1` → 404, both GBFS station feeds → `[]`. Static feeds (`system_information`, `vehicle_types`) work. Calls came from a cloud tool, not a browser. Possible causes: blocking of non-browser or non-Swiss clients, a backend outage, or a deliberate shutdown. `station_status` frozen since 2026-09-05 suggests a problem upstream, not just with our client. **Next step:** test from a normal browser on a Swiss connection.
- Fallback data sources if PubliBike's own feeds stay empty: the Swiss federal aggregator `https://sharedmobility.ch/gbfs.json` (SFOE, https://github.com/SFOE/sharedmobility, https://opentransportdata.swiss/de/dataset/sharedmobility), or the endpoints the PubliBike app calls.
- Undocumented: full `State` enum, `Type` id values, whether `capacity` counts e-bike-only slots, whether station ids are identical across both APIs, and the license for the custom API.
