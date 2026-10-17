"""Build the site from templates/ and data/.

Writes site/index.html, four sheets and two breakdown pages, then copies in the
files from static/ (the icons and Cloudflare's _redirects file). Each game gets
a consensus sheet, a kerb-attack sheet and a breakdown page:

  site/f1-25/    site/f1-25/kerb-attack/    site/f1-25/breakdown/
  site/f1-26/    site/f1-26/kerb-attack/    site/f1-26/breakdown/

templates/common.js holds the setting list and the consensus rule. build.py
pastes it into every sheet and breakdown page.

Usage: python3 scripts/build.py
"""
import datetime
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/gborges0727/f1-setups"
# CI sets SITE_VERSION to the release being deployed. A local build says "dev".
VERSION = os.environ.get("SITE_VERSION", "dev")

GAMES = {
    "f1-25": {"short": "F1 25", "cars": "2025 cars", "lede_cars": "the 2025 cars",
              "extra": " The three reverse layouts are included."},
    "f1-26": {"short": "F1 26", "cars": "2026 cars", "lede_cars": "the 2026 Season Pack cars",
              "extra": ""},
}

MODES = {
    "meta": {
        "title": "{short} Setup Sheet",
        "path": "{game}/",
        "lede": "Each value is the one most of the 20 fastest setups on F1Laps run at that "
                "track, for {lede_cars}.{extra} F1Laps' own meta setup takes the median of 100 setups instead, "
                "so some values differ from it. Settings marked Agreed are ones at least 70% of the "
                "20 run. The Dirty air column shows what to change for a race spent following "
                "other cars.",
        "description": "{short} car setups for every track, using the value most of the 20 "
                       "fastest setups on F1Laps run, with dirty-air changes for racing in traffic.",
        "sibling": ("{game}/kerb-attack/", "Kerb attack version"),
    },
    "kerb": {
        "title": "{short} Kerb-Attack Sheet",
        "path": "{game}/kerb-attack/",
        "lede": "The consensus setup for each track, for {lede_cars}, tuned for a driver who "
                "attacks corners and rides kerbs.{extra} Settings marked Agreed stay as the fastest "
                "setups run them, and only the others change. The Dirty air column shows what to "
                "change on top for a race spent following other cars.",
        "description": "{short} kerb-attack car setups for every track, built on the values the "
                       "fastest F1Laps setups run, with dirty-air changes for racing in traffic.",
        "sibling": ("{game}/", "Consensus version"),
    },
}

HEAD = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    "<style>:root{color-scheme:light;box-sizing:border-box;"
    "padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
    "body{margin:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif}"
    "img{max-width:100%}[hidden]{display:none!important}</style>\n"
    '<link rel="icon" href="/favicon.ico" sizes="32x32">'
    '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">\n'
)


def page(body):
    """Wrap a template in a full document: everything up to its first </style> goes in <head>."""
    i = body.index("</style>") + len("</style>")
    return HEAD + body[:i] + "\n</head><body>\n" + body[i:] + "\n</body></html>\n"


