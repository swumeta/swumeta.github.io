#!/usr/bin/env python3
"""Fetch Planetary Qualifier events from swu-competitivehub.com and create YAML event files."""

import os
import re
import sys
import urllib.request

BASE_URL = "https://www.swu-competitivehub.com"
LISTING_URL = f"{BASE_URL}/tournaments-results/"
EVENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "database", "events")

# Map flag alt text from the site to YAML country names
COUNTRY_MAP = {
    "UK": "United Kingdom",
}


def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def find_pq_links(html, dates):
    """Find all Planetary Qualifier links matching the given dates (YYYY-MM-DD format)."""
    pattern = re.compile(
        r'href="(' + re.escape(BASE_URL) + r'/event/planetary-qualifier-('
        + "|".join(re.escape(d) for d in dates)
        + r')-[^"]+/)"'
    )
    seen = set()
    results = []
    for match in pattern.finditer(html):
        url = match.group(1)
        if url not in seen:
            seen.add(url)
            results.append(url)
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

    # City
    m = re.search(r'id="span-231-135"[^>]*>\s*(.+?)\s*</span>', html)
    if m:
        info["city"] = m.group(1).strip()

    # Melee link
    m = re.search(r'href="(https://melee\.gg/Tournament/View/\d+)"', html)
    if m:
        info["melee"] = m.group(1)

    # Livestream (YouTube embed)
    m = re.search(r'<iframe[^>]+src="https://www\.youtube\.com/embed/([^"?]+)', html)
    if m:
        info["livestream"] = f"https://www.youtube.com/watch?v={m.group(1)}"

    return info


def slugify_city(city):
    """Convert city name to a filename-friendly slug."""
    slug = city.lower()
    # Normalize common accented characters
    replacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "ù": "u", "û": "u", "ü": "u",
        "ô": "o", "ö": "o",
        "î": "i", "ï": "i",
        "ç": "c",
        "ń": "n", "ñ": "n",
        "ł": "l",
        "ś": "s", "š": "s",
        "ž": "z", "ź": "z", "ż": "z",
        "ć": "c", "č": "c",
        "ř": "r",
        "ě": "e",
        "ů": "u",
        "ý": "y",
        "á": "a",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ą": "a",
        "ę": "e",
    }
    for char, repl in replacements.items():
        slug = slug.replace(char, repl)
    # Replace non-alphanumeric with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def write_event_yaml(date_str, info):
    """Write a YAML event file. Returns (filepath, created) tuple."""
    city = info.get("city", "unknown")
    slug = slugify_city(city)
    filename = f"{date_str}-pq-{slug}.yaml"
    filepath = os.path.join(EVENTS_DIR, filename)

    if os.path.exists(filepath):
        return filepath, False

    lines = ["---"]
    lines.append(f'name: "{info.get("name", "Planetary Qualifier " + city)}"')
    lines.append('type: "planetary-qualifier"')
    lines.append(f"players: {info.get('players', 0)}")
    lines.append(f'date: "{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"')
    lines.append("location:")
    lines.append(f'  country: "{info.get("country", "Unknown")}"')
    lines.append(f'  city: "{city}"')

    melee = info.get("melee", "")
    lines.append(f'melee: "{melee}"')

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
    print(f"Fetching Planetary Qualifiers for: {', '.join(iso_dates)}")

    # Fetch listing page
    print(f"\nFetching tournament listing from {LISTING_URL}...")
    listing_html = fetch_html(LISTING_URL)

    # Find PQ links for the requested dates
    pq_links = find_pq_links(listing_html, iso_dates)
    print(f"Found {len(pq_links)} Planetary Qualifier(s).")

    if not pq_links:
        print("No events found for the given dates.")
        sys.exit(0)

    # Process each event
    created = 0
    skipped = 0
    for url in pq_links:
        # Extract date from URL
        m = re.search(r"/planetary-qualifier-(\d{4})-(\d{2})-(\d{2})-", url)
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
        filepath, was_created = write_event_yaml(date_str, info)
        basename = os.path.basename(filepath)

        if was_created:
            created += 1
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
