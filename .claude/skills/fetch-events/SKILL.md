---
name: fetch-events
description: Fetch Planetary Qualifier, Sector Qualifier, and Regional Qualifier (Regional Championship) events from swu-competitivehub.com for given dates and create YAML event files. Use when the user asks to fetch, import, download, or add PQ/SQ/RQ events for specific dates (e.g. "fetch events for 20260411 20260412"). Also use when the user explicitly asks to fill in the top 8 of an event whose decklists were never published on melee.gg.
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
| Wasquehal, France | Lille |

Cities that already stand on their own — Lima, Osnabrück, Tampere, Indianapolis,
Aubagne — are left alone.

## Filling in a top 8 melee never published — on explicit request only

Some organisers never upload decklists to melee.gg. The build then leaves the
event with a bare `- rank:` list, no decklist ever arrives, and the event can
never be locked. The hub's *Results* table still carries the top 8 as player
plus leader/base, which the database records with the `player` / `leader` /
`base` form instead of a `url:` — see `20250614-pq-strasbourg.yaml`.

**Run this only when the user explicitly asks for it.** It is not part of
fetching events, and not something to do on your own initiative to "finish" an
event: decklists are added by the *Build website* job hours to days after the
event, so a fresh event with no decklists is waiting for the build, not
missing its results. Backfilling it early writes leader/base entries where the
build would have written real decklist URLs.

```bash
python3 ${CLAUDE_SKILL_DIR}/fetch_results.py <event.yaml|date-prefix> [--conventional-bases] [--dry-run]
```

The script finds the hub page by the event's melee id — falling back to the date
plus the city in the slug for the few events that carry no melee link, and
saying so in its report — and fills ranks 1 to 8 only. It fills a rank that
holds nothing (an empty entry, `url: null`, or no entry at all, which it
inserts in rank order), never one that already carries a result, and refuses an
event whose top 8 is already complete. Where the hub links the melee decklist
the build never saw, it records that `url:` rather than leader/base.

A rank the hub prints as "Unknow Leader" is left empty: a player name alone is
not a result. An unknown field is left out of the entry entirely — never
written as `null`.

It refuses an event outright when the hub's ranking disagrees with the
database's: where both name a decklist for a rank they must name the same one,
and a decklist the hub places in the top 8 must not already sit at another rank
in the file. Melee and the hub break ties differently often enough that a row
copied across a disagreement lands on the wrong player.

`--conventional-bases` answers the bare-colour question below with the code the
database already uses for that aspect — SOR-020, SOR-023, SOR-026, SOR-029, and
LOF-020, LOF-023, LOF-026, LOF-029 for a "{colour} Force". Without the flag a
bare colour stays a question for the user.

### What it will not decide for you

Each `NEEDS A DECISION` line is a card the script would have had to guess at.
**Ask the user; never pick one yourself.**

| Line | What it means |
|---|---|
| `the site only prints a generic "Blue" base` | The organiser recorded the aspect, not the card. The script lists the interchangeable candidates — the site groups every plain common base of that aspect under the one colour, so the choice changes the database, not the site's numbers. LOF's and LAW's commons are left out: LOF's render as "Blue Force", LAW's carry an ability and 27 HP. The pick is still the user's. |
| `no leader named 'X' in the card database` | The set is missing from `database/cards/` — fetch it first with the `fetch-cards` skill. |
| `'X' is ambiguous (JTL-021, LOF-012)` | Same card name in several sets and the page gave no set hint. |

Fill the missing field in by hand once the user answers.

### Locking

An event that gains a leader/base entry is locked by the script itself. Nothing
will ever add a decklist to such a rank, and the *Build website* job merges into
whatever it finds, so leaving it unlocked invites the build to write over the
hub's result. `lock-events` would never do it: that script counts decklist URLs
and reports a leader/base top 8 as incomplete.
