"""Build the site from templates/ and data/.

Writes site/index.html and four sheets, then copies in the files from static/
(the icons and Cloudflare's _redirects file). Each game gets an F1Laps meta
sheet and a kerb-attack sheet:

  site/f1-25/              site/f1-25/kerb-attack/
  site/f1-26/              site/f1-26/kerb-attack/

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
        "lede": "F1Laps' setup for each track, built from the 100 fastest setups its users "
                "uploaded, for {lede_cars}.{extra} Settings marked Agreed are the ones where fast "
                "drivers use the same value. The Dirty air column shows what to change for a race "
                "spent following other cars.",
        "description": "{short} car setups for every track from F1Laps' 100 fastest setups, "
                       "with dirty-air changes for racing in traffic.",
        "sibling": ("{game}/kerb-attack/", "Kerb attack version"),
    },
    "kerb": {
        "title": "{short} Kerb-Attack Sheet",
        "path": "{game}/kerb-attack/",
        "lede": "F1Laps' setup for each track, for {lede_cars}, tuned for a driver who attacks "
                "corners and rides kerbs.{extra} Settings fast drivers agree on stay exactly as "
                "F1Laps has them, and only the settings where they disagree change. The Dirty air "
                "column shows what to change on top for a race spent following other cars.",
        "description": "{short} kerb-attack car setups for every track, built on F1Laps' meta "
                       "setups, with dirty-air changes for racing in traffic.",
        "sibling": ("{game}/", "F1Laps meta version"),
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
        "Some F1Laps values fall between two clicks, such as 26.5 on a wing. Pick either "
        "neighbouring click.",
        "Most of the fastest laps behind these numbers are likely Time Trial laps, and Time Trial "
        "turns off tyre wear. For a race, raise tyre pressures if the tyres overheat or wear fast.",
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


def build():
    template = (ROOT / "templates" / "sheet.html").read_text()
    for game, g in GAMES.items():
        data = json.loads((ROOT / "data" / f"{game}.json").read_text())
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
                    .replace("__CONFIG__", json.dumps(config, ensure_ascii=False))
                    .replace("__DATA__", json.dumps(data["tracks"], separators=(",", ":"),
                                                    ensure_ascii=False)))
            out = ROOT / "site" / m["path"].format(**fill) / "index.html"
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
