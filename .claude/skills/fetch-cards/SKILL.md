---
name: fetch-cards
description: Download cards for a Star Wars Unlimited set from the official API and generate YAML files in the database. Use when the user asks to download, fetch, import, or add cards for a set (e.g. SOR, SHD, TWI, JTL, LOF, SEC, IBH, LAW).
argument-hint: <SET_CODE>
allowed-tools: Bash Read Write Glob Grep
---

# Fetch Cards for a Set

Download all cards for the given Star Wars Unlimited set from the official API and write them as YAML files into the database.

## Input

Set code: $ARGUMENTS

The set code must be uppercase (e.g. SOR, SHD, TWI, JTL, LOF, SEC, IBH, LAW).

## Instructions

1. Run the Python script below via Bash, passing the set code as argument.
2. Verify the output: check a few generated YAML files to make sure they look correct.
3. Report how many cards were generated and confirm the output directory.

## Script

```bash
python3 ${CLAUDE_SKILL_DIR}/fetch_cards.py $ARGUMENTS
```

## Expected YAML format

Each card file should follow this structure (fields are omitted when not applicable):

```yaml
---
set: "XXX"
number: 1
type: "leader"
rarity: "rare"
arena: "ground"
aspects:
- "command"
- "aggression"
cost: 6
name: "Card Name"
title: "Card Title"
art: "https://cdn.starwarsunlimited.com//card_....png"
thumbnail: "https://cdn.starwarsunlimited.com//thumbnail_....png"
```

## Validation

After running the script, spot-check at least 3 files (first, middle, last) to confirm:
- `set` matches the requested set code
- `type` is one of: leader, unit, event, upgrade, base
- `art` and `thumbnail` URLs are not empty
- No token cards (Credit, Experience, Shield) are included
