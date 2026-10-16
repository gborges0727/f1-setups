"""Build site/index.html, site/f1-25/ and site/f1-26/ from templates/ and data/.

site/kerb-attack/index.html is a finished page with its own data and is not
rebuilt here.

Usage: python3 scripts/build.py
"""
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GAMES = {
    "f1-25": {
        "title": "F1 25 Setup Sheet",
        "intro": "Setups from the 100 fastest laps per track on F1Laps, for the 2025 cars. "
                 "The three reverse layouts are included. Pick a track and copy the values "
                 "into the garage menus in the order shown.",
        "key": "f125",
    },
    "f1-26": {
        "title": "F1 26 Setup Sheet",
        "intro": "Setups from the 100 fastest laps per track on F1Laps, for the 2026 Season "
                 "Pack cars. Pick a track and copy the values into the garage menus in the "
                 "order shown.",
        "key": "f1",
    },
}

HEAD = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    "<style>:root{color-scheme:light;box-sizing:border-box;"
    "padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
    "body{margin:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif}"
    "img{max-width:100%}[hidden]{display:none!important}</style>\n"
)


def page(body):
    """Wrap a template in a full document: everything up to its first </style> goes in <head>."""
    i = body.index("</style>") + len("</style>")
    return HEAD + body[:i] + "\n</head><body>\n" + body[i:] + "\n</body></html>\n"


def names(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def wet_note(tracks):
    dry_only = [t["name"] for t in tracks if not t["wet"]]
    if not dry_only:
        return ""
    return (f"<p>F1Laps has no wet data for {names(dry_only)}. For those, start from the dry "
            "setup, add wing at both ends, soften the suspension, and move brake bias "
            "slightly rearward.</p>")


def build():
    template = (ROOT / "templates" / "sheet.html").read_text()
    for game, cfg in GAMES.items():
        data = json.loads((ROOT / "data" / f"{game}.json").read_text())
        fetched = datetime.date.fromisoformat(data["fetched"])
        html = (template
                .replace("__TITLE__", cfg["title"])
                .replace("__INTRO__", cfg["intro"])
                .replace("__WET_NOTE__", wet_note(data["tracks"]))
                .replace("__FETCHED__", f"{fetched.day} {fetched:%B %Y}")
                .replace("__KEY__", cfg["key"])
                .replace("__DATA__", json.dumps(data["tracks"], separators=(",", ":"),
                                                ensure_ascii=False)))
        out = ROOT / "site" / game / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(html))
        print(f"wrote {out.relative_to(ROOT)} ({len(data['tracks'])} tracks)")
    (ROOT / "site" / "index.html").write_text(page((ROOT / "templates" / "index.html").read_text()))
    print("wrote site/index.html")


if __name__ == "__main__":
    build()
