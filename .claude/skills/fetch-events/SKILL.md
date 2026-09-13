---
name: fetch-events
description: Fetch Planetary Qualifier, Sector Qualifier, and Regional Qualifier (Regional Championship) events from swu-competitivehub.com for given dates and create YAML event files. Use when the user asks to fetch, import, download, or add PQ/SQ/RQ events for specific dates (e.g. "fetch events for 20260411 20260412").
argument-hint: <DATE> [DATE ...] (e.g. 20260411, 20260412)
allowed-tools: Bash Read Write Glob Grep
---

# Fetch Planetary/Sector Qualifier Events

Download Planetary Qualifier and Sector Qualifier tournament data from swu-competitivehub.com for the given dates and create YAML event files in the database.

## Input

Date(s): $ARGUMENTS

Dates must be in YYYYMMDD format (e.g. 20260411 20260412). Multiple dates can be provided separated by spaces.

## Instructions

1. Run the Python script below via Bash, passing the dates as arguments.
2. Review the output: check which events were created or skipped (already existing).
3. Check the city of every created event against the grouping rule below, and
   fix any that are wrong (both the `city` and the `name` field, and rename the
   file so its slug matches).
4. Report how many events were created and list them.

## Script

```bash
python3 ${CLAUDE_SKILL_DIR}/fetch_events.py $ARGUMENTS
```

## City grouping rule

An event is filed under the nearest larger or better-known city, not the small
town the venue happens to sit in — a PQ at a shop in Wasquehal is
`Planetary Qualifier Lille`, not `Planetary Qualifier Wasquehal`.

The script does not do this: it writes the city exactly as the site prints it
(minus any trailing US/Canadian state code, which it does strip). Applying the
rule is your job, on every event the run creates.

For each created event, ask whether someone outside the region would place the
city on a map. If not, find the nearest major city and rewrite three things:

- the `city` field,
- the `name` field, which repeats the city,
- the filename, whose slug must match the new city.

Ignore what the database already contains. Older events were not always grouped
this way, so a town appearing there as its own city is not a precedent — and
neither is a large city's absence a reason to keep the town.

Known cases, as illustration of the intended granularity:

| Venue town | Filed under |
|---|---|
| Bothell, USA | Seattle |
| Beaverton, USA | Portland |
| Newington, USA | Hartford |
| Ridgeway, Canada | Niagara Falls |
| Abbiategrasso, Italy | Milan |
| Nerviano, Italy | Milan |
| Portici, Italy | Naples |
| Appingedam, Netherlands | Groningen |
| Arona, Spain | Santa Cruz de Tenerife |
| Aubagne, France | Marseille |
| Wasquehal, France | Lille |

Cities that already stand on their own — Lima, Osnabrück, Tampere, Indianapolis
— are left alone.
