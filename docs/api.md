# PubliBike API reference

Reference for the PubliBike data project. Compiled 2026-10-07 from the official docs and live calls, updated 2026-10-08.
Marked **[observed]** = seen in a live response. **[spec]** = from the docs/standard, not yet seen with real data.

---

## TL;DR

- **The only source with data right now (2026-10-08) is `https://rest.publibike.ch/v1/public/all/stations`** (section 3b). Its station data is under the `velospot` key; the `publibike` key is empty.
- The documented sources are public, unauthenticated, read-only, and **return empty station lists**:
  1. **Custom REST API** (`/v1/public/...`), richer: per-vehicle ids, bike/e-bike type, e-bike battery level.
  2. **Official GBFS v2.3 feed** (`/v1/gbfs/v2/...`), standardised, licensed **CC-BY-4.0**: aggregate counts per station.
- All sources are **current-state snapshots only**. No history, no trips. History must be built by polling and storing.
- Polling limit: **max once per minute** (custom API docs; GBFS `ttl` = 60 s). Nothing is documented for the `all/stations` endpoint, so we assume the same limit.

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
| `station_status` | `.../v1/gbfs/v2/en/station_status` | `stations: []`. `last_updated` was frozen at 2026-09-05; fresh again on 2026-10-08, but still empty |
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

| Need | Custom API | GBFS | `all/stations` (3b) |
|---|---|---|---|
| **Returns data today** | No | No | **Yes** |
| Bikes / e-bikes available per station | Yes, count `vehicles` by `type` | Yes, `vehicle_types_available` | **Yes**, `totalNonElectricalBike` / `totalElectricalBike` in one call |
| Station capacity, fill ratio | Yes | Yes | No capacity field |
| Individual bike ids (infer moves between stations) | **Yes** | No | Only via one HTML call per station |
| E-bike battery level (rideable vs. flat) | **Yes** (exact %) | No | Only via the HTML call, as a km-range bucket |
| Station `last_reported` (detect stale stations) | No | **Yes** | No (only `mapIcon` out-of-order status) |
| Clear open-data license | No (contact PubliBike) | **Yes, CC-BY-4.0** | No (undocumented) |
| Standard schema, existing tooling | No | Yes | No |

Current plan: poll every 5 min and store **station counts only**. Per-vehicle tracking is deferred (see `docs/decisions.md`). Of the three sources, only `all/stations` delivers counts right now, so it's the practical candidate. The choice isn't logged in `decisions.md` yet. The vehicle ids and battery levels above are the reason to come back to the custom API later.

---

## 3b. Combined PubliBike + Velospot endpoint [observed 2026-10-08]

- `GET https://rest.publibike.ch/v1/public/all/stations`: 200, about 1.27 MB, no auth.
- Shape: `{ "publibike": {"stations": []}, "velospot": {"responseData": [...], "responseStatus": {...}, "extraData": {...}} }`.
- `publibike.stations` is **empty**. All data is under `velospot.responseData`: **1687 stations, one network** (`encryptNetworkId` `a0plWVF5a3k2T2RuNWs2LzhYMTd3Zz09`), including about 253 in Zürich (e.g. Albisriederplatz). This suggests the PubliBike stations now run on the Velospot backend (unverified).
- Station fields: `station_name`, `station_address`, `encryptNetworkId`, `station_id` (base64-encoded, opaque), `stationNumber` (e.g. "600654"), `lat`/`lng` (strings), `totalBike`, `totalNonElectricalBike`, `totalElectricalBike`, `totalCargoBike`, `totalEscooter`, `totalGlider`, `mapIcon`, `mapIconFullpath`, `stationColor`, `detailsRoute`.
- `mapIcon` acts as a status: `stationAvailableWithBike`, `…NoBike`, `…WithBikeMixed`, `…NoBikeMixed`, `stationOutOfOrder`, `…WithBikeTrain`, `…NoBikeTrain`, `stationIsVelostation`.
- Per-station bikes: `detailsRoute` = `https://www.velospot.info/customer/public/getStationInfo/{encryptNetworkId}/{station_id}`. It returns `{"renderHtml": "..."}`: an HTML fragment listing each bike's ID (e.g. `001722e`; the suffix `e` means e-bike and `m` means a regular bike, which has an empty range cell) and its range as a "Km-Potenzial" bucket (e.g. `56-60 km`). The fragment has to be parsed as HTML. No exact battery %.
- Zürich [observed 2026-10-08]:
  - **293** station names end in `- Zürich`. This includes agglomeration stations such as `Bahnhof Kloten - Zürich` and `… - Urdorf - Zürich`, so the suffix marks the Zürich region, not the city.
  - **250** have "Zürich" in `station_address`. All 250 also have the name suffix.
  - All Zürich stations have a `stationNumber` in 490061–492001.
  - Zürich has no cargo bikes, e-scooters or gliders.
  - `totalBike` = `totalNonElectricalBike` + `totalElectricalBike`.
  - `stationNumber` and `station_id` are both unique across all 1687 stations. Both are strings; `stationNumber` is numeric.
- Snapshot 2026-10-08: 8267 vehicles (5619 e-bikes, 2501 bikes, 147 e-scooters), 214 stations with 0 bikes, 29 out of order.

## 4. Known issues and open questions

- **Documented endpoints are empty.** First seen 2026-10-07 ~22:00 UTC from a cloud tool: `/public/stations` → `[]`, `/public/partner/stations` → `{"stations":[]}`, `/public/stations/1` → 404, both GBFS station feeds → `[]`. Static feeds (`system_information`, `vehicle_types`) work. **Rechecked 2026-10-08 from the user's local machine with curl: still empty**, including `rest.publibike.ch/v1/public/stations`. So the client isn't being blocked. The likely explanation is the move to the Velospot backend (3b), and the old endpoints may never come back. GBFS `station_status` `last_updated` is fresh again (2026-10-07 ~23:14 UTC; earlier it was frozen at 2026-09-05), but the list is still empty.
- Fallback if `all/stations` disappears: the Swiss federal aggregator `https://sharedmobility.ch/gbfs.json` (SFOE, https://github.com/SFOE/sharedmobility, https://opentransportdata.swiss/de/dataset/sharedmobility). Not yet checked whether it carries the PubliBike/Velospot stations.
- `all/stations` open questions:
  - Rate limit and license.
  - Whether `station_id` / `stationNumber` stay the same over time. We key on `stationNumber`, and the daily sync logs a warning if a station's `station_id` changes.
  - The meaning of `Mixed`/`Train` in `mapIcon`.
- Undocumented (custom API): full `State` enum, `Type` id values, whether `capacity` counts e-bike-only slots, whether station ids are identical across both APIs, and the license.
