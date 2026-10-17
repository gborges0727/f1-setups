"""Download F1Laps' meta setups for F1 25 and F1 26 and save them to data/<game>.json.

Each track's meta page on F1Laps lists the setup built from the 100 fastest
setups uploaded for that track, a wet version when there is enough wet data,
and which settings fast drivers agree on (marked "important").

Each track's setup list on F1Laps also shows the 20 fastest setups one by one,
dry and wet. The script reads each of them and counts how many use each value,
so the sheets can show how much fast drivers disagree on a setting. Setup pages
never change, so it caches them in .cache/setups/ and a later run fetches only
new ones.

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
CACHE = ROOT / ".cache" / "setups"
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


# The pages for single setups spell some settings differently from the meta page.
LABELS = {
    "Differential Adjustment On Throttle": "Differential On Throttle",
    "Differential Adjustment Off Throttle": "Differential Off Throttle",
    "Break Pressure": "Brake Pressure",
    "Front Break Bias": "Front Brake Bias",
}


def one_setup(game, slug, sid):
    """Return {setting: number} for one uploaded setup, from the cache when it's there."""
    path = CACHE / f"{sid}.json"
    if path.exists():
        return json.loads(path.read_text())
    page = get(f"{BASE}/{game}/setups/{slug}/{sid}/")
    out = {}
    # (?:(?!<dt).)*? keeps each match inside one row, so a header row such as Team
    # can't take the label or value of the row after it.
    rows = re.findall(r'<dt[^>]*>((?:(?!<dt).)*?)</dt>(?:(?!<dt).)*?'
                      r'<dd class="[^"]*text-right[^"]*">(.*?)</dd>', page, re.S)
    for k, v in rows:
        k, v = text(k), text(v).replace(",", ".")
        if re.fullmatch(r"-?[\d.]+[%°˚]?(psi)?", v):
            out[LABELS.get(k, k)] = float(re.sub(r"[^\d.\-]", "", v))
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    time.sleep(1)
    return out


# Two setups count as the same when these match. Ride heights, the differential, brake bias
# and tyre pressures can still vary a little inside one shared setup.
SAME = ["Front Wing", "Rear Wing", "Front Suspension", "Rear Suspension",
        "Front Anti-Roll Bar", "Rear Anti-Roll Bar"]


def ease(s):
    """Score how forgiving a setup is to drive. Higher is easier.

    It rewards more rear wing against front wing, an open on-throttle differential, a locked
    off-throttle differential, a soft rear spring, a rear anti-roll bar softer than the front,
    and brake bias further forward. The first two count double, because they decide most of
    how the rear behaves.
    """
    return (2 * (s["Rear Wing"] - s["Front Wing"]) / 10
            - 2 * (s["Differential On Throttle"] - 50) / 25
            + (s["Differential Off Throttle"] - 10) / 20
            - s["Rear Suspension"] / 20
            - (s["Rear Anti-Roll Bar"] - s["Front Anti-Roll Bar"]) / 10
            + (s["Front Brake Bias"] - 50) / 3)


def lap(s):
    m, _, sec = s.partition(":")
    return float(m) * 60 + float(sec) if sec else None


def forgiving(setups, laps):
    """The most forgiving setup that two or more of the fastest share, or None. See pick()."""
    return pick(setups, laps, lambda values, members: ease(values))


def quickest(setups, laps):
    """The shared setup with the fastest lap, for the sheets' Fast column. See pick()."""
    return pick(setups, laps, lambda values, members: -members[0])


def pick(setups, laps, score):
    """The setup that two or more of the fastest share with the highest score, or None.

    Returns {"values": {setting: value}, "runs": setups that share it, "best": the list
    position of its fastest lap, "gap": seconds behind the fastest lap}. Inside a shared
    setup, each setting takes its most common value, and the faster setup wins a tie.
    """
    groups = {}
    for i, s in enumerate(setups):
        if all(k in s for k in SAME):
            groups.setdefault(tuple(s[k] for k in SAME), []).append(i)
    best = None
    for members in groups.values():
        if len(members) < 2:
            continue
        values = {}
        for k in setups[members[0]]:
            seen = [setups[i][k] for i in members if k in setups[i]]
            values[k] = max(seen, key=lambda v: (seen.count(v), -seen.index(v)))
        s = score(values, members)
        if best is None or s > best[0]:
            best = (s, members, values)
    if not best:
        return None
    _, members, values = best
    first, mine = lap(laps[0]), lap(laps[members[0]])
    gap = round(mine - first, 3) if first and mine else None
    return {"values": values, "runs": len(members), "best": members[0] + 1, "gap": gap}


def fastest(game, slug, cond):
    """Count the values the fastest listed setups use.

    Returns {"n": setups, "counts": {setting: [[value, count], ...]}}, plus "forgiving" and
    "quickest" for dry setups (see pick()). Wet lists are race laps in changing rain, so their lap
    times can't rank setups, and the wet sheets keep the vote.
    """
    page = get(f"{BASE}/{game}/setups/{slug}/" + ("wet/" if cond == "wet" else ""))
    laps = {}
    for row in re.findall(r"<tr\b.*?</tr>", page, re.S):
        m = re.search(rf'href="/{game}/setups/{slug}/([0-9a-f-]{{36}})/"', row)
        cells = [text(c) for c in re.findall(r"<td\b.*?</td>", row, re.S)]
        if m and len(cells) > 4:
            laps.setdefault(m.group(1), cells[4])
    ids = list(dict.fromkeys(re.findall(rf'href="/{game}/setups/{slug}/([0-9a-f-]{{36}})/"', page)))
    setups = [one_setup(game, slug, i) for i in ids]
    counts = {}
    for s in setups:
        for k, v in s.items():
            counts.setdefault(k, {})
            counts[k][v] = counts[k].get(v, 0) + 1
    out = {"n": len(setups),
           "counts": {k: sorted(([v, c] for v, c in c.items()), key=lambda vc: (-vc[1], vc[0]))
                      for k, c in counts.items()}}
    if cond == "dry":
        times = [laps.get(i, "") for i in ids]
        out["forgiving"] = forgiving(setups, times)
        out["quickest"] = quickest(setups, times)
    return out


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
        "fastest": {"dry": fastest(game, slug, "dry"), "wet": fastest(game, slug, "wet")},
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
              f"{len(t['important'])} agreed, fastest {t['fastest']['dry']['n']} dry and "
              f"{t['fastest']['wet']['n']} wet")
        time.sleep(1)
    out = {"game": game, "fetched": datetime.date.today().isoformat(), "tracks": tracks}
    path = ROOT / "data" / f"{game}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(ROOT)} ({len(tracks)} tracks)")


if __name__ == "__main__":
    for g in sys.argv[1:] or ["f1-25", "f1-26"]:
        fetch(g)
