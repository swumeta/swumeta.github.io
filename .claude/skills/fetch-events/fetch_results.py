#!/usr/bin/env python3
"""Backfill a top 8 from swu-competitivehub.com when melee has no decklists.

Only ever fills `- rank:` entries that carry no `url:`, and only inside the
top 8. See SKILL.md — this is a fallback, run on explicit request.
"""

import glob
import html
import os
import re
import sys
import unicodedata
import urllib.request

BASE_URL = "https://www.swu-competitivehub.com"
LISTING_URL = f"{BASE_URL}/tournaments-results/"
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(SKILL_DIR, "..", "..", "..", "database")
EVENTS_DIR = os.path.join(DATABASE_DIR, "events")
CARDS_DIR = os.path.join(DATABASE_DIR, "cards")

TOP_N = 8

# The site prints a bare colour when the organiser recorded the aspect and not
# the card. Which plain common base it was is unknowable from the page, so it is
# reported, never guessed — but the choice is narrower than it looks: the site
# groups every plain common base of an aspect under that one colour, so any of
# them renders the same.
GENERIC_BASES = {"blue", "red", "green", "yellow", "white", "black"}
COLOUR_ASPECTS = {
    "blue": "vigilance",
    "green": "command",
    "red": "aggression",
    "yellow": "cunning",
}

# Two sets break the common-base symmetry, so their commons are never offered as
# a stand-in for a bare colour. Nothing in the card database distinguishes them —
# it records neither HP nor card text — so the exception lives here.
SPECIAL_COMMONS = {
    "LOF": "the site labels them {colour} Force",
    "LAW": "they carry an ability and 27 HP",
}


