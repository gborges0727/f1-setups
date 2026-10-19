# F1 Setup Sheets

Car setups for every track in EA Sports F1 25, for both the 2025 cars and the 2026 cars from the F1 26 Season Pack. The live site is https://f1-setups-cgn.pages.dev/.

The setups come from [F1Laps](https://www.f1laps.com/). For each track, F1Laps lists the 20 fastest setups its users uploaded, dry and wet, and filters the list by session. The sheets read the race list and the Time Trial list and keep them apart. Each sheet opens on race setups, and a switch at the top shows Time Trial setups instead. The sheets leave out qualifying, because career mode's parc fermé makes qualifying run on the race setup.

For a dry track, `fetch.py` groups the up to 20 setups in a list that share the same wings, springs and anti-roll bars. It counts the different drivers in each group, not uploads, because one driver can upload the same setup twice. A group's pace is how far its best lap is behind the fastest lap in the list. Each column uses its group whole, so it never mixes two setups. The dry sheets have these columns, left to right:

1. Fast, the quickest group, even when only one driver runs it (`fast()` in `fetch.py`)
2. Shared Fast, the quickest group that two or more drivers run (`shared()`)
3. Popular, the group the most drivers run, with the quicker group winning a tie (`most_run()`)

Values in the Shared Fast and Popular columns show in blue where they differ from the Fast column. When two columns hold the same setup, a note under the track name says so.

For a wet track, each setting uses the value the most of the fastest wet setups run. Wet laps are set in changing rain, so their lap times can't rank setups. When F1Laps' meta value is one of the values the setups run, and its share is within 10 percentage points of the most common value's share, the meta value wins. So if 55% run 55% brake bias and 45% run 53%, and F1Laps says 53%, the sheet says 53%.

A setting counts as Agreed, shaded purple, when at least 70% of the setups run the same value and the Popular column uses it. When at least 70% run one value and the Popular column uses another, the setting is marked Unusual.

F1Laps' own meta setup takes the median of its 100 fastest setups, the middle value when they're lined up from lowest to highest. F1Laps doesn't state this, but every meta value sits on a click or exactly halfway between two, which is what a median of 100 gives. The median often differs from what most fast drivers run. The sheets fall back to F1Laps' meta value where F1Laps lists fewer than five setups, and for engine braking, which its setup pages leave out.

The game cannot import setup files. To use a setup, type it in once on the setup screen, then save it in the game as a custom setup for that track.

## Pages

| Page | What it shows |
|---|---|
| `/` | A start page where you pick the cars (2025 or 2026), then open their main sheet or breakdown page |
| `/f1-25/` and `/f1-26/` | The main setup for every track: 27 tracks with the 2025 cars, including the three reverse layouts, and 25 with the 2026 cars |
| `/f1-25/breakdown/` and `/f1-26/breakdown/` | Every value the fastest race or Time Trial setups run for each setting, as a bar chart, with F1Laps' median marked and a list of the settings where the two differ |

On each setting not marked Agreed, hovering over or tapping the chip shows what the fastest setups run. It gives their range and the share of each common value, such as "35% run 56%" for Monaco brake bias. It also gives F1Laps' median when that differs from the Popular column's value. The page addresses carry the chosen track and view (`/f1-25/breakdown/?view=tt#japan`), so the links between a game's sheet and its breakdown page keep both. Without them, a page opens on the track and view the viewer chose last, and then on race setups.

## Refresh the data

F1Laps updates its numbers as new laps arrive. To pull the latest numbers and rebuild every sheet:

```sh
python3 scripts/fetch.py    # downloads every track's meta page and fastest setups into data/f1-25.json and data/f1-26.json
python3 scripts/build.py    # writes the start page, two sheets and two breakdown pages into site/, and copies in static/
```

A first run reads several thousand setup pages, one per second, so it takes over an hour. Setup pages never change, so `fetch.py` caches them in `.cache/setups/` and a later run reads only new ones. Both scripts use only the Python standard library. The setting list, the vote and the column builder `consensus()` live in `templates/common.js`, which `build.py` pastes into every sheet and breakdown page. The built `site/` folder is the whole website, and git ignores it.

## Releases and deploys

Every push to `main` runs the Deploy workflow in GitHub Actions. It builds the site, deploys it to Cloudflare Pages, and publishes a GitHub release. The release number comes from the commit messages since the last release, which follow [Conventional Commits](https://www.conventionalcommits.org/):

| Commit | Example | New version after v1.2.3 |
|---|---|---|
| A breaking change (`type!:` or a `BREAKING CHANGE` footer) | `feat!: rename the sheet URLs` | v2.0.0 |
| A feature | `feat: add a rain setup column` | v1.3.0 |
| Anything else | `fix: correct the Monza rear wing` | v1.2.4 |

Every page footer shows the version it was built from and links to that release. A local build shows "Development build" instead.
