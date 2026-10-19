"""Build the site from templates/ and data/.

Writes site/index.html, two sheets and two breakdown pages, then copies in the
files from static/ (the icons and Cloudflare's _redirects file). Each game gets
a main sheet and a breakdown page:

  site/f1-25/    site/f1-25/breakdown/
  site/f1-26/    site/f1-26/breakdown/

templates/common.js holds the setting list and the rule that picks each value. build.py
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
        "lede": "Setups for {lede_cars}, from the 20 fastest race setups on F1Laps for each "
                "track. A switch shows the 20 fastest Time Trial setups instead. Qualifying "
                "setups are left out, because career mode's parc fermé makes qualifying run on "
                "the race setup. The Fast, Shared Fast and Popular columns show the quickest setup, "
                "the quickest one two or more drivers run, and the one most drivers run."
                "{extra} Each wet setting is the "
                "value most of the fastest wet setups run. Settings marked Agreed are ones at "
                "least 70% of the setups run.",
        "description": "{short} car setups for every track from F1Laps' fastest race setups, "
                       "with a Time Trial view. Each sheet shows the quickest setup, the "
                       "quickest one drivers share and the one most drivers run.",
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


def columns(game):
    """The paragraphs that say how each dry column picks its setup."""
    out = [
        "A dry setup comes from up to 20 of the fastest setups F1Laps lists for the track. The "
        "Race view reads its race list and the Time Trial view reads its Time Trial list. The "
        "sheet groups the setups that share wings, springs and anti-roll bars, and counts the "
        "different drivers who run each group. A group's pace is how far its best lap is behind "
        "the fastest lap in the list.",
        "The Fast column is the quickest group, even when only one driver runs it. The Shared "
        "Fast column is the quickest group that two or more drivers run. The Popular column is "
        "the group the most drivers run, and the quicker group wins a tie. When no two drivers "
        "share a setup, the Shared Fast column shows the most common value for each setting, and "
        "the Popular column shows the quickest setup.",
    ]
    return out


def notes(tracks, game):
    out = columns(game) + [
        "A wet setting is the value most of the fastest wet setups in the list run. When F1Laps' "
        "median is a value whose share is within 10 points of the most common one's, the median "
        "wins. Where F1Laps lists fewer than five setups, or leaves a setting off its setup "
        "pages, the sheet uses F1Laps' meta value, the median of its 100 fastest setups.",
        "A median can fall between two clicks, such as 26.5 on a wing. Pick either neighbouring "
        "click.",
        "The sheets leave out qualifying setups, because career mode's parc fermé makes "
        "qualifying run on the race setup. Time Trial has no tyre wear or fuel load, so its "
        "setups suit a single lap. If the tyres overheat or wear fast in a race, raise the tyre "
        "pressures.",
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
    "lede": "What up to 20 of the fastest race setups on F1Laps run for every setting, for "
            "{lede_cars}, against F1Laps' median of its 100 fastest.{extra} A switch shows the "
            "20 fastest Time Trial setups instead. Qualifying setups are left out, because career "
            "mode's parc fermé makes qualifying run on the race setup. The blue bar is the Popular "
            "column's value on a dry sheet, the whole setup the most drivers run, so it isn't "
            "always the most common value for each setting. Cards with an orange border are where that "
            "value differs from the median.",
    "description": "How many of the fastest {short} race and Time Trial setups on F1Laps run "
                   "each value, setting by setting, for every track, against F1Laps' median.",
}


def build():
    common = (ROOT / "templates" / "common.js").read_text()
    template = (ROOT / "templates" / "sheet.html").read_text().replace("__COMMON__", common)
    breakdown = (ROOT / "templates" / "breakdown.html").read_text().replace("__COMMON__", common)
    for game, g in GAMES.items():
        data = json.loads((ROOT / "data" / f"{game}.json").read_text())
        fetched = datetime.date.fromisoformat(data["fetched"])
        for mode, m in MODES.items():
            fill = dict(g, game=game)
            config = {
                "key": f"sheet-{game}-{mode}",
                "cars": g["cars"],
                "fetched": f"{fetched.day} {fetched:%B %Y}",
                "notes": notes(data["tracks"], game) + version_html(),
            }
            html = (template
                    .replace("__TITLE__", m["title"].format(**fill))
                    .replace("__DESCRIPTION__", esc(m["description"].format(**fill)))
                    .replace("__LEDE__", m["lede"].format(**fill))
                    .replace("__BREAKDOWN_URL__", f"/{game}/breakdown/")
                    .replace("__CONFIG__", json.dumps(config, ensure_ascii=False))
                    .replace("__DATA__", json.dumps(data["tracks"], separators=(",", ":"),
                                                    ensure_ascii=False)))
            out = ROOT / "site" / m["path"].format(**fill) / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(page(html))
            print(f"wrote {out.relative_to(ROOT)} ({len(data['tracks'])} tracks)")
        fill = dict(g, game=game)
        config = {"key": f"breakdown-{game}", "cars": g["cars"],
                  "fetched": f"{fetched.day} {fetched:%B %Y}",
                  "notes": "".join(f"<p>{p}</p>" for p in columns(game)) + version_html()}
        html = (breakdown
                .replace("__TITLE__", BREAKDOWN["title"].format(**fill))
                .replace("__DESCRIPTION__", esc(BREAKDOWN["description"].format(**fill)))
                .replace("__LEDE__", BREAKDOWN["lede"].format(**fill))
                .replace("__SHEET_URL__", f"/{game}/")
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
