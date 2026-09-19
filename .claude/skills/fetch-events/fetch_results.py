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
import urllib.parse
import urllib.request

BASE_URL = "https://www.swu-competitivehub.com"
SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap.xml"
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

# What the site prints where the card database keeps the printed name. Short
# forms the site chose itself, not abbreviations a reader would have to guess.
SITE_ALIASES = {
    ("leader", "sabine"): "Sabine Wren",
    ("leader", "anakin"): "Anakin Skywalker",
    ("base", "ecl"): "Energy Conversion Lab",
}

# Which plain common the database records when the site prints only a colour.
# Every candidate renders the same, so the pick is pure convention: the SOR
# common for an ordinary colour, the LOF one for a "{colour} Force". Applied
# only under --conventional-bases; without it a bare colour stays a question
# for the user, as it always was.
CONVENTIONAL_COMMONS = {
    ("plain", "vigilance"): "SOR-020",
    ("plain", "command"): "SOR-023",
    ("plain", "aggression"): "SOR-026",
    ("plain", "cunning"): "SOR-029",
    ("force", "vigilance"): "LOF-020",
    ("force", "command"): "LOF-023",
    ("force", "aggression"): "LOF-026",
    ("force", "cunning"): "LOF-029",
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

    Returns (by_name, commons):
      by_name  {('leader'|'base', normalized name): [(code, set), ...]}
      commons  {'plain'|'force': {aspect: [code, ...]}} — the common
               single-aspect bases the site lumps together under one name: a
               bare colour for the ordinary ones, "{colour} Force" for LOF's.
               LAW's carry an ability and belong to neither group.
    """
    by_name, commons = {}, {"plain": {}, "force": {}}
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
        ):
            group = "force" if card_set.group(1) == "LOF" else (
                None if card_set.group(1) in SPECIAL_COMMONS else "plain"
            )
            if group:
                commons[group].setdefault(aspects[0], []).append(code)
    return by_name, commons


def resolve(cards, commons, card_type, name, set_hint, conventional=False):
    """Resolve a card name to its code. Returns (code, error)."""
    if card_type == "base":
        colour = re.sub(r"\s+force$", "", name.strip(), flags=re.IGNORECASE)
        if normalize(colour) in GENERIC_BASES:
            group = "force" if colour.lower() != name.strip().lower() else "plain"
            aspect = COLOUR_ASPECTS.get(normalize(colour))
            if conventional and (group, aspect) in CONVENTIONAL_COMMONS:
                return CONVENTIONAL_COMMONS[(group, aspect)], None
            return None, generic_base_error(name, colour, commons[group], group)
    key = normalize(name)
    matches = cards.get((card_type, normalize(SITE_ALIASES.get((card_type, key), name))), [])
    if not matches:
        return None, f"no {card_type} named {name!r} in the card database"
    if len(matches) == 1:
        return matches[0][0], None
    narrowed = [code for code, card_set in matches if card_set == set_hint]
    if len(narrowed) == 1:
        return narrowed[0], None
    codes = ", ".join(code for code, _ in matches)
    return None, f"{name!r} is ambiguous ({codes})"


def generic_base_error(printed, colour, commons, group):
    """Explain what a bare colour on the site leaves undecided, and how narrow
    the choice really is."""
    aspect = COLOUR_ASPECTS.get(normalize(colour))
    codes = commons.get(aspect, []) if aspect else []
    if not codes:
        return f'the site only prints a generic "{printed}" base'
    if group == "force":
        return (
            f'the site only prints a generic "{printed}" base — any LOF common '
            f"{aspect} base renders under that one name, so pick whichever the "
            f"user wants recorded: {', '.join(codes)}"
        )
    excluded = "; ".join(
        f"{card_set}'s are out, {reason.format(colour=colour)}"
        for card_set, reason in sorted(SPECIAL_COMMONS.items())
    )
    return (
        f'the site only prints a generic "{printed}" base — any plain common '
        f"{aspect} base renders under that one name, so pick whichever the user "
        f"wants recorded: {', '.join(codes)} ({excluded})"
    )


_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_IMG_RE = re.compile(r'<img src="([^"]+)" alt="([^"]*)"[^>]*class="icon-(leader|base)')
_SET_HINT_RE = re.compile(r"-([A-Z0-9]{3})\.[a-z]+$")


def parse_results(page):
    """Return {rank: {'player', 'leader', 'base', 'leader_set', 'base_set'}}.

    The Results table is server-rendered: rank in the first cell (a bare number
    on recent pages, an ordinal such as "5th" on older ones), leader and base as
    <img> alt text, player in the last cell. A row often also links the melee
    decklist the build never saw, which is better data than leader/base.
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
        rank = re.match(r"\s*(\d+)(?:st|nd|rd|th)?\s*$", strip_tags(cells[0]))
        if not rank:
            continue
        entry = {"player": strip_tags(cells[-1])}
        link = _DECKLIST_RE.search(row)
        if link:
            entry["decklist"] = link.group(1)
        for src, alt, kind in _IMG_RE.findall(row):
            entry[kind] = re.sub(r"\s*\([A-Z0-9]{3}\)\s*$", "", html.unescape(alt))
            hint = _SET_HINT_RE.search(src)
            in_alt = re.search(r"\(([A-Z0-9]{3})\)\s*$", alt)
            entry[f"{kind}_set"] = in_alt.group(1) if in_alt else (
                hint.group(1) if hint else None
            )
        results[int(rank.group(1))] = entry
    return results


_DECKLIST_RE = re.compile(r'href="(https://melee\.gg/Decklist/View/[^"]+)"')


def strip_tags(cell):
    return " ".join(re.sub(r"<[^>]*>", "", html.unescape(cell)).split())


_event_urls = None


def event_urls():
    """Every event URL the hub publishes, from its sitemaps.

    The /tournaments-results/ listing only carries the last few months, so an
    older event is invisible there; the sitemaps go back to the first event.
    """
    global _event_urls
    if _event_urls is None:
        index = fetch_html(SITEMAP_INDEX_URL)
        _event_urls = []
        for sitemap in re.findall(r"<loc>([^<]*evenement-sitemap[^<]*)</loc>", index):
            _event_urls += re.findall(r"<loc>([^<]*/event/[^<]*)</loc>", fetch_html(sitemap))
    return _event_urls


def find_hub_page(date, melee_url, city=""):
    """Locate the hub page for an event by matching its melee link.

    A handful of events carry no melee link at all. For those the date plus the
    city in the slug is the only handle there is, so it is used — but only when
    it singles one page out, and the caller says so in its report.
    """
    urls = list(dict.fromkeys(u for u in event_urls() if date in u))
    for url in urls:
        page = fetch_html(url)
        if melee_url and melee_url.rsplit("/", 1)[-1] in page:
            return url, page
    if not melee_url and city:
        named = [u for u in urls if normalize(city) in normalize(urllib.parse.unquote(u))]
        if len(named) == 1:
            return named[0], fetch_html(named[0])
    return None, None


_MELEE_RE = re.compile(r'^melee:[ \t]*"?([^"\s]+)"?[ \t]*$', re.MULTILINE)
_DATE_RE = re.compile(r'^date:\s*"?(\d{4})-(\d{2})-(\d{2})"?', re.MULTILINE)
_RANK_RE = re.compile(r"^- rank: (\d+)\n((?:^  \w+:.*\n)*)", re.MULTILINE)
# An older import wrote `url: null` for a rank melee never published; it carries
# no more information than an empty entry, so both are fillable.
_EMPTY_URL_RE = re.compile(r"\s*url:\s*(?:null|~)?\s*$")
_RECORDED_URL_RE = re.compile(r'^  url:\s*"?(https?://\S+?)"?\s*$', re.MULTILINE)


def needs_fill(body):
    """True when a `- rank:` entry holds no result — empty, or only `url: null`."""
    lines = [line for line in body.splitlines() if line.strip()]
    return all(_EMPTY_URL_RE.match(line) for line in lines)


_PLAYERS_RE = re.compile(r"^players:\s*(\d+)\s*$", re.MULTILINE)
_DECKS_RE = re.compile(r"^decks:[^\S\n]*\n?", re.MULTILINE)


_TYPE_RE = re.compile(r"^type:.*\n", re.MULTILINE)


def ensure_locked(text):
    """Mark the event final.

    A leader/base entry is the end of the line for that rank — nothing will
    ever add a decklist to it — and the Build website job merges into whatever
    it finds, so an unlocked event invites it to write over the hub's result.
    """
    if re.search(r"^locked:\s*true\s*$", text, re.MULTILINE):
        return text
    return _TYPE_RE.sub(lambda m: m.group(0) + "locked: true\n", text, count=1)


def insert_rows(text, rows):
    """Add `- rank:` entries the file has no row for at all, in rank order.

    Some events were imported with a partial `decks:` list, or none — the rows
    the hub has for those ranks have nowhere to be substituted into.
    """
    if not _DECKS_RE.search(text):
        text = text.rstrip("\n") + "\ndecks:\n"
    decks_end = _DECKS_RE.search(text).end()
    entries = [(int(m.group(1)), m.start(), m.end()) for m in _RANK_RE.finditer(text)]
    insertions = []
    for rank, body in rows.items():
        after = [e for e in entries if e[0] > rank]
        offset = after[0][1] if after else (entries[-1][2] if entries else decks_end)
        insertions.append((offset, f"- rank: {rank}\n{body}"))
    for offset, block in sorted(insertions, reverse=True):
        text = text[:offset] + block + text[offset:]
    return text


def backfill(path, cards, commons, apply_changes, conventional=False):
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as f:
        text = f.read()

    date = _DATE_RE.search(text)
    melee = _MELEE_RE.search(text)
    if not date:
        return f"{name}: no date field", False
    players = _PLAYERS_RE.search(text)
    field = min(TOP_N, int(players.group(1))) if players and int(players.group(1)) else TOP_N
    rows = {int(rank): body for rank, body in _RANK_RE.findall(text)}
    gaps = [r for r in range(1, field + 1) if r not in rows or needs_fill(rows[r])]
    if not gaps:
        return f"{name}: already has top 8 decklists — use them, not this fallback", False

    city = re.search(r'^  city:\s*"?([^"\n]+?)"?\s*$', text, re.MULTILINE)
    url, page = find_hub_page(
        "-".join(date.groups()),
        melee.group(1) if melee else "",
        city.group(1) if city else "",
    )
    if not page:
        return f"{name}: no matching event page on the hub", False

    results = parse_results(page)

    # The hub and the database do not always rank an event the same way, and a
    # row copied into a rank the other site gives to someone else is worse than
    # an empty one. Two things have to hold: where both name a decklist for a
    # rank they must name the same one, and a decklist the hub puts in the top 8
    # must not already sit at some other rank in the file — including below it,
    # which is how the widest disagreements show up.
    recorded = {
        m.group(1).rstrip("/"): int(rank)
        for rank, body in _RANK_RE.findall(text)
        for m in _RECORDED_URL_RE.finditer(body)
    }
    disagree = set()
    for rank, entry in results.items():
        theirs = (entry.get("decklist") or "").rstrip("/")
        if theirs and recorded.get(theirs, rank) != rank:
            disagree.add(rank)
    for rank, body in rows.items():
        have = _RECORDED_URL_RE.search(body)
        theirs = results.get(rank, {}).get("decklist")
        if have and theirs and have.group(1).rstrip("/") != theirs.rstrip("/"):
            disagree.add(rank)
    disagree = sorted(disagree)
    if disagree:
        return (
            f"{name}: the hub ranks this event differently — rank(s) {disagree} "
            f"hold another decklist there, so its rows cannot be trusted ({url})",
            False,
        )

    absent = [r for r in gaps if r not in results]
    gaps = [r for r in gaps if r in results]
    if not gaps:
        return f"{name}: hub lists no result for rank(s) {absent} ({url})", False

    problems = [f"hub lists no result for rank(s) {absent}"] if absent else []
    updates = {}
    for rank in gaps:
        entry = results[rank]
        # The hub often links the melee decklist the build never saw. It is a
        # real result rather than a leader/base reconstruction, so it wins.
        if entry.get("decklist"):
            updates[rank] = f'  url: "{entry["decklist"]}"\n'
            continue
        # Some pages leave the player column blank; an empty `player:` reads
        # back as null, so the field is left out rather than written hollow.
        fields = [f"  player: {entry['player']}"] if entry["player"] else []
        resolved = {}
        for kind in ("leader", "base"):
            if kind not in entry:
                problems.append(f"rank {rank}: no {kind} on the hub page")
                continue
            code, error = resolve(
                cards, commons, kind, entry[kind], entry.get(f"{kind}_set"), conventional
            )
            if code:
                resolved[kind] = code
                fields.append(f"  {kind}: {code}")
            else:
                problems.append(f"rank {rank} ({entry['player']}): {error}")
        # A leader is what identifies the deck; the hub prints "Unknow Leader"
        # when the organiser recorded nothing. An entry naming only a player is
        # no more a result than an empty one, so leave the rank alone and say so.
        if "leader" not in resolved:
            problems.append(f"rank {rank} ({entry['player']}): left empty, no leader to record")
            continue
        updates[rank] = "".join(f"{line}\n" for line in fields)

    usable = [r for r in gaps if r in updates]
    if not usable:
        return f"{name}: the hub records nothing usable for rank(s) {gaps} ({url})", False

    def replace(match):
        rank = int(match.group(1))
        if rank not in updates:
            return match.group(0)
        return f"- rank: {rank}\n{updates[rank]}"

    new_text = _RANK_RE.sub(replace, text)
    added = {r: body for r, body in updates.items() if r not in rows}
    if added:
        new_text = insert_rows(new_text, added)
    if new_text != text and any("leader:" in body for body in updates.values()):
        new_text = ensure_locked(new_text)
    if apply_changes and new_text != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)

    ranks = ", ".join(str(r) for r in usable)
    how = "" if melee else " (matched by city, not by melee link — check it)"
    report = [f"{name}: filled rank(s) {ranks} from {url}{how}"]
    report += [f"  NEEDS A DECISION — {p}" for p in problems]
    return "\n".join(report), True


def main(argv):
    apply_changes = "--dry-run" not in argv
    conventional = "--conventional-bases" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(
            "usage: fetch_results.py <event.yaml|pattern> [...] "
            "[--conventional-bases] [--dry-run]"
        )
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

    cards, commons = load_cards()
    failed = 0
    for path in paths:
        report, ok = backfill(path, cards, commons, apply_changes, conventional)
        print(report)
        failed += not ok
    if apply_changes:
        print("\nReview every NEEDS A DECISION line before locking the event.")
    else:
        print("\n(dry run — nothing written)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
