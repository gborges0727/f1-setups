# F1 Setup Sheets

Car setups for every track in EA Sports F1 25, for both the 2025 cars and the 2026 cars from the F1 26 Season Pack. The live site is https://f1-setups-cgn.pages.dev/.

The setups come from [F1Laps](https://www.f1laps.com/). For each track, F1Laps lists the 20 fastest setups its users uploaded, dry and wet, and filters the list by session.

The list has no next page, but its team filter shows another 20 fastest for each team. So `fetch.py` reads the list with no filter and the list for every team except the F2 teams, and keeps the 100 fastest setups it finds. It builds this pool for race setups and for Time Trial setups and keeps the two apart. When a team's list comes back full and its last lap is quicker than the pool's 100th, the pool may miss more of that team's setups. `fetch.py` prints a warning and stores the team under `capped` in the data. Each sheet opens on race setups, and a switch at the top shows Time Trial setups instead. The sheets leave out qualifying, because career mode's parc fermé makes qualifying run on the race setup.

For a dry track, `fetch.py` groups the setups in a pool that share the same wings, springs and anti-roll bars. It counts the different drivers in each group, not uploads, because one driver can upload the same setup twice. A group's pace is how far its best lap is behind the fastest lap in the pool. Each column uses its group whole, so it never mixes two setups. The dry sheets have these columns, left to right:

1. Fast, the quickest group, even when only one driver runs it (`fast()` in `fetch.py`)
2. Popular, the group the most drivers run, with the quicker group winning a tie (`most_run()`)
3. Alt, the group the most drivers run among the groups that differ a lot from both Popular and Fast, with the quicker group winning a tie (`alt()`)
4. F1Laps Meta, F1Laps' own meta setup, the track's `dry` block in `data/<game>.json`
5. Stable, the site author's own recipe built from the F1Laps Meta values (`stable()` in `templates/common.js`), with one set of rules for each game

A group can be the Alt column when two or more drivers run it and it has at least two big differences from Popular and at least two from Fast. A big difference is 5 or more clicks on a wing, a suspension or an anti-roll bar, or 20 points or more on a differential. Each setting counts on its own (`BIG` in `fetch.py`). When no group passes, the sheet has no Alt column and a note says so. The Alt column's note lists its big differences from Popular.

The F1Laps Meta column doesn't come from a group. F1Laps takes the median of each setting across its 100 fastest setups, one setting at a time. So the column can mix values that no single driver runs together, and a value can fall between two clicks. It is the same in the Race and Time Trial views.

The F1 25 Stable column starts from the F1Laps Meta values. It raises the rear wing 3 clicks and lowers the rear anti-roll bar 3 clicks. It sets the differential to 75% on throttle and 50% off throttle. It sets brake pressure to 95% and moves front brake bias 1 point forward. Every other setting keeps the meta value. A half value rounds to the lower wing, the softer spring and anti-roll bar, the higher ride height and the more forward bias.

The F1 26 Stable column follows the same rules with one change. It keeps the meta brake bias instead of moving it forward. The author's laps in the 2026 cars at Barcelona and Monaco on 2026-10-26 set the F1 26 rules, and the F1 26 sheet's notes give the numbers behind each one.

The page works the column out each time it loads, so it follows the meta values when the data is refreshed. Only the dry sheets show it, and the "same setup" note leaves it out. The author has driven the F1 25 column only at Canada so far, and nobody has driven the F1 26 column yet.

Values in the Popular, Alt, F1Laps Meta and Stable columns show in blue where they differ from the Fast column. When the Fast and Popular columns hold the same setup, a note under the track name says so.

For a wet track, each setting uses the value the most of the fastest wet setups run. Wet laps are set in changing rain, so their lap times can't rank setups. When F1Laps' meta value is one of the values the setups run, and its share is within 10 percentage points of the most common value's share, the meta value wins. So if 55% run 55% brake bias and 45% run 53%, and F1Laps says 53%, the sheet says 53%.

A setting counts as Agreed, shaded purple, when at least 70% of the setups run the same value and the Popular column uses it. When at least 70% run one value and the Popular column uses another, the setting is marked Unusual.

F1Laps' own meta setup takes the median of its 100 fastest setups, the middle value when they're lined up from lowest to highest. F1Laps doesn't state this, but every meta value sits on a click or exactly halfway between two, which is what a median of 100 gives. The median often differs from what most fast drivers run. The sheets fall back to F1Laps' meta value where F1Laps lists fewer than five setups. F1Laps also lists engine braking at 50% on every F1 26 meta setup, but the game has no such setting, so the sheets leave it out.

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

A first run reads about 13,000 setup pages and a few thousand list pages, one per second, so it takes about six hours. Setup pages never change, so `fetch.py` caches them in `.cache/setups/` and a later run reads only new ones. A later run still reads every list page again, the list with no filter and one for each team. When F1Laps returns a server error, `fetch.py` waits a minute and tries again, up to four times. Both scripts use only the Python standard library. The setting list, the vote and the column builder `consensus()` live in `templates/common.js`, which `build.py` pastes into every sheet and breakdown page. The built `site/` folder is the whole website, and git ignores it.

## Releases and deploys

Every push to `main` runs the Deploy workflow in GitHub Actions. It builds the site, deploys it to Cloudflare Pages, and publishes a GitHub release. The release number comes from the commit messages since the last release, which follow [Conventional Commits](https://www.conventionalcommits.org/):

| Commit | Example | New version after v1.2.3 |
|---|---|---|
| A breaking change (`type!:` or a `BREAKING CHANGE` footer) | `feat!: rename the sheet URLs` | v2.0.0 |
| A feature | `feat: add a rain setup column` | v1.3.0 |
| Anything else | `fix: correct the Monza rear wing` | v1.2.4 |

Every page footer shows the version it was built from and links to that release. A local build shows "Development build" instead.
