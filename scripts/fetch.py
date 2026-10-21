"""Download F1Laps' meta setups for F1 25 and F1 26 and save them to data/<game>.json.

Each track's meta page on F1Laps lists the setup built from the 100 fastest
setups uploaded for that track, a wet version when there is enough wet data,
and which settings fast drivers agree on (marked "important").

Each track's setup list on F1Laps also shows the 20 fastest setups one by one,
dry and wet, filtered by session. The list has no next page, but its team filter
shows another 20 for each team. So for race setups and for Time Trial setups,
the script reads the list with no filter and the list for each non-F2 team. It keeps
the 100 fastest setups it finds, the pool, and keeps the race and Time Trial
pools apart. It counts how many use each value, so the sheets can show how much
fast drivers disagree on a setting. It leaves out qualifying, because career mode's parc fermé makes
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
import urllib.error
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


def get(url, tries=4):
    """The page at url. A server error (5xx) or a dropped connection waits a minute and tries
    again, up to tries times, because a full run takes hours and F1Laps sometimes goes down."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if i == tries - 1 or (isinstance(e, urllib.error.HTTPError) and e.code < 500):
                raise
            print(f"retry in 60 s: {url}: {e}", flush=True)
            time.sleep(60)


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


def pace(values, lap_, drivers):
    """Score a setup on lap time. The score is minus its best lap's gap to the pool's fastest lap."""
    return -lap_["gap"] if lap_["gap"] is not None else float("-inf")


def popular(values, lap_, drivers):
    """Score a setup on how many different drivers run it, then on pace() to break a tie."""
    return (drivers, pace(values, lap_, drivers))


def fast(setups, entries):
    """The quickest setup, for the Fast column, even when only one driver runs it. See pick()."""
    return pick(setups, entries, pace, min_drivers=1)


def most_run(setups, entries):
    """The setup the most different drivers run, for the Popular column. See pick().

    When no two drivers share a setup, every setup has one driver, so pace() decides and this
    is the quickest one-driver setup.
    """
    return pick(setups, entries, popular, min_drivers=1)


# A big difference between two setups, for the Alt column. Each setting counts on its own, and
# the number is how far apart the values must be, in clicks or differential points.
BIG = {"Front Wing": 5, "Rear Wing": 5, "Front Suspension": 5, "Rear Suspension": 5,
       "Front Anti-Roll Bar": 5, "Rear Anti-Roll Bar": 5,
       "Differential On Throttle": 20, "Differential Off Throttle": 20}


def big(a, b):
    """The settings of BIG where setups a and b differ by a big difference."""
    return [k for k, d in BIG.items() if k in a and k in b and abs(a[k] - b[k]) >= d]


def alt(setups, entries, fast_, popular_):
    """The setup for the Alt column, or None. See pick().

    It takes the group two or more drivers run with the most drivers, among the groups with two
    or more big differences from Popular and two or more from Fast. That leaves out the Fast and
    Popular groups themselves. pace() breaks a tie. The result adds "vs_popular" and "vs_fast",
    the settings that differ a lot from each.
    """
    if not fast_ or not popular_:
        return None
    apart = lambda v: len(big(v, popular_["values"])) >= 2 and len(big(v, fast_["values"])) >= 2
    out = pick(setups, entries, lambda v, lap_, d: (apart(v), d, pace(v, lap_, d)))
    if not out or not apart(out["values"]):
        return None
    return {**out, "vs_popular": big(out["values"], popular_["values"]),
            "vs_fast": big(out["values"], fast_["values"])}