def names(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def notes(tracks):
    out = [
        "Each value is the one most of the fastest setups F1Laps lists for the track run: the 20 "
        "fastest dry setups, or up to 20 wet ones. When F1Laps' median is a value whose share is "
        "within 10 points of the most common one's, the median wins. Where F1Laps lists fewer "
        "than five setups, or leaves a setting off its setup pages, the sheet uses F1Laps' meta "
        "value, the median of its 100 fastest setups.",
        "A median can fall between two clicks, such as 26.5 on a wing. Pick either neighbouring "
        "click.",
        "Most of the fastest laps are Time Trial laps, and Time Trial turns off tyre wear. For a "
        "race, raise tyre pressures if the tyres overheat or wear fast.",
        "Parc fermé locks the setup once qualifying starts. If you expect to start behind other "
        "cars, enter the Dirty air values before qualifying.",
    ]
    dry_only = [t["name"] for t in tracks if not t["wet"]]
    if dry_only:
        out.append(f"F1Laps has no wet data for {names(dry_only)}. For those, start from the dry "
                   "setup, add wing at both ends, soften the suspension, and move brake bias "
                   "slightly rearward.")
    out.append("The game can't import setup files. Type a setup in once, then save it in the game "
               "as a custom setup for that track.")
    return "".join(f"<p>{p}</p>" for p in out)


def version_html():
    if VERSION == "dev":
        return f'<p>Development build. The source is on <a href="{REPO}">GitHub</a>.</p>'
    return (f'<p>Version <a href="{REPO}/releases/tag/{VERSION}">{VERSION}</a>. '
            f'The source is on <a href="{REPO}">GitHub</a>.</p>')


def esc(s):
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


BREAKDOWN = {
    "title": "{short} Setup Breakdown",
    "lede": "What the 20 fastest setups on F1Laps run for every setting, for {lede_cars}, against "
            "F1Laps' median of its 100 fastest.{extra} The sheets use the value the most setups "
            "run, or the median when its share is within 10 points of that value's. Cards with an "
            "orange border are where the two differ.",
    "description": "How many of the fastest {short} setups on F1Laps run each value, setting by "
                   "setting, for every track, against F1Laps' median.",
}


def with_picks(tracks, picks):
    """Copy the tracks with each one's hand-picked values from data/picks.json attached as "pick"."""
    ids = {t["id"] for t in tracks}
    for slug in picks:
        if slug not in ids:
            raise SystemExit(f"data/picks.json: no track {slug!r}")
    out = []
    for t in tracks:
        p = picks.get(t["id"])
        if p:
            for cond, pick in p.items():
                bad = [k for k in pick["values"] if not t.get(cond) or k not in t[cond]]
                if bad:
                    raise SystemExit(f"data/picks.json: {t['id']} {cond} has no {', '.join(bad)}")
            t = dict(t, pick=p)
        out.append(t)
    return out


def build():
    common = (ROOT / "templates" / "common.js").read_text()
    template = (ROOT / "templates" / "sheet.html").read_text().replace("__COMMON__", common)
    breakdown = (ROOT / "templates" / "breakdown.html").read_text().replace("__COMMON__", common)
    picks = json.loads((ROOT / "data" / "picks.json").read_text())
    for game, g in GAMES.items():
        data = json.loads((ROOT / "data" / f"{game}.json").read_text())
        picked = with_picks(data["tracks"], picks.get(game, {}))
        fetched = datetime.date.fromisoformat(data["fetched"])
        for mode, m in MODES.items():
            fill = dict(g, game=game)
            sib_path, sib_label = m["sibling"]
            config = {
                "mode": mode,
                "key": f"sheet-{game}-{mode}",
                "cars": g["cars"],
                "fetched": f"{fetched.day} {fetched:%B %Y}",
                "notes": notes(data["tracks"]) + version_html(),
            }
            html = (template
                    .replace("__TITLE__", m["title"].format(**fill))
                    .replace("__DESCRIPTION__", esc(m["description"].format(**fill)))
                    .replace("__LEDE__", m["lede"].format(**fill))
                    .replace("__SIBLING_URL__", "/" + sib_path.format(**fill))
                    .replace("__SIBLING_LABEL__", sib_label)
                    .replace("__BREAKDOWN_URL__", f"/{game}/breakdown/")
                    .replace("__CONFIG__", json.dumps(config, ensure_ascii=False))
                    .replace("__DATA__", json.dumps(picked, separators=(",", ":"),
                                                    ensure_ascii=False)))
            out = ROOT / "site" / m["path"].format(**fill) / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(page(html))
            print(f"wrote {out.relative_to(ROOT)} ({len(data['tracks'])} tracks)")
        fill = dict(g, game=game)
        config = {"key": f"breakdown-{game}", "cars": g["cars"],
                  "fetched": f"{fetched.day} {fetched:%B %Y}", "notes": version_html()}
        html = (breakdown
                .replace("__TITLE__", BREAKDOWN["title"].format(**fill))
                .replace("__DESCRIPTION__", esc(BREAKDOWN["description"].format(**fill)))
                .replace("__LEDE__", BREAKDOWN["lede"].format(**fill))
                .replace("__SHEET_URL__", f"/{game}/")
                .replace("__KERB_URL__", f"/{game}/kerb-attack/")
                .replace("__CONFIG__", json.dumps(config, ensure_ascii=False))
                .replace("__DATA__", json.dumps(data["tracks"], separators=(",", ":"), ensure_ascii=False)))
        out = ROOT / "site" / game / "breakdown" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(html))
        print(f"wrote {out.relative_to(ROOT)} ({len(data['tracks'])} tracks)")
    index = (ROOT / "templates" / "index.html").read_text().replace("__VERSION__", version_html())
    (ROOT / "site" / "index.html").write_text(page(index))
    print("wrote site/index.html")
    for f in sorted((ROOT / "static").iterdir()):
        shutil.copy(f, ROOT / "site" / f.name)
    print(f"copied static/ into site/ (version {VERSION})")


if __name__ == "__main__":
    build()
