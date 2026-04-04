#!/usr/bin/env python3
"""Fetch all cards for a Star Wars Unlimited set from the official API."""

import json
import os
import sys
import urllib.request

API_URL = "https://admin.starwarsunlimited.com/api/card-list"
DATABASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "database", "cards")

EXCLUDED_TYPES = {"Credit Token", "Token Upgrade", "Token Unit"}

ASPECT_MAP = {
    "Vigilance": "vigilance",
    "Aggression": "aggression",
    "Command": "command",
    "Cunning": "cunning",
    "Heroism": "heroism",
    "Villainy": "villainy",
}
RARITY_MAP = {
    "Common": "common",
    "Uncommon": "uncommon",
    "Rare": "rare",
    "Legendary": "legendary",
    "Special": "special",
}
TYPE_MAP = {
    "Leader": "leader",
    "Unit": "unit",
    "Event": "event",
    "Upgrade": "upgrade",
    "Base": "base",
}
ARENA_MAP = {"Ground": "ground", "Space": "space"}


def fetch_page(set_code, page, page_size=100):
    url = (
        f"{API_URL}"
        f"?filters%5Bexpansion%5D%5Bcode%5D%5B%24eq%5D={set_code}"
        f"&pagination%5BpageSize%5D={page_size}"
        f"&pagination%5Bpage%5D={page}"
    )
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def get_name(obj):
    try:
        return obj["data"]["attributes"]["name"]
    except (TypeError, KeyError):
        return ""


def get_list_names(obj):
    try:
        return [i["attributes"]["name"] for i in obj["data"]]
    except (TypeError, KeyError):
        return []


def get_art_url(obj):
    try:
        return obj["data"]["attributes"]["formats"]["card"]["url"]
    except (TypeError, KeyError):
        return ""


def get_thumb_url(obj):
    try:
        return obj["data"]["attributes"]["formats"]["thumbnail"]["url"]
    except (TypeError, KeyError):
        return ""


def escape_yaml(s):
    return s.replace('"', '\\"')


def fetch_all_cards(set_code):
    all_cards = {}
    page = 1

    while True:
        data = fetch_page(set_code, page)
        pagination = data["meta"]["pagination"]
        total_pages = pagination["pageCount"]

        if pagination["total"] == 0:
            print(f"Error: no cards found for set '{set_code}'.")
            sys.exit(1)

        for item in data["data"]:
            attrs = item["attributes"]
            card_num = attrs["cardNumber"]
            card_count = attrs.get("cardCount", 999)

            # Skip variants (cardNumber > cardCount)
            if card_num > card_count:
                continue

            # Skip if variant of another card
            if (attrs.get("variantOf") or {}).get("data"):
                continue

            # Skip tokens
            type_name = get_name(attrs.get("type", {}))
            if type_name in EXCLUDED_TYPES:
                continue

            if card_num not in all_cards:
                all_cards[card_num] = attrs

        print(f"  Page {page}/{total_pages} - {len(all_cards)} cards collected")

        if page >= total_pages:
            break
        page += 1

    return all_cards


def write_yaml(set_code, card_num, attrs, output_dir):
    card_type = TYPE_MAP.get(get_name(attrs.get("type", {})), "")
    rarity = RARITY_MAP.get(get_name(attrs.get("rarity", {})), "")
    aspects = [ASPECT_MAP.get(a, a.lower()) for a in get_list_names(attrs.get("aspects", {}))]
    arenas = [ARENA_MAP.get(a, a.lower()) for a in get_list_names(attrs.get("arenas", {}))]
    art_url = get_art_url(attrs.get("artFront", {}))
    thumb_url = get_thumb_url(attrs.get("artThumbnail", {}))
    cost = attrs.get("cost")
    name = escape_yaml(attrs.get("title", ""))
    title = escape_yaml(attrs.get("subtitle") or "")

    lines = ["---"]
    lines.append(f'set: "{set_code}"')
    lines.append(f"number: {card_num}")
    lines.append(f'type: "{card_type}"')
    lines.append(f'rarity: "{rarity}"')

    if arenas:
        lines.append(f'arena: "{arenas[0]}"')

    if aspects:
        lines.append("aspects:")
        for asp in aspects:
            lines.append(f'- "{asp}"')

    if cost is not None:
        lines.append(f"cost: {cost}")

    lines.append(f'name: "{name}"')
    if title:
        lines.append(f'title: "{title}"')

    lines.append(f'art: "{art_url}"')
    lines.append(f'thumbnail: "{thumb_url}"')

    filepath = os.path.join(output_dir, f"{set_code}-{card_num:03d}.yaml")
    with open(filepath, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: fetch_cards.py <SET_CODE>")
        print("Example: fetch_cards.py LAW")
        sys.exit(1)

    set_code = sys.argv[1].upper()
    output_dir = os.path.join(DATABASE_DIR, set_code)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Fetching cards for set '{set_code}'...")
    all_cards = fetch_all_cards(set_code)
    print(f"\nTotal cards: {len(all_cards)}")

    # Clean existing files
    import glob

    for f in glob.glob(os.path.join(output_dir, "*.yaml")):
        os.remove(f)

    for card_num in sorted(all_cards.keys()):
        write_yaml(set_code, card_num, all_cards[card_num], output_dir)

    card_count = next(iter(all_cards.values())).get("cardCount", "?") if all_cards else "?"
    expected = set(range(1, int(card_count) + 1)) if isinstance(card_count, int) else set()
    actual = set(all_cards.keys())
    missing = expected - actual

    print(f"Generated {len(all_cards)} YAML files in {output_dir}")
    if missing:
        print(f"Missing card numbers: {sorted(missing)}")
    elif expected:
        print(f"All {card_count} cards present!")


if __name__ == "__main__":
    main()
