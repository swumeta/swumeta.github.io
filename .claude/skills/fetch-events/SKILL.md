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
3. Report how many events were created and list them.

## Script

```bash
python3 ${CLAUDE_SKILL_DIR}/fetch_events.py $ARGUMENTS
```
