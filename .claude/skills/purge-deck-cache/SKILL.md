---
name: purge-deck-cache
description: Delete cached deck files for decks referenced in events. Use when the user asks to purge, clear, delete, or remove deck cache for specific events, dates, or date ranges (e.g. "March 2026", "20260329", "all april events").
argument-hint: <DATE_PATTERN> (e.g. 202603, 20260329, "202603 202604")
allowed-tools: Bash Read Glob Grep
---

# Purge Deck Cache

Delete cached deck files corresponding to decks referenced in event files matching the given date pattern(s).

## Input

Date pattern(s): $ARGUMENTS

Patterns can be:
- A full date: `20260329` (matches events on that date)
- A year-month prefix: `202603` (matches all events in March 2026)
- Multiple patterns separated by spaces: `202603 202604`

## Instructions

1. Run the Python script below via Bash, passing the date patterns as arguments.
2. Report the results: how many events matched, how many cache files were deleted.

## Script

```bash
python3 ${CLAUDE_SKILL_DIR}/purge_deck_cache.py $ARGUMENTS
```
