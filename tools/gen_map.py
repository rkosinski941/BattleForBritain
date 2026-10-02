"""Generate a square-grid operational map of Britain and Normandy, 1066.

England and Wales stay on y <= 45 and Normandy/Ponthieu on y >= 49. The open
rows between them are the Channel. src/world.js treats y <= 46 as England once
a Norman army is ashore, so France must not cross that line.

Ermine Street is the straight north road London–Lincoln–York. In fair weather
a housecarl spends four ticks on a road cell and five on a town, with 32 ticks
and eight orders a week, and that road is two weeks long.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W, H = 46, 64

SEA, BEACH, CLEAR, FOREST, HILL, MARSH, RIVER, ROAD, TOWN = range(9)
CH = {
    SEA: "~",
    BEACH: ",",
    CLEAR: ".",
    FOREST: "f",
    HILL: "h",
    MARSH: "m",
    RIVER: "=",
    ROAD: ":",
    TOWN: "#",
}
LANDISH = {CLEAR, FOREST, HILL, MARSH, BEACH, RIVER, ROAD, TOWN}
WALKABLE = {CLEAR, FOREST, HILL, MARSH, BEACH, RIVER, ROAD}

# Inclusive west-east spans. Inlets (Humber, Wash, Thames, Bristol Channel,
# Cardigan Bay, Solway, Morecambe) are indents in the shore, not round holes.
LAND = {
    # Northern England, tapering toward the Cheviots.
    2: [(22, 26)],
    3: [(21, 27)],
    4: [(20, 28)],
    5: [(19, 29)],
    6: [(18, 30)],
    7: [(17, 31)],
    8: [(16, 32)],
    9: [(15, 32)],
    10: [(14, 33)],
    11: [(16, 33)],  # Solway Firth
    12: [(13, 33)],  # Cumbria
    13: [(11, 34)],
    14: [(11, 34)],
    15: [(10, 34)],
    16: [(10, 34)],
    17: [(12, 33)],  # Morecambe Bay
    18: [(10, 33)],
    19: [(9, 33)],
    20: [(8, 33)],
    21: [(7, 33)],
    22: [(7, 34)],
    23: [(7, 34)],  # York
    24: [(6, 33)],
    25: [(6, 28)],  # Humber, north shore
    26: [(6, 27)],
    27: [(5, 31)],  # Lincolnshire begins
    28: [(5, 35)],
    29: [(5, 35)],  # Lincoln, on Ermine Street
    30: [(6, 33)],
    31: [(8, 31)],  # The Wash; Cardigan Bay on the west
    32: [(9, 29)],
    33: [(6, 35)],  # Norfolk shore; Pembrokeshire
    34: [(5, 39)],
    35: [(5, 40)],  # East Anglia
    36: [(6, 39)],
    37: [(8, 37)],  # Bristol Channel opening; Essex
    38: [(13, 28)],  # London, Thames mouth, channel still open
    39: [(15, 35)],  # head of the channel; north Kent
    40: [(7, 39)],  # Devon returns west; Dover's cliffs
    41: [(5, 39)],
    42: [(4, 36)],
    43: [(4, 34)],  # Sussex beaches: Chichester, Pevensey, Hastings
    44: [(5, 14)],  # Cornwall
    45: [(6, 10), (19, 22)],  # Lizard, and the Isle of Wight across the Solent
    # 46-48 Channel
    # Normandy and Ponthieu. St-Valery's headland is the shore closest to Sussex.
    49: [(31, 38)],
    50: [(13, 18), (21, 27), (31, 39)],  # Cotentin, Dives, Seine mouth, Ponthieu
    51: [(11, 40)],
    52: [(10, 41)],
    53: [(10, 41)],
    54: [(9, 41)],
    55: [(9, 42)],
    56: [(10, 41)],
    57: [(11, 40)],
    58: [(12, 39)],
    59: [(14, 37)],
    60: [(16, 35)],
    61: [(18, 33)],
}

TOWNS = [
    ("York", 25, 23, 15, "english"),
    ("Durham", 20, 14, 4, "english"),
    ("Lincoln", 25, 29, 6, "english"),
    ("Nottingham", 19, 27, 5, "english"),
    ("Norwich", 37, 35, 5, "english"),
    ("Stamford", 28, 31, 4, "english"),
    ("Oxford", 19, 35, 5, "english"),
    ("London", 25, 38, 25, "english"),
    ("Winchester", 18, 40, 15, "english"),
    ("Canterbury", 33, 40, 8, "english"),
    ("Dover", 39, 41, 8, "english"),
    ("Hastings", 33, 43, 6, "english"),
    ("Pevensey", 29, 43, 6, "english"),
    ("Chichester", 22, 43, 4, "english"),
    ("Exeter", 11, 41, 5, "english"),
    ("Gloucester", 16, 37, 5, "english"),
    ("Wallingford", 22, 36, 4, "english"),
    ("Thetford", 32, 34, 3, "english"),
    ("St-Valery", 33, 49, 4, "norman"),
    ("Bayeux", 16, 54, 3, "norman"),
    ("Caen", 21, 56, 6, "norman"),
    ("Rouen", 30, 57, 8, "norman"),
    ("Dives", 24, 51, 3, "norman"),
]

# Must be ports, and must actually touch water (the flag is not a fiction).
REQUIRED_PORTS = {
    "London",
    "York",
    "Pevensey",
    "Hastings",
    "Dover",
    "St-Valery",
    "Dives",
    "Rouen",
}


def stamp(grid, cx, cy, rx, ry, terr):
    for y in range(max(0, cy - ry - 1), min(H, cy + ry + 2)):
        for x in range(max(0, cx - rx - 1), min(W, cx + rx + 2)):
            if ((x - cx) / max(rx, 0.5)) ** 2 + ((y - cy) / max(ry, 0.5)) ** 2 <= 1:
                if grid[y][x] in (CLEAR, HILL, FOREST, MARSH):
                    grid[y][x] = terr


def rook_line(x0, y0, x1, y1):
    """4-connected line. Length in steps is |dx| + |dy|."""
    pts = [(x0, y0)]
    x, y = x0, y0
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1 if x0 > x1 else 0
    sy = 1 if y0 < y1 else -1 if y0 > y1 else 0
    ix = iy = 0
    while ix < dx or iy < dy:
        # Step the axis that is furthest behind the straight line.
        if iy == dy or (ix < dx and (ix + 1) * dy <= (iy + 1) * dx):
            x += sx
            ix += 1
        else:
            y += sy
            iy += 1
        pts.append((x, y))
    return pts


def neighbors(x, y):
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        xx, yy = x + dx, y + dy
        if 0 <= xx < W and 0 <= yy < H:
            yield xx, yy


def fill_land(grid):
    for y, spans in LAND.items():
        for west, east in spans:
            for x in range(west, east + 1):
                grid[y][x] = CLEAR


def apply_beaches(grid):
    for y in range(H):
        for x in range(W):
            if grid[y][x] not in (CLEAR, HILL, FOREST, MARSH):
                continue
            sea_n = y > 0 and grid[y - 1][x] == SEA
            sea_s = y + 1 < H and grid[y + 1][x] == SEA
            sea_e = x + 1 < W and grid[y][x + 1] == SEA
            # South coast of England, including the Kent corner at Dover.
            if y <= 45 and y >= 40 and (sea_s or (sea_e and x >= 36)):
                grid[y][x] = BEACH
            # Norman and Ponthieu shore facing the Channel.
            elif y >= 49 and sea_n:
                grid[y][x] = BEACH


def paint_line(grid, points, terr, allowed):
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        for x, y in rook_line(x0, y0, x1, y1):
            if grid[y][x] in allowed:
                grid[y][x] = terr


def town_xy(towns, name):
    t = next(t for t in towns if t["name"] == name)
    return t["x"], t["y"]


def build():
    grid = [[SEA for _ in range(W)] for _ in range(H)]
    fill_land(grid)

    # Uplands and woods. Roads are painted later and bridge these.
    stamp(grid, 22, 6, 3, 3, HILL)  # Cheviots
    stamp(grid, 16, 16, 3, 8, HILL)  # Pennines, west of the Vale of York
    stamp(grid, 10, 27, 4, 7, HILL)  # Welsh massif
    stamp(grid, 16, 34, 3, 2, HILL)  # Cotswolds
    stamp(grid, 10, 42, 3, 2, HILL)  # Dartmoor
    stamp(grid, 30, 41, 7, 1, HILL)  # North and South Downs
    stamp(grid, 18, 55, 6, 3, HILL)  # Norman bocage

    stamp(grid, 30, 41, 4, 2, FOREST)  # the Weald, inland of the Sussex shore
    stamp(grid, 15, 42, 2, 1, FOREST)  # New Forest
    stamp(grid, 21, 26, 2, 2, FOREST)  # Sherwood
    stamp(grid, 12, 24, 2, 3, FOREST)  # Welsh woods
    stamp(grid, 34, 34, 2, 2, FOREST)  # East Anglia
    stamp(grid, 24, 56, 4, 2, FOREST)  # Norman woods

    stamp(grid, 30, 31, 3, 2, MARSH)  # the Fens, east of Ermine Street
    stamp(grid, 18, 38, 2, 1, MARSH)  # Somerset levels
    stamp(grid, 35, 42, 2, 1, MARSH)  # Romney Marsh
    stamp(grid, 29, 27, 2, 1, MARSH)  # Humber levels

    apply_beaches(grid)

    towns = []
    for name, x, y, value, owner in TOWNS:
        if not (0 <= x < W and 0 <= y < H) or grid[y][x] == SEA:
            raise SystemExit(f"{name} ({x},{y}) is not on land")
        grid[y][x] = TOWN
        towns.append(
            {"name": name, "x": x, "y": y, "value": value, "owner": owner, "port": False}
        )

    thames_mouth = (30, 38)
    humber_mouth = (29, 26)
    severn_mouth = (14, 39)
    seine_mouth = (29, 50)
    paint_line(
        grid,
        [town_xy(towns, "Gloucester"), town_xy(towns, "Oxford"), town_xy(towns, "Wallingford"), town_xy(towns, "London"), thames_mouth],
        RIVER,
        WALKABLE,
    )
    paint_line(grid, [town_xy(towns, "York"), humber_mouth], RIVER, WALKABLE)
    paint_line(
        grid,
        [(9, 30), town_xy(towns, "Gloucester"), severn_mouth],
        RIVER,
        WALKABLE,
    )
    # East of Rouen, so the road north to Ponthieu does not pave over the whole Seine.
    paint_line(grid, [(31, 57), (31, 51), seine_mouth], RIVER, WALKABLE)
    paint_line(grid, [town_xy(towns, "St-Valery"), (33, 53)], RIVER, WALKABLE)  # Somme

    roads = [
        ["London", "Lincoln", "York"],  # Ermine Street
        ["York", "Durham"],
        ["Dover", "Canterbury", (28, 39), "London"],  # stays on land west of the Thames mouth
        ["London", "Wallingford", "Oxford"],
        ["Oxford", "Gloucester"],
        ["Exeter", "Winchester", "London"],
        ["Chichester", "Pevensey", "Hastings", (36, 41), "Dover"],
        ["Winchester", "Chichester"],
        ["London", (28, 36), "Thetford", "Norwich"],
        ["Nottingham", "Lincoln"],
        ["Caen", "Bayeux"],
        ["Dives", "Caen"],
        ["Caen", "Rouen"],
        ["Rouen", (33, 52), "St-Valery"],
        ["Dives", (24, 52), (33, 52), "St-Valery"],
    ]
    for path in roads:
        coords = [town_xy(towns, p) if isinstance(p, str) else p for p in path]
        paint_line(grid, coords, ROAD, WALKABLE)

    # Roads bridge rivers. Put a quay back on any required port the pavement sealed off.
    # Never cut the x=25 Ermine Street corridor between York and London.
    for t in towns:
        if t["name"] not in REQUIRED_PORTS:
            continue
        if any(grid[yy][xx] in (SEA, BEACH, RIVER) for xx, yy in neighbors(t["x"], t["y"])):
            continue
        opened = False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, yy = t["x"] + dx, t["y"] + dy
            if not (0 <= xx < W and 0 <= yy < H):
                continue
            if grid[yy][xx] in (SEA, TOWN):
                continue
            if xx == 25 and 23 <= yy <= 38:
                continue
            grid[yy][xx] = RIVER
            opened = True
            break
        if not opened:
            raise SystemExit(f"no quay for {t['name']}")

    for t in towns:
        wet = any(grid[yy][xx] in (SEA, BEACH, RIVER) for xx, yy in neighbors(t["x"], t["y"]))
        t["port"] = wet
        if t["name"] in REQUIRED_PORTS and not wet:
            raise SystemExit(f"{t['name']} is flagged a port but touches no water")

    return grid, towns


def road_costs(grid, start, goal):
    """Per-step move costs for a housecarl along road and town cells."""
    from collections import deque

    q = deque([start])
    prev = {start: None}
    while q:
        x, y = q.popleft()
        if (x, y) == goal:
            break
        for xx, yy in neighbors(x, y):
            if (xx, yy) in prev:
                continue
            if grid[yy][xx] not in (ROAD, TOWN) and (xx, yy) != goal:
                continue
            prev[(xx, yy)] = (x, y)
            q.append((xx, yy))
    if goal not in prev:
        return None
    cells = []
    cur = goal
    while cur != start:
        cells.append(cur)
        cur = prev[cur]
    cells.reverse()
    costs = []
    for x, y in cells:
        costs.append(5 if grid[y][x] == TOWN else 4)
    return costs


def weeks_for(costs, tick_budget=32, order_cap=8):
    i = 0
    weeks = 0
    while i < len(costs):
        weeks += 1
        ticks = 0
        orders = 0
        while i < len(costs) and orders < order_cap and ticks + costs[i] <= tick_budget:
            ticks += costs[i]
            orders += 1
            i += 1
        if orders == 0:
            raise SystemExit(f"step cost {costs[i]} does not fit in a week")
    return weeks


def channel_steps(grid, origin, landings):
    """Fleet steps from a sea cell beside origin to a Sussex beach or port."""
    from collections import deque

    starts = [(xx, yy) for xx, yy in neighbors(*origin) if grid[yy][xx] == SEA]
    if not starts:
        return None
    goals = set()
    for name_xy in landings:
        goals.add(name_xy)
        for xx, yy in neighbors(*name_xy):
            if grid[yy][xx] in (BEACH, SEA):
                goals.add((xx, yy))
    naval = {SEA, BEACH, RIVER, TOWN}
    q = deque((s, 0) for s in starts)
    seen = set(starts)
    while q:
        (x, y), d = q.popleft()
        if (x, y) in goals and grid[y][x] != SEA:
            return d
        if (x, y) in goals and d > 0:
            return d
        for xx, yy in neighbors(x, y):
            if (xx, yy) in seen:
                continue
            if grid[yy][xx] not in naval:
                continue
            seen.add((xx, yy))
            q.append(((xx, yy), d + 1))
    return None


def validate(grid, towns):
    by = {t["name"]: t for t in towns}
    errors = []

    def need(cond, msg):
        if not cond:
            errors.append(msg)

    york, lincoln, london = by["York"], by["Lincoln"], by["London"]
    need(york["y"] < lincoln["y"] < london["y"], "Ermine Street should run York, Lincoln, London from north to south")
    need(york["x"] == lincoln["x"] == london["x"], "Ermine Street should be a straight north road")
    costs = road_costs(grid, (london["x"], london["y"]), (york["x"], york["y"]))
    need(costs is not None, "no road connects London to York")
    weeks = None
    if costs is not None:
        weeks = weeks_for(costs)
        need(weeks <= 2, f"London–York road is {len(costs)} steps, {weeks} fair weeks (want about 2)")
        # Lincoln has to sit on that road, not off on a side track.
        need(grid[lincoln["y"]][lincoln["x"]] == TOWN, "Lincoln missing")

    hastings, pevensey, dover = by["Hastings"], by["Pevensey"], by["Dover"]
    need(pevensey["x"] < hastings["x"] < dover["x"], "Sussex shore should run Pevensey, Hastings, Dover west to east")
    need(pevensey["y"] >= 40 and hastings["y"] >= 40, "Pevensey and Hastings should sit on the south coast")
    for name in ("Pevensey", "Hastings", "Chichester"):
        t = by[name]
        sea_s = t["y"] + 1 < H and grid[t["y"] + 1][t["x"]] == SEA
        need(sea_s or any(grid[yy][xx] == BEACH for xx, yy in neighbors(t["x"], t["y"])), f"{name} is not on a south-coast beach")

    stv = by["St-Valery"]
    dives = by["Dives"]
    need(stv["y"] > hastings["y"], "St-Valery should lie across the Channel from Hastings")
    need(abs(stv["x"] - hastings["x"]) <= 4, "St-Valery should stand opposite Sussex, not off in Brittany")
    need(stv["y"] >= 49 and dives["y"] >= 49, "Norman ports must stay south of the England latitude line")

    for y in range(H):
        for x in range(W):
            if grid[y][x] == SEA:
                continue
            if 46 <= y <= 48:
                errors.append(f"land in the Channel at {x},{y}")
                break

    win = by["Winchester"]
    need(win["x"] < london["x"] and win["y"] > london["y"] - 1, "Winchester should sit in Wessex, southwest of London")
    need(by["Dover"]["x"] >= by["Canterbury"]["x"], "Dover should be east of Canterbury, on the Kent corner")

    steps = channel_steps(
        grid,
        (stv["x"], stv["y"]),
        [(pevensey["x"], pevensey["y"]), (hastings["x"], hastings["y"])],
    )
    need(steps is not None and steps <= 8, f"Channel crossing is {steps} fleet steps (want a fair-weather week, <= 8)")

    for name in REQUIRED_PORTS:
        need(by[name]["port"], f"{name} is not a port")

    # Cornwall is the southwestern tip; the Isle of Wight sits further east.
    # Wales bulges west of the Midlands.
    corn = [x for y in range(43, 46) for x in range(16) if grid[y][x] != SEA]
    wales = min((x for y in range(28, 35) for x in range(W) if grid[y][x] != SEA), default=99)
    need(wales <= 6, "Wales should bulge to the western sea")
    need(bool(corn) and min(corn) <= 6, "Cornwall should be the southwestern peninsula")

    if errors:
        raise SystemExit("map check failed:\n- " + "\n- ".join(errors))
    return {"ermine_steps": len(costs) if costs else None, "ermine_weeks": weeks, "channel_steps": steps}


def main():
    grid, towns = build()
    stats = validate(grid, towns)
    lines = ["".join(CH[c] for c in row) for row in grid]
    debug = "--debug" in sys.argv
    if debug:
        lines = [f"{y:02d} {line}" for y, line in enumerate(lines)]
    print("\n".join(lines))
    print("--- towns ---")
    for t in towns:
        print(f"{t['name']:14} {t['x']:2},{t['y']:2} port={t['port']} {CH[grid[t['y']][t['x']]]}")
    print(
        f"Ermine Street {stats['ermine_steps']} steps, "
        f"{stats['ermine_weeks']} fair weeks for housecarls. "
        f"Channel {stats['channel_steps']} fleet steps, St-Valery to Sussex."
    )
    out = {
        "w": W,
        "h": H,
        "terrain": [cell for row in grid for cell in row],
        "towns": towns,
    }
    dest = Path(__file__).resolve().parents[1] / "data" / "map.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out), encoding="utf-8")
    print("wrote", dest)


if __name__ == "__main__":
    main()
