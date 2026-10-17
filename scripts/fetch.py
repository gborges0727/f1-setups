"""Download F1Laps' meta setups for F1 25 and F1 26 and save them to data/<game>.json.

Each track's meta page on F1Laps lists the setup built from the 100 fastest
setups uploaded for that track, a wet version when there is enough wet data,
and which settings fast drivers agree on (marked "important").

Each track's setup list on F1Laps also shows the 20 fastest setups one by one,
dry and wet, filtered by session. The script reads the 20 fastest qualifying
setups and the 20 fastest race setups and counts how many use each value, so the
sheets can show how much fast drivers disagree on a setting. It leaves out Time
Trial, which has no tyre wear or fuel load. Setup pages never change, so it
caches them in .cache/setups/ and a later run fetches only new ones.

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


# The settings ease() reads. A shared setup missing any of them can't be scored.
EASE = ["Front Wing", "Rear Wing", "Differential On Throttle", "Differential Off Throttle",
        "Rear Suspension", "Front Anti-Roll Bar", "Rear Anti-Roll Bar", "Front Brake Bias"]


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
    try:
        return float(m) * 60 + float(sec) if sec else None
    except ValueError:
        return None


# F1Laps' session filter codes. Time Trial (6) is left out: it has no tyre wear or fuel load,
# so its setups are built for one lap rather than a race weekend.
SESSIONS = {"quali": "4", "race": "5"}


def forgiving(setups, entries):
    """The most forgiving setup that two or more of the fastest share, or None. See pick()."""
    return pick(setups, entries, lambda values, pace: ease(values))


def quickest(setups, entries):
    """The shared setup with the best qualifying and race pace, for the Fast column. See pick()."""
    def pace_score(values, pace):
        gaps = [p["gap"] for p in pace.values() if p["gap"] is not None]
        return -sum(gaps) / len(gaps) if gaps else float("-inf")
    return pick(setups, entries, pace_score)


def pick(setups, entries, score):
    """The setup that two or more drivers among the fastest share with the highest score, or None.

    One driver can upload the same setup from qualifying and from a race, so the count is of
    different drivers, not uploads. A setup run in both qualifying and the race beats one run in
    only one of them. Returns {"values": {setting: value}, "runs": drivers who run it, and
    "quali" and "race": {"best": list position of its fastest lap, "gap": seconds behind that
    list's fastest lap, or None when F1Laps shows no lap time}, or None where nobody ran it in
    that session}. Inside a shared setup,
    each setting takes its most common value, and the setup listed first wins a tie.
    """
    first = {}
    for e in entries:
        if e["rank"] == 1:
            first[e["kind"]] = lap(e["lap"])
    groups = {}
    for i, s in enumerate(setups):
        if all(k in s for k in SAME):
            groups.setdefault(tuple(s[k] for k in SAME), []).append(i)
    drivers = lambda members: len({entries[i]["user"] for i in members})
    shared = [m for m in groups.values() if drivers(m) >= 2]
    both = [m for m in shared if {entries[i]["kind"] for i in m} == set(SESSIONS)]
    best = None
    for members in both or shared:
        values = {}
        for k in setups[members[0]]:
            seen = [setups[i][k] for i in members if k in setups[i]]
            values[k] = max(seen, key=lambda v: (seen.count(v), -seen.index(v)))
        if any(k not in values for k in EASE):
            continue
        pace = {}
        for kind in SESSIONS:
            mine = [entries[i] for i in members if entries[i]["kind"] == kind]
            if mine:
                timed = sorted((e for e in mine if lap(e["lap"])), key=lambda e: e["rank"])
                top = timed[0] if timed else min(mine, key=lambda e: e["rank"])
                t, f = lap(top["lap"]), first.get(kind)
                pace[kind] = {"best": top["rank"], "gap": round(t - f, 3) if t and f else None}
        s = score(values, pace)
        if best is None or s > best[0]:
            best = (s, members, values, pace)
    if not best:
        return None
    _, members, values, pace = best
    return {"values": values, "runs": drivers(members),
            **{kind: pace.get(kind) for kind in SESSIONS}}


def fastest(game, slug, cond):
    """Count the values the fastest qualifying and race setups use.

    Reads F1Laps' lists of up to 20 fastest qualifying setups and up to 20 fastest race setups.
    Returns {"n": setups, "quali": how many came from qualifying, "race": how many from the
    race, "counts": {setting: [[value, count], ...]}}, plus "forgiving" and "quickest" for
    dry setups (see pick()). Wet laps are set in changing rain, so the wet sheets keep the vote.
    """
    entries = []
    for kind, code in SESSIONS.items():
        page = get(f"{BASE}/{game}/setups/{slug}/" + ("wet/" if cond == "wet" else "") +
                   f"?session={code}")
        seen = set()
        for row in re.findall(r"<tr\b.*?</tr>", page, re.S):
            m = re.search(rf'href="/{game}/setups/{slug}/([0-9a-f-]{{36}})/"', row)
            cells = [text(c) for c in re.findall(r"<td\b.*?</td>", row, re.S)]
            if m and len(cells) > 4 and m.group(1) not in seen:
                seen.add(m.group(1))
                entries.append({"kind": kind, "rank": len(seen), "lap": cells[4],
                                "user": cells[1], "id": m.group(1)})
        time.sleep(1)
    setups = [one_setup(game, slug, e["id"]) for e in entries]
    counts = {}
    for s in setups:
        for k, v in s.items():
            counts.setdefault(k, {})
            counts[k][v] = counts[k].get(v, 0) + 1
    out = {"n": len(setups),
           **{kind: sum(e["kind"] == kind for e in entries) for kind in SESSIONS},
           "counts": {k: sorted(([v, c] for v, c in c.items()), key=lambda vc: (-vc[1], vc[0]))
                      for k, c in counts.items()}}
    if cond == "dry":
        out["forgiving"] = forgiving(setups, entries)
        out["quickest"] = quickest(setups, entries)
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
