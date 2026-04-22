#!/usr/bin/env python3
"""Fetch Planetary/Sector Qualifier events from swu-competitivehub.com and create YAML event files."""

import os
import re
import sys
import unicodedata
import urllib.request

BASE_URL = "https://www.swu-competitivehub.com"
LISTING_URL = f"{BASE_URL}/tournaments-results/"
EVENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "database", "events")

# Map flag alt text from the site to YAML country names
COUNTRY_MAP = {
    "UK": "United Kingdom",
}

# Supported event types: URL slug -> (filename prefix, YAML type, display label)
EVENT_TYPES = {
    "planetary-qualifier": ("pq", "planetary-qualifier", "Planetary Qualifier"),
    "sector-qualifier": ("sq", "sector-qualifier", "Sector Qualifier"),
}


def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def find_event_links(html, dates):
    """Find all supported event links matching the given dates (YYYY-MM-DD format).

    Returns a list of (url, event_type_key) tuples, where event_type_key is a
    key in EVENT_TYPES.
    """
    slugs = "|".join(re.escape(s) for s in EVENT_TYPES)
    date_re = "|".join(re.escape(d) for d in dates)
    # Require the date to follow the event slug directly, which excludes
    # variants like "planetary-qualifier-limited-...".
    pattern = re.compile(
        r'href="(' + re.escape(BASE_URL) + r'/event/(' + slugs
        + r')-(?:' + date_re + r')-[^"]+/)"'
    )
    seen = set()
    results = []
    for match in pattern.finditer(html):
        url = match.group(1)
        event_type = match.group(2)
        if url not in seen:
            seen.add(url)
            results.append((url, event_type))
    return results


def parse_event_page(html):
    """Extract event details from an event page."""
    info = {}

    # Tournament name from h1 > span
    m = re.search(r'id="span-4-135"[^>]*>\s*(.+?)\s*</span>', html)
    if m:
        info["name"] = m.group(1).strip()

    # Country from flag alt text
    m = re.search(r'alt="([^"]+)"[^>]*height="60"', html)
    if m:
        raw_country = m.group(1).strip()
        info["country"] = COUNTRY_MAP.get(raw_country, raw_country)

    # Players count
    m = re.search(r'id="span-219-135"[^>]*>\s*(\d+)\s*</span>\s*players', html)
    if m:
        info["players"] = int(m.group(1))

    # City — strip trailing US state code (e.g. "Atlanta - GA" → "Atlanta")
    m = re.search(r'id="span-231-135"[^>]*>\s*(.+?)\s*</span>', html)
    if m:
        city = m.group(1).strip()
        city = re.sub(r"\s*-\s*[A-Z]{2}$", "", city)
        info["city"] = city

    # Melee link (Tournament/View for PQs, Hub/View for SQs)
    m = re.search(r'href="(https://melee\.gg/(?:Tournament|Hub)/View/\d+)"', html)
    if m:
        info["melee"] = m.group(1)

    # Livestream (YouTube embed)
    m = re.search(r'<iframe[^>]+src="https://www\.youtube\.com/embed/([^"?]+)', html)
    if m:
        info["livestream"] = f"https://www.youtube.com/watch?v={m.group(1)}"

    return info


# Characters that don't decompose via NFKD and need explicit mapping
_NON_DECOMPOSABLE = str.maketrans({
    "ł": "l", "Ł": "L",
    "ø": "o", "Ø": "O",
    "đ": "d", "Đ": "D",
    "þ": "th", "Þ": "Th",
    "ß": "ss",
    "æ": "ae", "Æ": "Ae",
    "œ": "oe", "Œ": "Oe",
})


def slugify_city(city):
    """Convert city name to a filename-friendly slug."""
    pre = city.translate(_NON_DECOMPOSABLE)
    normalized = unicodedata.normalize("NFKD", pre)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_str.lower())
    return slug.strip("-")


_MELEE_RE = re.compile(r'^melee:\s*"([^"]+)"', re.MULTILINE)


