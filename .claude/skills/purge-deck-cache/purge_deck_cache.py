#!/usr/bin/env python3
"""Purge cached deck files for decks referenced in events matching date patterns."""

import glob
import os
import re
import sys

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..")
EVENTS_DIR = os.path.join(BASE_DIR, "database", "events")
CACHE_DIR = os.path.join(BASE_DIR, "cache", "decks")

URL_RE = re.compile(r'url:\s*"(https://melee\.gg/Decklist/View/[^"]+)"')


def find_event_files(patterns):
    """Find event YAML files matching any of the given date patterns."""
    all_files = sorted(glob.glob(os.path.join(EVENTS_DIR, "*.yaml")))
    matched = []
    for f in all_files:
        basename = os.path.basename(f)
        if any(basename.startswith(p) for p in patterns):
            matched.append(f)
    return matched


def extract_deck_urls(event_files):
    """Extract all deck URLs from event files."""
    urls = set()
    for filepath in event_files:
        with open(filepath) as f:
            for line in f:
                m = URL_RE.search(line)
                if m:
                    urls.add(m.group(1))
    return urls


def find_cache_files(urls):
    """Find cache files whose source field matches any of the given URLs."""
    # Extract UUIDs for faster matching
    uuids = set()
    for url in urls:
        uuid = url.rsplit("/", 1)[-1]
        if uuid:
            uuids.add(uuid)

    if not uuids:
        return []

    # Walk cache directory and check each file's source line
    cache_files = []
    for root, _, files in os.walk(CACHE_DIR):
        for fname in files:
            if not (fname.endswith(".yaml") or fname.endswith(".yaml.skip")):
                continue
            filepath = os.path.join(root, fname)
            try:
                with open(filepath) as f:
                    # Read only the first few lines to find the source field
                    for line in f:
                        if line.startswith("source:"):
                            if any(uuid in line for uuid in uuids):
                                cache_files.append(filepath)
                            break
                        # Stop looking after a few lines
                        if not line.startswith(("---", "source")):
                            break
            except (OSError, UnicodeDecodeError):
                continue

    return cache_files


def main():
    if len(sys.argv) < 2:
        print("Usage: purge_deck_cache.py <DATE_PATTERN> [DATE_PATTERN ...]")
        print("Examples:")
        print("  purge_deck_cache.py 202603           # All March 2026 events")
        print("  purge_deck_cache.py 20260329          # Events on 2026-03-29")
        print("  purge_deck_cache.py 202603 202604     # March and April 2026")
        sys.exit(1)

    patterns = sys.argv[1:]
    print(f"Date patterns: {', '.join(patterns)}")

    # Find matching events
    event_files = find_event_files(patterns)
    if not event_files:
        print("No event files found matching the given patterns.")
        sys.exit(0)

    print(f"Found {len(event_files)} event(s):")
    for f in event_files:
        print(f"  - {os.path.basename(f)}")

    # Extract deck URLs
    urls = extract_deck_urls(event_files)
    print(f"\nFound {len(urls)} unique deck URL(s) across events.")

    if not urls:
        print("No deck URLs to purge.")
        sys.exit(0)

    # Find and delete cache files
    print("\nSearching cache for matching files...")
    cache_files = find_cache_files(urls)

    if not cache_files:
        print("No cache files found for these decks.")
        sys.exit(0)

    print(f"Found {len(cache_files)} cache file(s) to delete.")
    for filepath in cache_files:
        os.remove(filepath)
        print(f"  Deleted: {os.path.relpath(filepath, BASE_DIR)}")

    print(f"\nDone! Deleted {len(cache_files)} cache file(s).")


if __name__ == "__main__":
    main()
