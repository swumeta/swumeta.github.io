---
name: lock-events
description: Determine whether an event's results are known and add `locked: true` to its YAML file. Use when the user asks to lock events, mark results as known/final, or asks whether an event's results are complete (e.g. "lock the 2026-09-05 events", "add locked to events with a known result").
argument-hint: <DATE_PATTERN> (e.g. 20260905, 202609, "20260905 20260906") [--dry-run]
allowed-tools: Bash Read Glob Grep
---

# Lock Events With Known Results

Mark event YAML files as final by adding `locked: true`, once their results are
known.

## Input

Date pattern(s): $ARGUMENTS

Patterns are filename prefixes under `database/events/`:

- A full date: `20260905`
- A year-month prefix: `202609`
- Multiple patterns separated by spaces: `20260905 20260906`
- `--dry-run` reports what would change without writing

## The rule — when are results "known"?

**An event's results are known when every rank from 1 to 8 has a decklist
URL.** Nothing else counts.

```yaml
decks:
- rank: 1
  url: "https://melee.gg/Decklist/View/..."   # ← a decklist URL is required
- rank: 2
  url: "https://melee.gg/Decklist/View/..."
# ... through rank 8
```

Traps that have caused wrong locks before:

- **A `- rank:` entry with no `url:` is not a result.** Some events get a full
  standings list (ranks 1..N) with zero decklists attached. Counting rank
  entries instead of decklist URLs will lock events that have no results at
  all. Always check for `url:`.
- **`players: 0` means no result has been published**, even if the event
  already has a page on swu-competitivehub.com. Never lock these.
- Missing decklists below rank 8 are irrelevant — only the top 8 matters.
- For an event with fewer than 8 players, the whole field must have decklists.

Decklists are **not** written by the `fetch-events` skill. They are added by
the GitHub Actions "Build website" job, which commits them back as
*Generated site content*. So the usual sequence is: fetch events → let the
workflow run → `git pull -r` → lock.

## When the build finds no decklists

The build reads decklists from melee.gg. Some organisers never publish them
there, which leaves a bare `- rank:` list. **swu-competitivehub.com often has
the top 8 anyway** — its results table links straight to the melee decklists.
When an event is stuck without decklists, check the hub page before assuming
the result is unknown:

```
https://www.swu-competitivehub.com/event/<event-slug>/
```

Scrape the `<tr>` rows of the *Results* table: the first `<td>` is the rank and
the row's `href` is the decklist URL. Insert a `url:` line under the matching
`- rank:` entries, verify the URLs return HTTP 200, then lock the event — the
`locked: true` flag is what stops the build from overwriting the file.

## Judgment call: a partial top 8

An event where a single top-8 player never submitted a decklist (e.g. rank 8
missing) fails the strict rule, but the repository contains ~32 locked events
in exactly that state. The script leaves them unlocked and reports them.
**Ask the user before locking those** — do not decide silently.

## Never unlock

The script only ever adds `locked: true`. Removing the flag is a manual
decision: a locked event is a deliberate statement that the data is final.

## Instructions

1. Run the script below via Bash.
2. Review the output: locked events, skipped events with their reason, and any
   warning about already-locked events with an incomplete top 8.
3. Report which events were locked and which were skipped, with the reason.
4. If any event was skipped only because of a partial top 8, ask the user
   whether to lock it anyway.

## Script

```bash
python3 ${CLAUDE_SKILL_DIR}/lock_events.py $ARGUMENTS
```