def load_existing_melee_index():
    """Return {melee_url: filepath} for all existing event YAML files."""
    index = {}
    try:
        names = os.listdir(EVENTS_DIR)
    except FileNotFoundError:
        return index
    for name in names:
        if not name.endswith(".yaml"):
            continue
        path = os.path.join(EVENTS_DIR, name)
        try:
            with open(path) as f:
                content = f.read()
        except OSError:
            continue
        m = _MELEE_RE.search(content)
        if m:
            index[m.group(1)] = path
    return index


def write_event_yaml(date_str, info, event_type):
    """Write a YAML event file. Returns (filepath, created) tuple."""
    file_prefix, yaml_type, label = EVENT_TYPES[event_type]
    city = info.get("city", "unknown")
    slug = slugify_city(city)
    filename = f"{date_str}-{file_prefix}-{slug}.yaml"
    filepath = os.path.join(EVENTS_DIR, filename)

    if os.path.exists(filepath):
        return filepath, False

    lines = ["---"]
    lines.append(f'name: "{info.get("name", label + " " + city)}"')
    lines.append(f'type: "{yaml_type}"')
    lines.append(f"players: {info.get('players', 0)}")
    lines.append(f'date: "{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"')
    lines.append("location:")
    lines.append(f'  country: "{info.get("country", "Unknown")}"')
    lines.append(f'  city: "{city}"')

    if "melee" in info:
        lines.append(f'melee: "{info["melee"]}"')

    lines.append("contributors:")
    lines.append('- "NotAlex"')

    if "livestream" in info:
        lines.append("links:")
        lines.append(f'- url: "{info["livestream"]}"')
        lines.append('  title: "Livestream"')

    with open(filepath, "w") as f:
        f.write("\n".join(lines) + "\n")

    return filepath, True


def main():
    if len(sys.argv) < 2:
        print("Usage: fetch_events.py <DATE> [DATE ...]")
        print("Example: fetch_events.py 20260411 20260412")
        sys.exit(1)

    # Validate and convert dates
    raw_dates = sys.argv[1:]
    dates = []
    for d in raw_dates:
        d = d.strip().replace("-", "")
        if not re.match(r"^\d{8}$", d):
            print(f"Error: invalid date format '{d}'. Use YYYYMMDD.")
            sys.exit(1)
        dates.append(d)

    iso_dates = [f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in dates]
    print(f"Fetching Planetary/Sector Qualifiers for: {', '.join(iso_dates)}")

    # Fetch listing page
    print(f"\nFetching tournament listing from {LISTING_URL}...")
    listing_html = fetch_html(LISTING_URL)

    # Find event links for the requested dates
    event_links = find_event_links(listing_html, iso_dates)
    print(f"Found {len(event_links)} event(s).")

    if not event_links:
        print("No events found for the given dates.")
        sys.exit(0)

    # Index existing events by melee URL so we can detect duplicates whose
    # filename slug would otherwise differ (e.g. "México" vs "Estado de México").
    melee_index = load_existing_melee_index()

    # Process each event
    created = 0
    skipped = 0
    date_re = re.compile(r"-(\d{4})-(\d{2})-(\d{2})-")
    for url, event_type in event_links:
        # Extract date from URL
        m = date_re.search(url)
        if not m:
            print(f"  Skipping (can't parse date): {url}")
            continue
        date_str = m.group(1) + m.group(2) + m.group(3)

        print(f"\n  Fetching: {url}")
        try:
            event_html = fetch_html(url)
        except Exception as e:
            print(f"    Error fetching page: {e}")
            continue

        info = parse_event_page(event_html)

        melee_url = info.get("melee")
        if melee_url and melee_url in melee_index:
            existing = os.path.basename(melee_index[melee_url])
            skipped += 1
            print(f"    Skipped (same melee as {existing})")
            continue

        filepath, was_created = write_event_yaml(date_str, info, event_type)
        basename = os.path.basename(filepath)

        if was_created:
            created += 1
            if melee_url:
                melee_index[melee_url] = filepath
            city = info.get("city", "?")
            country = info.get("country", "?")
            players = info.get("players", 0)
            livestream = " + livestream" if "livestream" in info else ""
            print(f"    Created: {basename} ({city}, {country}, {players} players{livestream})")
        else:
            skipped += 1
            print(f"    Skipped (already exists): {basename}")

    print(f"\nDone! Created {created} event(s), skipped {skipped} existing.")


if __name__ == "__main__":
    main()
