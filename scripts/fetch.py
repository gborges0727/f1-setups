"""Download F1Laps' meta setups for F1 25 and F1 26 and save them to data/<game>.json.

Each track's meta page on F1Laps lists the setup built from the 100 fastest
setups uploaded for that track, a wet version when there is enough wet data,
and which settings fast drivers agree on (marked "important").

Usage: python3 scripts/fetch.py [f1-25] [f1-26]
"""
import datetime
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://www.f1laps.com"
UA = {"User-Agent": "Mozilla/5.0 (f1-setups; +https://f1-setups-cgn.pages.dev/)"}

NAMES = {
    "australia": "Australia", "china": "China", "japan": "Japan", "bahrain": "Bahrain",
    "saudi_arabia": "Saudi Arabia", "miami": "Miami", "canada": "Canada", "monaco": "Monaco",
    "spain": "Spain", "austria": "Austria", "silverstone": "Great Britain", "spa": "Belgium",
    "hungary": "Hungary", "netherlands": "Netherlands", "monza": "Italy (Monza)",
    "madrid": "Spain (Madrid)", "azerbaijan": "Azerbaijan", "singapore": "Singapore",
    "usa": "USA (Austin)", "mexico": "Mexico", "brazil": "Brazil", "las_vegas": "Las Vegas",
    "qatar": "Qatar", "abudhabi": "Abu Dhabi", "imola": "Italy (Imola)",
    "austria_reverse": "Austria (reverse)", "netherlands_reverse": "Netherlands (reverse)",
    "silverstone_reverse": "Great Britain (reverse)",
}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def text(s):
    return html.unescape(re.sub(r"<[^>]+>|\s+", " ", s)).strip()


def setup_block(page, start, end):
    """Return {setting: value} for the dt/dd rows between two HTML comments."""
    i = page.find(start)
    if i < 0:
        return {}
    j = page.find(end, i + 1) if end else -1
    seg = page[i:j if j > 0 else len(page)]
    rows = re.findall(r'<dt[^>]*>(.*?)</dt>.*?<dd class="[^"]*text-right[^"]*">(.*?)</dd>', seg, re.S)
    # F1Laps writes some decimals with a comma (e.g. "26,50"); store them with a point.
    return {text(k): text(v).replace(",", ".") for k, v in rows}


def track(game, slug):
    url = f"{BASE}/{game}/setups/{slug}/meta/"
    page = get(url)
    head = page[:page.find("<!-- Dry Tab Content -->")]
    important = re.findall(
        r'<span class="text-sm text-foreground">([^<]+)</span>\s*<span[^>]*>important</span>', head)
    name = NAMES.get(slug, slug.replace("_", " ").title())
    if game == "f1-26" and slug == "spain":
        name = "Spain (Barcelona)"
    return {
        "id": slug,
        "name": name,
        "url": url,
        "important": important,
        "dry": setup_block(page, "<!-- Dry Tab Content -->", "<!-- Wet Tab Content -->"),
        "wet": setup_block(page, "<!-- Wet Tab Content -->", "</main>") or None,
    }


def fetch(game):
    index = get(f"{BASE}/{game}/setups/")
    slugs = []
    for s in re.findall(rf'href="/{game}/setups/([a-z_]+)/"', index):
        if s != "wet" and s not in slugs:
            slugs.append(s)
    tracks = []
    for s in slugs:
        t = track(game, s)
        if len(t["dry"]) < 20:
            sys.exit(f"{game} {s}: found {len(t['dry'])} dry settings, expected 20 or 21. "
                     "F1Laps may have changed its page layout.")
        tracks.append(t)
        print(f"{game} {s}: {len(t['dry'])} dry, {len(t['wet'] or {})} wet, "
              f"{len(t['important'])} agreed")
        time.sleep(1)
    out = {"game": game, "fetched": datetime.date.today().isoformat(), "tracks": tracks}
    path = ROOT / "data" / f"{game}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(ROOT)} ({len(tracks)} tracks)")


if __name__ == "__main__":
    for g in sys.argv[1:] or ["f1-25", "f1-26"]:
        fetch(g)