def pick(setups, entries, score, keep=None, min_drivers=2):
    """The setup with the highest score that min_drivers or more of the fastest drivers run, or None.

    setups and entries come from one pool, see one_list(). One driver can upload the same
    setup twice, so the count is of different drivers, not uploads. keep(setup), when given,
    drops each setup that fails it before the drivers are counted, so a group's drivers all pass
    it.
    Returns {"values": {setting: value}, "runs": drivers who run it, "best": pool position of
    its fastest lap, "gap": seconds behind the pool's fastest lap, or None when F1Laps shows no
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


# F1Laps shows at most 20 setups in a list and has no next page. Its team filter shows a
# separate top 20 for each team, so one_list() reads the list once with no filter and once per
# team, then keeps the POOL fastest setups of them all.
PAGE = 20
POOL = 100


def rows(page, game, slug):
    """[{"lap", "user", "team", "id"}, ...] for the setups on one F1Laps list page, in its order."""
    entries, seen = [], set()
    for row in re.findall(r"<tr\b.*?</tr>", page, re.S):
        m = re.search(rf'href="/{game}/setups/{slug}/([0-9a-f-]{{36}})/"', row)
        cells = [text(c) for c in re.findall(r"<td\b.*?</td>", row, re.S)]
        if m and len(cells) > 4 and m.group(1) not in seen:
            seen.add(m.group(1))
            entries.append({"lap": cells[4], "user": cells[1], "team": cells[2], "id": m.group(1)})
    return entries


def teams(page):
    """The values of the team filter on a list page, leaving out "Any Team" and the F2 teams."""
    i = page.find('name="filter_team"')
    if i < 0:
        return []
    return [v for v in re.findall(r'<option[^>]*value="([^"]*)"', page[i:page.find("</select>", i)])
            if v and not v.startswith("f2_")]


def one_list(game, slug, cond, kind):
    """Count the values the POOL fastest setups in one of F1Laps' lists use.

    kind is a key of LISTS. The list with no filter and each team's list add their setups to one
    pool, sorted by lap time. Setups with no lap time go last. Returns {"n": setups, "counts":
    {setting: [[value, count], ...]}, "capped": teams}, plus "fast", "popular" and "alt" for dry
    setups. capped names each team whose list came back full with its last lap quicker than the
    pool's last, because the pool may miss more of that team's setups. Wet laps are set in
    changing rain, so the wet sheets keep the vote.
    """
    url = f"{BASE}/{game}/setups/{slug}/" + ("wet/" if cond == "wet" else "") + f"?session={LISTS[kind]}"
    page = get(url)
    found = {e["id"]: e for e in rows(page, game, slug)}
    full = {}
    # The list with no filter can come back short (17 at Canada in F1 25) while the team lists
    # still add setups, so only an empty one skips them.
    for team in teams(page) if found else []:
        time.sleep(1)
        listed = rows(get(f"{url}&team={team}"), game, slug)
        for e in listed:
            found.setdefault(e["id"], e)
        if len(listed) >= PAGE:
            full[team] = lap(listed[-1]["lap"])
    order = list(found)
    untimed = lambda e: lap(e["lap"]) is None
    entries = sorted(found.values(), key=lambda e: (untimed(e), lap(e["lap"]) or 0, order.index(e["id"])))[:POOL]
    for i, e in enumerate(entries):
        e["rank"] = i + 1
    last = lap(entries[-1]["lap"]) if len(entries) >= POOL else None
    capped = [team for team, t in full.items() if last is None or (t is not None and t < last)]
    if capped:
        print(f"warning: {game} {slug} {cond} {kind}: the pool may miss setups from "
              f"{', '.join(capped)}, whose lists came back full")
    time.sleep(1)
    setups = [one_setup(game, slug, e["id"]) for e in entries]
    counts = {}
    for s in setups:
        for k, v in s.items():
            counts.setdefault(k, {})
            counts[k][v] = counts[k].get(v, 0) + 1
    out = {"n": len(setups),
           "counts": {k: sorted(([v, c] for v, c in c.items()), key=lambda vc: (-vc[1], vc[0]))
                      for k, c in counts.items()},
           "capped": capped}
    if cond == "dry":
        out["fast"] = fast(setups, entries)
        out["popular"] = most_run(setups, entries)
        out["alt"] = alt(setups, entries, out["fast"], out["popular"])
    return out


def fastest(game, slug, cond):
    """{"race": the race pool's counts, "tt": the Time Trial pool's counts}. See one_list()."""
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
