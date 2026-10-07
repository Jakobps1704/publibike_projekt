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
- **Store station counts and a bike event log.**
  - Counts: one row per station per poll, with bikes, e-bikes, capacity and state.
  - Events: compare vehicle ids between consecutive polls and log *appeared* / *left* with the vehicle id, type, battery and station.
  - The exact schema is `(open)`.
- **Source: PubliBike custom API `/public/partner/stations`** `(tentative)`. It is the only source with vehicle ids and battery levels, which the events need. GBFS has counts only but is CC-BY-4.0. See `docs/api.md`.

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
