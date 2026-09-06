#!/usr/bin/env python3
"""Add `locked: true` to event files whose top 8 decklists are known.

An event result is considered known — and the event can be locked — only when
every rank from 1 to 8 has a decklist URL. See SKILL.md for the full rule.
"""

import glob
import os
import re
import sys

EVENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "database", "events")

TOP_N = 8

_PLAYERS_RE = re.compile(r"^players:\s*(\d+)\s*$", re.MULTILINE)
_TYPE_RE = re.compile(r'^type: ".*"\n', re.MULTILINE)
_DECK_RE = re.compile(r'^- rank:\s*(\d+)\s*$\n(?:^  url:\s*"([^"]*)"\s*$\n?)?', re.MULTILINE)


def parse_event(text):
    """Return (players, {rank: url_or_empty}) for an event file."""
    m = _PLAYERS_RE.search(text)
    players = int(m.group(1)) if m else 0
    decks = {int(rank): (url or "") for rank, url in _DECK_RE.findall(text)}
    return players, decks


def missing_top_decklists(players, decks):
    """Ranks in the top 8 (or top `players` for smaller events) without a decklist."""
    if players <= 0:
        return list(range(1, TOP_N + 1))
    return [r for r in range(1, min(TOP_N, players) + 1) if not decks.get(r)]


def add_locked(text):
    """Insert `locked: true` right after the `type:` line."""
    return _TYPE_RE.sub(lambda m: m.group(0) + "locked: true\n", text, count=1)


def main(argv):
    apply_changes = "--dry-run" not in argv
    patterns = [a for a in argv if not a.startswith("--")] or [""]

    paths = sorted(
        {p for pattern in patterns for p in glob.glob(os.path.join(EVENTS_DIR, f"{pattern}*.yaml"))}
    )
    if not paths:
        print("No event file matches the given pattern(s).")
        return 1

    locked, skipped, already, warned = [], [], 0, []
    for path in paths:
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        players, decks = parse_event(text)
        missing = missing_top_decklists(players, decks)
        is_locked = "locked: true" in text

        if is_locked:
            already += 1
            if missing:
                warned.append((name, missing))
            continue
        if missing:
            skipped.append((name, players, missing))
            continue

        if apply_changes:
            new_text = add_locked(text)
            if new_text == text:
                skipped.append((name, players, ["no `type:` line to anchor on"]))
                continue
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)
        locked.append((name, players, len(decks)))

    verb = "Locked" if apply_changes else "Would lock"
    print(f"{verb} {len(locked)} event(s):")
    for name, players, ndecks in locked:
        print(f"  {name}  ({players} players, {ndecks} decklists)")

    if skipped:
        print(f"\nSkipped {len(skipped)} event(s) without a complete top {TOP_N}:")
        for name, players, missing in skipped:
            detail = "no result yet" if players == 0 else f"missing rank(s) {missing}"
            print(f"  {name}  ({players} players, {detail})")

    print(f"\n{already} event(s) already locked.")
    if warned:
        print(f"WARNING: {len(warned)} locked event(s) have an incomplete top {TOP_N}:")
        for name, missing in warned:
            print(f"  {name}  missing rank(s) {missing}")
        print("  (left untouched — this script never unlocks an event)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
