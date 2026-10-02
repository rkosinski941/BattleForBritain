# Battle for Britain — agent notes

Static HTML/JS wargame. No Node, no bundler. Serve with `python -m http.server 8080`.

## Stack

- `index.html`, `style.css`, `src/*.js` (ES modules)
- Map: `tools/gen_map.py` writes `data/map.json`
- Play: open `http://localhost:8080` (modules will not load from `file://`)

## Rules

- You command William. English and Norse are AI.
- Simultaneous orders, 32-tick resolution, cardinal movement, max eight orders.
- Channel: land units embark on a friendly fleet; remaining sea orders pass to the fleet. Gales block sea.
- Commit after every working build. Do not merge your own PRs.
- Prefer small PRs that leave the game playable.
- Verify in the browser: title screen, pick up a unit, plot orders, execute a week, date advances.
- Do not add a build step or npm toolchain unless the issue asks for it.

## Layout

| Path | Role |
| --- | --- |
| `src/world.js` | Terrain, map load, order of battle |
| `src/engine.js` | Orders, pathing, combat, weather, victory |
| `src/ai.js` | English and Norse orders |
| `src/view.js` | Scrolling canvas, HUD, input |
| `src/main.js` | Title / game / end screens |
| `data/map.json` | Generated grid and towns |

If you change coasts or towns, regenerate with `python tools/gen_map.py` and check the ASCII print before committing.

## Cursor Cloud specific instructions

- Python 3 on the base image is enough. There is no package install. `data/map.json` is already committed.
- The `game` terminal serves this repo with `python3 -m http.server 8080`. If it is not running, start that command from the repo root.
- Open `http://localhost:8080`. Modules do not load from `file://`.
- Verify in the browser: title screen, Cross the Channel, hold a Norman unit, plot an order, Execute week, and confirm the HUD date moves past 18 September 1066.
