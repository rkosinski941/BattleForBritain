"""Generate a square-grid operational map of Britain and Normandy, 1066.

The land mask is a hand-drawn coastline, not a smoothed blob. England and
Wales stay on y <= 44. Rows 45 and 46 are the open Channel. Normandy and
Ponthieu start at y >= 47, south of the latitude src/world.js treats as
England (y <= 46).

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

# Inclusive west-east spans. Inlets are bites in the shore, not round holes.
# Spine of the island is x=22: York (y=18), Lincoln (y=24), London (y=32).
LAND = {
    # Northern England, widening south from the Cheviots.
    2: [(21, 26)],
    3: [(19, 29)],
    4: [(18, 31)],
    5: [(17, 32)],
    6: [(16, 33)],
    7: [(15, 33)],
    8: [(14, 34)],
    # Solway Firth, then the Cumbrian bulge and Morecambe Bay.
    9: [(17, 34)],
    10: [(16, 34)],
    11: [(11, 34)],
    12: [(9, 34)],
    13: [(12, 33)],
    14: [(8, 33)],
    # Wales juts west. The Humber is a funnel on the east of York.
    15: [(4, 33)],
    16: [(2, 33)],
    17: [(2, 33)],
    18: [(2, 26)],
    19: [(2, 24)],
    20: [(3, 32)],
    21: [(3, 35)],
    # Cardigan Bay bites deep. The Wash is a square gulf. Lincoln is x=22.
    22: [(8, 36)],
    23: [(10, 34)],
    24: [(8, 27)],
    25: [(6, 26)],
    26: [(4, 26)],
    # Pembrokeshire hooks west. Norfolk jumps out to close the Wash.
    27: [(2, 37)],
    28: [(2, 40)],
    29: [(2, 42)],  # East Anglia
    30: [(2, 41)],
    31: [(3, 36)],
    # Thames estuary, east of London.
    32: [(2, 27)],
    33: [(2, 26)],
    # Bristol Channel: South Wales, open water, then the Somerset bridge.
    34: [(2, 11), (19, 28)],
    35: [(2, 9), (21, 34)],
    36: [(3, 7), (23, 41)],  # Wales tip, and Dover's cliff at the east end
    # The channel mouth opens west. Devon is the south shore.
    37: [(10, 39)],
    38: [(6, 36)],
    39: [(4, 34)],
    # Lyme Bay opens south between Devon and Hampshire.
    40: [(3, 12), (20, 34)],
    # Sussex shore. Sea is immediately south of the eastern span, so a fleet
    # that embarks at St-Valery can reach this beach in the same fair week.
    41: [(3, 11), (20, 33)],
    # Cornwall keeps going. The Solent, south of Sussex, is open water.
    42: [(4, 9)],
    # Isle of Wight, with sea on every side.
    43: [(5, 8), (24, 26)],
    44: [(6, 7), (25, 25)],
    # 45-46 open Channel.
    # Cotentin to the west, St-Valery's headland to the east, Seine bay between.
    47: [(13, 16), (31, 35)],
    48: [(12, 18), (30, 38)],
    49: [(11, 20), (30, 39)],
    50: [(10, 25), (29, 40)],
    51: [(9, 41)],
    52: [(8, 41)],
    53: [(9, 40)],
    54: [(10, 39)],
    55: [(11, 38)],
    56: [(13, 36)],
    57: [(15, 34)],
    58: [(17, 32)],
}

TOWNS = [
    ("York", 22, 18, 15, "english"),
    ("Durham", 18, 8, 4, "english"),
    ("Lincoln", 22, 24, 6, "english"),
    ("Nottingham", 16, 22, 5, "english"),
    ("Norwich", 39, 29, 5, "english"),
    ("Stamford", 26, 28, 4, "english"),
    ("Oxford", 16, 32, 5, "english"),
    ("London", 22, 32, 25, "english"),
    ("Winchester", 21, 38, 15, "english"),
    ("Canterbury", 33, 37, 8, "english"),
    ("Dover", 41, 36, 8, "english"),
    ("Hastings", 31, 41, 6, "english"),
    ("Pevensey", 26, 41, 6, "english"),
    ("Chichester", 22, 41, 4, "english"),
    ("Exeter", 9, 38, 5, "english"),
    ("Gloucester", 20, 34, 5, "english"),
    ("Wallingford", 19, 33, 4, "english"),
    ("Thetford", 33, 30, 3, "english"),
    ("St-Valery", 31, 47, 4, "norman"),
    ("Bayeux", 15, 50, 3, "norman"),
    ("Caen", 22, 53, 6, "norman"),
    ("Rouen", 34, 55, 8, "norman"),
    ("Dives", 23, 50, 3, "norman"),
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

# Ermine Street. Quay-building must not cut this column.
SPINE_X = 22
SPINE_Y0, SPINE_Y1 = 18, 32


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
            # South coast: Sussex, the Solent shore, Cornwall, and Wight's south edge.
            if 39 <= y <= 44 and sea_s:
                grid[y][x] = BEACH
            # Dover's cliff, where Kent meets the sea on the east and the south.
            elif 35 <= y <= 38 and x >= 36 and (sea_s or sea_e):
                grid[y][x] = BEACH
            # Norman and Ponthieu shore facing the Channel.
            elif y >= 47 and sea_n:
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


def paint_road(grid, coords):
    """Paint a road, and refuse a route that steps into the sea."""
    for i in range(len(coords) - 1):
        segment = rook_line(*coords[i], *coords[i + 1])
        for x, y in segment:
            cell = grid[y][x]
            if cell == SEA:
                raise SystemExit(
                    f"road crosses sea at {x},{y} between {coords[i]} and {coords[i + 1]}"
                )
            if cell in WALKABLE:
                grid[y][x] = ROAD


def build():
    grid = [[SEA for _ in range(W)] for _ in range(H)]
    fill_land(grid)

    # Uplands and woods sit inland. Roads are painted later and bridge them.
    # None of these ellipses are the coastline.
    stamp(grid, 22, 5, 3, 2, HILL)  # Cheviots
    stamp(grid, 14, 15, 3, 6, HILL)  # Pennines, west of the Vale of York
    stamp(grid, 7, 29, 4, 6, HILL)  # Welsh massif
    stamp(grid, 16, 37, 2, 2, HILL)  # Cotswolds
    stamp(grid, 10, 39, 2, 1, HILL)  # Dartmoor
    stamp(grid, 28, 39, 5, 1, HILL)  # North and South Downs
    stamp(grid, 22, 55, 5, 2, HILL)  # Norman bocage

    stamp(grid, 27, 38, 3, 1, FOREST)  # the Weald
    stamp(grid, 12, 39, 2, 1, FOREST)  # New Forest
    stamp(grid, 18, 23, 2, 2, FOREST)  # Sherwood, west of Ermine Street
    stamp(grid, 6, 31, 2, 2, FOREST)  # Welsh woods
    stamp(grid, 36, 29, 2, 2, FOREST)  # East Anglia
    stamp(grid, 26, 54, 3, 2, FOREST)  # Norman woods

    stamp(grid, 28, 27, 2, 1, MARSH)  # the Fens, east of Ermine Street
    stamp(grid, 12, 38, 2, 1, MARSH)  # Somerset levels
    stamp(grid, 32, 39, 2, 1, MARSH)  # Romney Marsh
    stamp(grid, 25, 20, 1, 1, MARSH)  # Humber levels

    apply_beaches(grid)

    towns = []
    for name, x, y, value, owner in TOWNS:
        if not (0 <= x < W and 0 <= y < H) or grid[y][x] == SEA:
            raise SystemExit(f"{name} ({x},{y}) is not on land")
        grid[y][x] = TOWN
        towns.append(
            {"name": name, "x": x, "y": y, "value": value, "owner": owner, "port": False}
        )

    # Rivers reach the sea. They stay off the x=22 march except at the town cells.
    paint_line(
        grid,
        [
            town_xy(towns, "Gloucester"),
            (20, 33),
            town_xy(towns, "Oxford"),
            town_xy(towns, "Wallingford"),
            town_xy(towns, "London"),
            (27, 32),
        ],
        RIVER,
        WALKABLE,
    )
    paint_line(grid, [town_xy(towns, "York"), (26, 18)], RIVER, WALKABLE)
    paint_line(
        grid,
        [(10, 30), (20, 31), town_xy(towns, "Gloucester"), (18, 34)],
        RIVER,
        WALKABLE,
    )
    # East of Rouen, so the road north to Ponthieu does not pave the whole Seine.
    paint_line(grid, [(35, 55), (37, 55), (37, 48)], RIVER, WALKABLE)
    paint_line(grid, [(32, 47), (32, 50)], RIVER, WALKABLE)  # Somme

    roads = [
        ["London", "Lincoln", "York"],  # Ermine Street
        ["York", "Durham"],
        ["Dover", (39, 36), (36, 37), "Canterbury", (28, 36), (24, 34), "London"],
        ["London", "Wallingford", "Oxford"],
        ["Oxford", (19, 33), "Gloucester"],
        ["Exeter", "Winchester", (24, 37), (24, 34), "London"],
        ["Chichester", "Pevensey", "Hastings", (33, 40), (34, 38), (36, 37), (39, 36), "Dover"],
        ["Winchester", (20, 39), (22, 40), "Chichester"],
        ["London", (24, 31), (30, 30), "Thetford", "Norwich"],
        ["Nottingham", "Lincoln"],
        ["Caen", "Bayeux"],
        ["Dives", "Caen"],
        ["Caen", "Rouen"],
        ["Rouen", (34, 50), (32, 48), "St-Valery"],
        ["Dives", (23, 52), (32, 52), "St-Valery"],
    ]
    for path in roads:
        coords = [town_xy(towns, p) if isinstance(p, str) else p for p in path]
        paint_road(grid, coords)

    # Roads bridge rivers. Put a quay back on any required port the pavement sealed off.
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
            if xx == SPINE_X and SPINE_Y0 <= yy <= SPINE_Y1:
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


def _xs(grid, y):
    return [x for x in range(W) if grid[y][x] != SEA]


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
        need(grid[lincoln["y"]][lincoln["x"]] == TOWN, "Lincoln missing")
        on_road = road_costs(grid, (london["x"], london["y"]), (lincoln["x"], lincoln["y"]))
        need(on_road is not None, "Lincoln is off Ermine Street")

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
    need(stv["y"] >= 47 and dives["y"] >= 47, "Norman ports must stay south of the England latitude line")

    for y in range(45, 47):
        for x in range(W):
            if grid[y][x] != SEA:
                errors.append(f"land in the Channel at {x},{y}")
                break

    for t in towns:
        if t["owner"] == "norman":
            need(t["y"] > 46, f"{t['name']} is on the England side of the latitude line")

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

    # Silhouette, so a later edit cannot smooth these back into a blob.
    wales = min((x for y in range(15, 34) for x in _xs(grid, y)), default=99)
    need(wales <= 3, "Wales should jut to the western sea")
    cardigan = min(_xs(grid, 23), default=0)
    need(cardigan >= 9, "Cardigan Bay should indent the Welsh coast")
    wash = max(_xs(grid, 25), default=99)
    anglia = max(_xs(grid, 29), default=0)
    need(wash <= 27 and anglia >= 40, "the Wash should bite, and East Anglia should bulge east of it")
    thames = max(_xs(grid, 32), default=99)
    need(thames <= 28, "the Thames estuary should cut in east of London")
    need(grid[34][5] != SEA and grid[34][15] == SEA, "the Bristol Channel should separate South Wales from Somerset")
    need(bool(_xs(grid, 44)) and min(_xs(grid, 44)) <= 7, "Cornwall should be the southwestern peninsula")
    corn = [x for y in range(41, 45) for x in range(14) if grid[y][x] != SEA]
    need(bool(corn) and min(corn) <= 6, "Cornwall should run to the southwest")
    need(grid[40][8] != SEA and grid[40][16] == SEA and grid[40][24] != SEA, "Lyme Bay should open on the south coast")
    # Isle of Wight: land with sea to the north, south, west, and east.
    need(grid[43][25] != SEA and grid[44][25] != SEA, "the Isle of Wight should sit in the Solent")
    need(
        grid[42][25] == SEA and grid[45][25] == SEA and grid[43][23] == SEA and grid[43][27] == SEA,
        "the Isle of Wight should be an island, not a bump on Hampshire",
    )
    need(grid[47][14] != SEA and grid[47][33] != SEA and grid[48][24] == SEA, "Cotentin and St-Valery should be two headlands with the Seine bay between")

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
