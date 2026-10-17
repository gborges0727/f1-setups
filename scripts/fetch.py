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


def lap(s):
    m, _, sec = s.partition(":")
    try:
        return float(m) * 60 + float(sec) if sec else None
    except ValueError:
        return None


# F1Laps' session filter codes. Time Trial (6) is left out: it has no tyre wear or fuel load,
# so its setups are built for one lap rather than a race weekend.
SESSIONS = {"quali": "4", "race": "5"}


# The safe setup has a locked on-throttle differential, so both rear wheels drive together out
# of corners, like the F1 25 Saudi Arabia setup the owner tested. That leaves out the soft setup
# many race drivers share, whose open differential (30 to 60%) and locked off-throttle
# differential make the car slow to turn in.
LOCKED = 85


def pace(values, pace, drivers):
    """Score a shared setup on lap time: minus the average of its qualifying and race gaps."""
    gaps = [p["gap"] for p in pace.values() if p["gap"] is not None]
    return -sum(gaps) / len(gaps) if gaps else float("-inf")


def safe(setups, entries):
    """The safe setup for the sheet's main column, or None. See pick().

    It takes the quickest setup with an on-throttle differential of LOCKED% or more that two or
    more drivers share. When no two drivers share one, it takes the quickest one-driver setup
    with a locked differential. When no setup has one, it takes the quickest shared setup.
    """
    locked = lambda s: s.get("Differential On Throttle", 0) >= LOCKED
    return (pick(setups, entries, pace, keep=locked)
            or pick(setups, entries, pace, keep=locked, min_drivers=1)
            or pick(setups, entries, pace))


def quickest(setups, entries):
    """The shared setup with the best qualifying and race pace, for the Fast column. See pick()."""
    return pick(setups, entries, pace)


def pick(setups, entries, score, keep=None, min_drivers=2):
    """The setup that two or more drivers among the fastest share with the highest score, or None.

    One driver can upload the same setup from qualifying and from a race, so the count is of
    different drivers, not uploads. keep(setup), when given, drops each setup that fails it
    before the drivers are counted, so a group's drivers all pass it. A setup
    run in both qualifying and the race beats one run in only one of them. Returns
    {"values": {setting: value}, "runs": drivers who run it, and "quali" and "race": {"best":
    list position of its fastest lap, "gap": seconds behind that list's fastest lap, or None
    when F1Laps shows no lap time}, or None where nobody ran it in that session}. Inside a
    shared setup, each setting takes its most common value, and the setup listed first wins a
    tie. score(values, pace, drivers) ranks the candidates, highest first.
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
    found = []
    for members in groups.values():
        if keep:
            members = [i for i in members if keep(setups[i])]
        if not members or drivers(members) < min_drivers:
            continue
        values = {}
        for k in setups[members[0]]:
            seen = [setups[i][k] for i in members if k in setups[i]]
            values[k] = max(seen, key=lambda v: (seen.count(v), -seen.index(v)))
        found.append((members, values))
    both = [(m, v) for m, v in found if {entries[i]["kind"] for i in m} == set(SESSIONS)]
    best = None
    for members, values in both or found:
        pace = {}
        for kind in SESSIONS:
            mine = [entries[i] for i in members if entries[i]["kind"] == kind]
            if mine:
                timed = sorted((e for e in mine if lap(e["lap"])), key=lambda e: e["rank"])
                top = timed[0] if timed else min(mine, key=lambda e: e["rank"])
                t, f = lap(top["lap"]), first.get(kind)
                pace[kind] = {"best": top["rank"], "gap": round(t - f, 3) if t and f else None}
        s = score(values, pace, drivers(members))
        if best is None or s > best[0]:
            best = (s, members, values, pace)
    if not best:
        return None
    _, members, values, pace = best
    return {"values": values, "runs": drivers(members),
            **{kind: pace.get(kind) for kind in SESSIONS}}


# The Segrob's column starts from the owner's tested F1 25 Saudi Arabia setup, the most stable
# car the owner has driven. Each track gets the setup among its fastest that drives most like it.
MINE = {"f1-25": {
    "Differential On Throttle": 100, "Differential Off Throttle": 10,
    "Front Camber": -3.5, "Rear Camber": -2, "Front Toe": 0, "Rear Toe": 0.1,
    "Front Suspension": 41, "Rear Suspension": 12,
    "Front Anti-Roll Bar": 21, "Rear Anti-Roll Bar": 18,
    "Brake Pressure": 100, "Front Brake Bias": 52,
    "Front Right Tyre Pressure": 26.5, "Rear Right Tyre Pressure": 23,
}}
# The game's range for each setting MINE compares, so a click on a narrow setting counts for as
# much as a click's share of a wide one. Wings and ride heights are left out, because each track
# needs its own.
RANGE = {"Differential On Throttle": 90, "Differential Off Throttle": 90,
         "Front Camber": 1, "Rear Camber": 1.5, "Front Toe": 0.5, "Rear Toe": 0.5,
         "Front Suspension": 40, "Rear Suspension": 40,
         "Front Anti-Roll Bar": 20, "Rear Anti-Roll Bar": 20,
         "Brake Pressure": 20, "Front Brake Bias": 20,
         "Front Right Tyre Pressure": 7, "Rear Right Tyre Pressure": 6}


def segrob(setups, entries, mine):
    """The setup for the Segrob's column: the uploaded setup closest to mine, or None.

    Closeness is the distance between the two setups across the settings in RANGE, each
    divided by its range. Only setups with a locked on-throttle differential count, unless none
    has one. A tie goes to the setup higher in its list. Returns the same shape as pick(), with
    "runs" counting the drivers who upload exactly this setup.
    """
    def far(s):
        return sum(((s.get(k, v) - v) / RANGE[k]) ** 2 for k, v in mine.items()) ** 0.5
    pool = [i for i, s in enumerate(setups) if s.get("Differential On Throttle", 0) >= LOCKED]
    pool = pool or list(range(len(setups)))
    if not pool:
        return None
    best = min(pool, key=lambda i: (round(far(setups[i]), 6), entries[i]["rank"]))
    members = [i for i, s in enumerate(setups) if s == setups[best]]
    first = {e["kind"]: lap(e["lap"]) for e in entries if e["rank"] == 1}
    pace = {}
    for kind in SESSIONS:
        ups = sorted((entries[i] for i in members if entries[i]["kind"] == kind), key=lambda e: e["rank"])
        if ups:
            t, f = lap(ups[0]["lap"]), first.get(kind)
            pace[kind] = {"best": ups[0]["rank"], "gap": round(t - f, 3) if t and f else None}
    return {"values": setups[best], "runs": len({entries[i]["user"] for i in members}),
            "distance": round(far(setups[best]), 3), **{kind: pace.get(kind) for kind in SESSIONS}}


def fastest(game, slug, cond):
    """Count the values the fastest qualifying and race setups use.

    Reads F1Laps' lists of up to 20 fastest qualifying setups and up to 20 fastest race setups.
    Returns {"n": setups, "quali": how many came from qualifying, "race": how many from the
    race, "counts": {setting: [[value, count], ...]}}, plus "forgiving" (the
    safe setup, see safe()), "quickest" and, for a game in MINE, "segrob" for dry setups. Wet laps are set in changing rain, so the wet sheets keep the vote.
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
        # The sheets read the safe setup from "forgiving", the key's name before the safe rule.
        out["forgiving"] = safe(setups, entries)
        out["quickest"] = quickest(setups, entries)
        if game in MINE:
            out["segrob"] = segrob(setups, entries, MINE[game])
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