def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def normalize(name):
    """Fold a card name to a comparison key: ASCII, lowercase, alphanumeric."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_str = decomposed.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_str.lower())


def load_cards():
    """Index the card database.

    Returns (by_name, plain_commons):
      by_name       {('leader'|'base', normalized name): [(code, set), ...]}
      plain_commons {aspect: [code, ...]} — the common single-aspect bases the
                    site lumps together under a bare colour, SPECIAL_COMMONS
                    aside.
    """
    by_name, plain_commons = {}, {}
    for path in sorted(glob.glob(os.path.join(CARDS_DIR, "*", "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        m = re.search(r'^type: "(leader|base)"', text, re.MULTILINE)
        if not m:
            continue
        card_type = m.group(1)
        name = re.search(r'^name: "([^"]*)"', text, re.MULTILINE)
        card_set = re.search(r'^set: "([^"]*)"', text, re.MULTILINE)
        if not name or not card_set:
            continue
        code = os.path.basename(path)[: -len(".yaml")]
        by_name.setdefault((card_type, normalize(name.group(1))), []).append(
            (code, card_set.group(1))
        )
        aspects = re.findall(r'^- "(\w+)"', text, re.MULTILINE)
        rarity = re.search(r'^rarity: "([^"]*)"', text, re.MULTILINE)
        if (
            card_type == "base"
            and rarity
            and rarity.group(1) == "common"
            and len(aspects) == 1
            and card_set.group(1) not in SPECIAL_COMMONS
        ):
            plain_commons.setdefault(aspects[0], []).append(code)
    return by_name, plain_commons


def resolve(cards, plain_commons, card_type, name, set_hint):
    """Resolve a card name to its code. Returns (code, error)."""
    if card_type == "base" and normalize(name) in GENERIC_BASES:
        return None, generic_base_error(name, plain_commons)
    matches = cards.get((card_type, normalize(name)), [])
    if not matches:
        return None, f"no {card_type} named {name!r} in the card database"
    if len(matches) == 1:
        return matches[0][0], None
    narrowed = [code for code, card_set in matches if card_set == set_hint]
    if len(narrowed) == 1:
        return narrowed[0], None
    codes = ", ".join(code for code, _ in matches)
    return None, f"{name!r} is ambiguous ({codes})"


def generic_base_error(colour, plain_commons):
    """Explain what a bare colour on the site leaves undecided, and how narrow
    the choice really is."""
    aspect = COLOUR_ASPECTS.get(normalize(colour))
    codes = plain_commons.get(aspect, []) if aspect else []
    if not codes:
        return f'the site only prints a generic "{colour}" base'
    excluded = "; ".join(
        f"{card_set}'s are out, {reason.format(colour=colour)}"
        for card_set, reason in sorted(SPECIAL_COMMONS.items())
    )
    return (
        f'the site only prints a generic "{colour}" base — any plain common '
        f"{aspect} base renders under that one name, so pick whichever the user "
        f"wants recorded: {', '.join(codes)} ({excluded})"
    )


_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_IMG_RE = re.compile(r'<img src="([^"]+)" alt="([^"]*)"[^>]*class="icon-(leader|base)')
_SET_HINT_RE = re.compile(r"-([A-Z0-9]{3})\.[a-z]+$")


def parse_results(page):
    """Return {rank: {'player', 'leader', 'base', 'leader_set', 'base_set'}}.

    The Results table is server-rendered: rank in the first cell, leader and
    base as <img> alt text, player in the last cell. Rows carry no decklist
    link — an event that has one is handled by the decklist path instead.
    """
    start = page.find('id="tableResults"')
    if start < 0:
        return {}
    body = page[page.find("<tbody>", start) : page.find("</tbody>", start)]
    results = {}
    for row in _ROW_RE.findall(body):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 2:
            continue
        rank = re.match(r"\s*(\d+)\s*$", re.sub(r"<[^>]*>", "", cells[0]))
        if not rank:
            continue
        entry = {"player": strip_tags(cells[-1])}
        for src, alt, kind in _IMG_RE.findall(row):
            entry[kind] = re.sub(r"\s*\([A-Z0-9]{3}\)\s*$", "", html.unescape(alt))
            hint = _SET_HINT_RE.search(src)
            in_alt = re.search(r"\(([A-Z0-9]{3})\)\s*$", alt)
            entry[f"{kind}_set"] = in_alt.group(1) if in_alt else (
                hint.group(1) if hint else None
            )
        results[int(rank.group(1))] = entry
    return results


def strip_tags(cell):
    return " ".join(re.sub(r"<[^>]*>", "", html.unescape(cell)).split())


def find_hub_page(date, melee_url):
    """Locate the hub page for an event by matching its melee link."""
    listing = fetch_html(LISTING_URL)
    urls = re.findall(
        r'href="(' + re.escape(BASE_URL) + r"/event/[^\"]*" + re.escape(date) + r'[^"]*)"',
        listing,
    )
    for url in dict.fromkeys(urls):
        page = fetch_html(url)
        if melee_url and melee_url.rsplit("/", 1)[-1] in page:
            return url, page
    return None, None


_MELEE_RE = re.compile(r'^melee:\s*"([^"]+)"', re.MULTILINE)
_DATE_RE = re.compile(r'^date:\s*"(\d{4})-(\d{2})-(\d{2})"', re.MULTILINE)
_RANK_RE = re.compile(r"^- rank: (\d+)\n((?:^  \w+:.*\n)*)", re.MULTILINE)


def backfill(path, cards, plain_commons, apply_changes):
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as f:
        text = f.read()

    date = _DATE_RE.search(text)
    melee = _MELEE_RE.search(text)
    if not date:
        return f"{name}: no date field", False
    if any(
        "url:" in body for rank, body in _RANK_RE.findall(text) if int(rank) <= TOP_N
    ):
        return f"{name}: already has top 8 decklists — use them, not this fallback", False

    url, page = find_hub_page("-".join(date.groups()), melee.group(1) if melee else "")
    if not page:
        return f"{name}: no matching event page on the hub", False

    results = parse_results(page)
    missing = [r for r in range(1, TOP_N + 1) if r not in results]
    if missing:
        return f"{name}: hub lists no result for rank(s) {missing} ({url})", False

    problems, updates = [], {}
    for rank in range(1, TOP_N + 1):
        entry = results[rank]
        fields = [f"  player: {entry['player']}"]
        for kind in ("leader", "base"):
            if kind not in entry:
                problems.append(f"rank {rank}: no {kind} on the hub page")
                continue
            code, error = resolve(
                cards, plain_commons, kind, entry[kind], entry.get(f"{kind}_set")
            )
            if code:
                fields.append(f"  {kind}: {code}")
            else:
                problems.append(f"rank {rank} ({entry['player']}): {error}")
        updates[rank] = "".join(f"{line}\n" for line in fields)

    def replace(match):
        rank = int(match.group(1))
        if rank not in updates or match.group(2).strip():
            return match.group(0)
        return f"- rank: {rank}\n{updates[rank]}"

    new_text = _RANK_RE.sub(replace, text)
    if apply_changes and new_text != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)

    report = [f"{name}: filled ranks 1-{TOP_N} from {url}"]
    report += [f"  NEEDS A DECISION — {p}" for p in problems]
    return "\n".join(report), True


def main(argv):
    apply_changes = "--dry-run" not in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print("usage: fetch_results.py <event.yaml|pattern> [...] [--dry-run]")
        return 2

    paths = sorted(
        {
            p
            for a in args
            for p in (
                glob.glob(a)
                if os.sep in a or a.endswith(".yaml")
                else glob.glob(os.path.join(EVENTS_DIR, f"{a}*.yaml"))
            )
        }
    )
    if not paths:
        print("No event file matches the given argument(s).")
        return 1

    cards, plain_commons = load_cards()
    failed = 0
    for path in paths:
        report, ok = backfill(path, cards, plain_commons, apply_changes)
        print(report)
        failed += not ok
    if apply_changes:
        print("\nReview every NEEDS A DECISION line before locking the event.")
    else:
        print("\n(dry run — nothing written)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
