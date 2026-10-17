# F1 Setup Sheets

Car setups for every track in EA Sports F1 25, for both the 2025 cars and the 2026 cars from the F1 26 Season Pack. The live site is https://f1-setups-cgn.pages.dev/.

The setups come from [F1Laps](https://www.f1laps.com/). For each track, F1Laps lists the 20 fastest setups its users uploaded, dry and wet. The sheets favour a car that's easy to drive over the fastest lap.

For a dry track, `fetch.py` groups the 20 setups that share the same wings, springs and anti-roll bars. It keeps the groups that two or more drivers run and scores each one on how forgiving it is. A setup scores higher for each of these:

- more rear wing against front wing
- a more open on-throttle differential
- a more locked off-throttle differential
- a softer rear spring
- a rear anti-roll bar softer than the front
- brake bias further forward

The wing balance and the on-throttle differential count double. The sheet uses the top-scoring group whole. That keeps it from mixing two setups, which happened at Saudi Arabia in F1 25 under the old per-setting vote. In October 2026 the picked setup's best lap was a median of 0.63 s behind the fastest lap at its track.

For a wet track, each setting uses the value the most of the fastest wet setups run. Wet laps on F1Laps are race laps in changing rain, so their lap times can't rank setups. When F1Laps' meta value is one of the values the setups run, and its share is within 10 percentage points of the most common value's share, the meta value wins. So if 55% run 55% brake bias and 45% run 53%, and F1Laps says 53%, the sheet says 53%.

A setting counts as Agreed, shaded purple, when at least 70% of the setups run the same value and the sheet uses it.

F1Laps' own meta setup takes the median of its 100 fastest setups, the middle value when they're lined up from lowest to highest. F1Laps doesn't state this, but every meta value sits on a click or exactly halfway between two, which is what a median of 100 gives. The median often differs from what most fast drivers run. At Suzuka in F1 25, 15 of the 20 fastest setups run the front anti-roll bar at 6, while the median is 1. The sheets fall back to F1Laps' meta value where F1Laps lists fewer than five setups, and for engine braking, which its setup pages leave out.

Most of the laps behind these numbers are Time Trial laps, which have no tyre wear, so race setups may need higher tyre pressures and a more open on-throttle differential.

The game cannot import setup files. To use a setup, type it in once on the setup screen, then save it in the game as a custom setup for that track.

## Pages

| Page | What it shows |
|---|---|
| `/` | A start page where you pick the cars (2025 or 2026) and the setup style |
| `/f1-25/` and `/f1-26/` | The main setup for every track: 27 tracks with the 2025 cars, including the three reverse layouts, and 25 with the 2026 cars |
| `/f1-25/kerb-attack/` and `/f1-26/kerb-attack/` | The same setups, with the settings fast drivers disagree on changed for riding kerbs, in qualifying and race versions |
| `/f1-25/breakdown/` and `/f1-26/breakdown/` | Every value the 20 fastest setups run for each setting, as a bar chart, with F1Laps' median marked and a list of the settings where the two differ |

Under each setting not marked Agreed, a line shows what the fastest setups run. It gives their range and the share of each common value, such as "35% run 56%" for Monaco brake bias. It also gives F1Laps' median when that differs from the sheet's value. The page addresses carry the chosen track (`/f1-25/breakdown/#japan`), so the links between a game's sheets and its breakdown page keep the same track.

## Picked values

Some values on the sheets can be picked by hand, and a pick replaces the sheet's own value. `data/picks.json` lists them by game, track and weather, with each setting under its F1Laps label. Each entry also has a `why`, which the sheet prints above the setup. A picked setting shows a blue Picked chip, and the kerb-attack and dirty-air changes still apply on top of it. The breakdown pages ignore picks. `fetch.py` never writes `data/picks.json`, so a refresh keeps the picks. `build.py` stops with an error when a pick names a track or setting the data doesn't have.

## Dirty air

Each dry main sheet also has a Fast column for drivers who want lap time over ease. It shows the setup that two or more of the 20 fastest share with the quickest lap, taken whole like the forgiving setup. The kerb-attack and wet sheets don't have it.

Every sheet has a Dirty air column. It shows what to change for a race spent following other cars: two clicks more front wing, a softer front anti-roll bar, and brake bias one step rearward. Parc fermé locks the setup once qualifying starts, so those changes go in before qualifying.

## Refresh the data

F1Laps updates its numbers as new laps arrive. To pull the latest numbers and rebuild every sheet:

```sh
python3 scripts/fetch.py    # downloads every track's meta page and fastest setups into data/f1-25.json and data/f1-26.json
python3 scripts/build.py    # writes the start page, four sheets and two breakdown pages into site/, and copies in static/
```

A first run reads about 2,000 setup pages, one per second, so it takes about 40 minutes. Setup pages never change, so `fetch.py` caches them in `.cache/setups/` and a later run reads only new ones. Both scripts use only the Python standard library. The kerb-attack and dirty-air changes live in `templates/sheet.html`, in the `KERB` and `DIRTY` tables. The setting list and the rule that applies the forgiving setup and the vote live in `templates/common.js`, which `build.py` pastes into every sheet and breakdown page. The built `site/` folder is the whole website, and git ignores it.

## Releases and deploys

Every push to `main` runs the Deploy workflow in GitHub Actions. It builds the site, deploys it to Cloudflare Pages, and publishes a GitHub release. The release number comes from the commit messages since the last release, which follow [Conventional Commits](https://www.conventionalcommits.org/):

| Commit | Example | New version after v1.2.3 |
|---|---|---|
| A breaking change (`type!:` or a `BREAKING CHANGE` footer) | `feat!: rename the sheet URLs` | v2.0.0 |
| A feature | `feat: add a rain setup column` | v1.3.0 |
| Anything else | `fix: correct the Monza rear wing` | v1.2.4 |

Every page footer shows the version it was built from and links to that release. A local build shows "Development build" instead.
