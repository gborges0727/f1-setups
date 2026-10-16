# F1 Setup Sheets

Car setups for every track in EA Sports F1 25, for both the 2025 cars and the 2026 cars from the F1 26 Season Pack. The live site is https://f1-setups-cgn.pages.dev/.

The setups come from [F1Laps](https://www.f1laps.com/). For each track, F1Laps looks at the 100 fastest setups its users uploaded and publishes the value fast drivers use for each setting. It also marks the settings where fast drivers agree. The sheets shade those settings purple. Most of the laps behind these numbers are Time Trial laps, which have no tyre wear, so race setups may need higher tyre pressures and a more open on-throttle differential.

The game cannot import setup files. To use a setup, type it in once on the setup screen, then save it in the game as a custom setup for that track.

## Pages

| Page | What it shows |
|---|---|
| `/` | A start page where you pick the cars (2025 or 2026) and the setup style |
| `/f1-25/` | F1Laps setups for 27 tracks with the 2025 cars, including the three reverse layouts |
| `/f1-26/` | F1Laps setups for 25 tracks with the 2026 cars |
| `/kerb-attack/` | The F1Laps setups for both car generations, with the settings fast drivers disagree on changed for riding kerbs, in qualifying and race versions |

## Refresh the data

F1Laps updates its numbers as new laps arrive. To pull the latest numbers and rebuild the F1 25 and F1 26 sheets:

```sh
python3 scripts/fetch.py    # downloads every track page into data/f1-25.json and data/f1-26.json
python3 scripts/build.py    # writes site/index.html, site/f1-25/ and site/f1-26/
```

Both scripts use only the Python standard library. `build.py` leaves `site/kerb-attack/index.html` alone, because that page keeps its own copy of the data.

The `site/` folder is the whole website. Any static host can serve it.
