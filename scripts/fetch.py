"""Download F1Laps' meta setups for F1 25 and F1 26 and save them to data/<game>.json.

Each track's meta page on F1Laps lists the setup built from the 100 fastest
setups uploaded for that track, a wet version when there is enough wet data,
and which settings fast drivers agree on (marked "important").

Each track's setup list on F1Laps also shows the 20 fastest setups one by one,
dry and wet, filtered by session. The script reads the 20 fastest race setups
and the 20 fastest Time Trial setups and keeps the two lists apart. It counts
how many use each value, so the sheets can show how much fast drivers disagree
on a setting. It leaves out qualifying, because career mode's parc fermé makes
qualifying run on the race setup. Setup pages never change, so it caches them
in .cache/setups/ and a later run fetches only new ones, a second apart.

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
    time.sleep(1)
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


# F1Laps' session filter codes. Qualifying (4) is left out, because career mode's parc fermé
# makes qualifying run on the race setup.
LISTS = {"race": "5", "tt": "6"}


# The Forgiving column starts from the quickest race setup with a locked on-throttle
# differential, so both rear wheels drive together out of corners. That leaves out the soft
# setup many race drivers share, whose open differential (30 to 60%) and locked off-throttle
# differential make the car slow to turn in.
LOCKED = 85


def pace(values, lap_, drivers):
    """Score a setup on lap time. The score is minus its best lap's gap to the list's fastest lap."""
    return -lap_["gap"] if lap_["gap"] is not None else float("-inf")


def popular(values, lap_, drivers):
    """Score a setup on how many different drivers run it, then on pace() to break a tie."""
    return (drivers, pace(values, lap_, drivers))


def fast(setups, entries):
    """The quickest setup, for the Fast column, even when only one driver runs it. See pick()."""
    return pick(setups, entries, pace, min_drivers=1)


def shared(setups, entries):
    """The quickest setup two or more drivers run, for the Shared column. See pick()."""
    return pick(setups, entries, pace)


def most_run(setups, entries):
    """The setup the most different drivers run, for the Popular column. See pick().

    When no two drivers share a setup, every setup has one driver, so pace() decides and this
    is the quickest one-driver setup.
    """
    return pick(setups, entries, popular, min_drivers=1)


def safe(setups, entries):
    """The starting setup for the Forgiving column, or None. See pick().

    It takes the quickest setup with an on-throttle differential of LOCKED% or more that two or
    more drivers share. When no two drivers share one, it takes the quickest one-driver setup
    with a locked differential. When no setup has one, it takes the quickest shared setup.
    """
    locked = lambda s: s.get("Differential On Throttle", 0) >= LOCKED
    return (pick(setups, entries, pace, keep=locked)
            or pick(setups, entries, pace, keep=locked, min_drivers=1)
            or pick(setups, entries, pace))


def pick(setups, entries, score, keep=None, min_drivers=2):
    """The setup with the highest score that min_drivers or more of the fastest drivers run, or None.

    setups and entries come from one F1Laps list. One driver can upload the same setup twice,
    so the count is of different drivers, not uploads. keep(setup), when given, drops each
    setup that fails it before the drivers are counted, so a group's drivers all pass it.
    Returns {"values": {setting: value}, "runs": drivers who run it, "best": list position of
    its fastest lap, "gap": seconds behind the list's fastest lap, or None when F1Laps shows no
    lap time}. Inside a shared setup, each setting takes its most common value, and the setup
    listed first wins a tie. score(values, {"best", "gap"}, drivers) ranks the candidates,
    highest first.
    """
    first = next((lap(e["lap"]) for e in entries if e["rank"] == 1), None)
    groups = {}
    for i, s in enumerate(setups):
        if all(k in s for k in SAME):
            groups.setdefault(tuple(s[k] for k in SAME), []).append(i)
    drivers = lambda members: len({entries[i]["user"] for i in members})
    best = None
    for members in groups.values():
        if keep:
            members = [i for i in members if keep(setups[i])]
        if not members or drivers(members) < min_drivers:
            continue
        values = {}
        for k in setups[members[0]]:
            seen = [setups[i][k] for i in members if k in setups[i]]
            values[k] = max(seen, key=lambda v: (seen.count(v), -seen.index(v)))
        timed = sorted((entries[i] for i in members if lap(entries[i]["lap"])), key=lambda e: e["rank"])
        top = timed[0] if timed else min((entries[i] for i in members), key=lambda e: e["rank"])
        t = lap(top["lap"])
        lap_ = {"best": top["rank"], "gap": round(t - first, 3) if t and first else None}
        s = score(values, lap_, drivers(members))
        if best is None or s > best[0]:
            best = (s, members, values, lap_)
    if not best:
        return None
    _, members, values, lap_ = best
    return {"values": values, "runs": drivers(members), **lap_}


def one_list(game, slug, cond, kind):
    """Count the values one of F1Laps' lists of the 20 fastest setups uses.

    kind is a key of LISTS. Returns {"n": setups, "counts": {setting: [[value, count], ...]}},
    plus "fast", "shared" and "popular" for dry setups, and "forgiving" (the Forgiving column's
    starting setup, see safe()) for dry race setups. Wet laps are set in changing rain, so the
    wet sheets keep the vote.
    """
    page = get(f"{BASE}/{game}/setups/{slug}/" + ("wet/" if cond == "wet" else "") +
               f"?session={LISTS[kind]}")
    entries, seen = [], set()
    for row in re.findall(r"<tr\b.*?</tr>", page, re.S):
        m = re.search(rf'href="/{game}/setups/{slug}/([0-9a-f-]{{36}})/"', row)
        cells = [text(c) for c in re.findall(r"<td\b.*?</td>", row, re.S)]
        if m and len(cells) > 4 and m.group(1) not in seen:
            seen.add(m.group(1))
            entries.append({"rank": len(seen), "lap": cells[4], "user": cells[1], "id": m.group(1)})
    time.sleep(1)
    setups = [one_setup(game, slug, e["id"]) for e in entries]
    counts = {}
    for s in setups:
        for k, v in s.items():
            counts.setdefault(k, {})
            counts[k][v] = counts[k].get(v, 0) + 1
    out = {"n": len(setups),
           "counts": {k: sorted(([v, c] for v, c in c.items()), key=lambda vc: (-vc[1], vc[0]))
                      for k, c in counts.items()}}
    if cond == "dry":
        out["fast"] = fast(setups, entries)
        out["shared"] = shared(setups, entries)
        out["popular"] = most_run(setups, entries)
        if kind == "race":
            out["forgiving"] = safe(setups, entries)
    return out


def fastest(game, slug, cond):
    """{"race": the race list's counts, "tt": the Time Trial list's counts}. See one_list()."""
    return {kind: one_list(game, slug, cond, kind) for kind in LISTS}


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
        fd, fw = t["fastest"]["dry"], t["fastest"]["wet"]
        print(f"{game} {s}: {len(t['dry'])} dry, {len(t['wet'] or {})} wet, "
              f"{len(t['important'])} agreed, fastest race {fd['race']['n']} dry and "
              f"{fw['race']['n']} wet, Time Trial {fd['tt']['n']} dry and {fw['tt']['n']} wet")
        time.sleep(1)
    out = {"game": game, "fetched": datetime.date.today().isoformat(), "tracks": tracks}
    path = ROOT / "data" / f"{game}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(ROOT)} ({len(tracks)} tracks)")


if __name__ == "__main__":
    for g in sys.argv[1:] or ["f1-25", "f1-26"]:
        fetch(g)
