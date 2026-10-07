# PubliBike Zurich — data project

A personal project for collecting and analysing PubliBike bike-sharing data in Zurich. Two motivations:
1. Understand (and maybe predict or improve) why stations are often empty when I need a bike.
2. Learn applied data analysis on a real, messy dataset.

The scope is **deliberately open**. Don't narrow it, or build toward one specific question or product, unless I ask for that.

## Status
<!-- Claude: keep this block current. Rewrite it; don't append. Max ~10 lines. -->
_Last updated: 2026-10-08_

- **Built:** nothing yet. The repo has only context files.
- **Blocked:** all PubliBike station endpoints return empty lists (custom API and GBFS). GBFS `station_status` has been frozen since 2026-09-05. Not yet checked from a normal browser on a Swiss connection. See `docs/api.md` → Known issues.
- **Next:** confirm whether data is available → build the collector.

## Where things are

| Path | What |
|---|---|
| `CLAUDE.md` | This file: entry point, status, rules |
| `docs/api.md` | PubliBike API + GBFS reference. Read before touching the collector |
| `docs/decisions.md` | Current decisions and why. Read before proposing anything structural |
| `docs/findings.md` | What the data has shown so far (create it when the first finding exists) |
| `collector/` | Polling + storage code (planned) |
| `analysis/` | Notebooks/scripts, one per question, numbered `01_…` (planned) |
| `data/` | Local data. **Gitignored, never commit** |

## Conventions

- **Python only**, for all code: collector, analysis, utilities. Use Python ≥ 3.11 and declare dependencies in `pyproject.toml`.
- Store all timestamps in **UTC**. Convert to `Europe/Zurich` only for analysis and display.
- Secrets (DB URLs, keys) go in environment variables or a gitignored `.env`, never in code.
- Keep things simple and replaceable. Prefer a small script over a framework until the need is real.
- Respect the API: poll no more often than the interval in `docs/decisions.md`, and identify politely (a descriptive User-Agent).

## Keeping the context current

This repo is the project's memory, and later sessions only know what is written here. Before finishing any task that changed something:

1. **Status:** update the Status block above if what's built, blocked, or next has changed. Update the date.
2. **Decisions:** when a choice is made or changed (tooling, schema, interval, data source, scope), update `docs/decisions.md` in place. It holds the current state, not a log. Keep entries short.
3. **Findings:** when analysis shows something about the data, add it to `docs/findings.md`, with the date, a one-line claim, and the notebook or script it came from.
4. **API knowledge:** when you learn something new about the endpoints (an undocumented field, an enum value, an outage, a behaviour change), update `docs/api.md` and move the item from [spec] to [observed] where applicable.
5. **Layout:** if you add or remove a top-level folder or key file, update the table above.
6. **Don't decide silently.** If a task needs a significant choice that isn't in `docs/decisions.md`, ask me. If I'm not around, make the choice, log it as `tentative`, and mention it in your reply.
7. Keep this file short (under ~100 lines). Put detail in `docs/` and link to it from here.
8. Commit context updates in the same commit as the code they describe.
