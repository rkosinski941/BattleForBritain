"""Generate a square-grid operational map of Britain and Normandy, 1066.

The silhouette follows the Norman Conquest plate, not its political colours:

- Britain is one tall island. Scotland, north of the campaign, continues the
  same coasts and stays impassable. The playable north is the Northumbrian
  shoulder, not a neck under a gray hat.
- Wales is the western mass. Cornwall is a long arm to the southwest.
  East Anglia bulges east of the Wash. Kent is the southeast corner.
- The Channel is a strait: wide between Cornwall and Brittany, about a
  fair-weather week from St-Valery to Sussex, and only a few cells at Dover.
- The Cotentin is a north-pointing fist west of the Seine bay. Brittany,
  impassable, points west under the western Channel. Maine and Flanders
  continue the French land without wrapping the playable coast.

Playable England is small-grid y <= 45, with y = 46 left as water so
Boulogne can approach Dover. Normandy starts at y >= 47, south of the
latitude src/world.js treats as England. ENGLAND_LAT stays 46 + the
Scotland padding.

Ermine Street is the straight north road London–Lincoln–York. In fair
weather a housecarl spends four ticks on a road cell and five on a town,
with 32 ticks and eight orders a week, and that road is two weeks long.
A fleet step across the Channel is one order; eight steps is one week.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Playable mask. The island is deliberately narrower than the old blob so
# the bulges read. Padding: north Scotland, west Brittany, east Flanders,
# south Maine and Anjou.
W, H = 40, 70
OX, OY = 16, 16
EAST, SOUTH = 8, 4
BIG_W, BIG_H = W + OX + EAST, H + OY + SOUTH

# Small-grid row that src/world.js still treats as the south edge of England
# once the Scotland padding is added. Norman land stays strictly south of it.
ENGLAND_Y = 46

SEA, BEACH, CLEAR, FOREST, HILL, MARSH, RIVER, ROAD, TOWN = range(9)
OUT = 9
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
    OUT: "x",
}
WALKABLE = {CLEAR, FOREST, HILL, MARSH, BEACH, RIVER, ROAD}

# Inclusive west-east spans on the playable mask.
# Spine x=16: York y=16, Lincoln y=23, London y=30. Fourteen road steps.
LAND = {
    # Northumbrian shoulder. Scotland continues these edges.
    1: [(12, 22)],
    2: [(11, 22)],
    3: [(11, 23)],
    4: [(10, 23)],
    5: [(10, 23)],
    # Solway Firth, then Cumbria falling away toward Wales.
    6: [(12, 24)],
    7: [(9, 24)],
    8: [(7, 24)],
    9: [(6, 23)],
    10: [(5, 23)],
    # The Humber bites east of the Vale. Wales is the western mass.
    11: [(3, 22)],
    12: [(2, 20)],
    13: [(2, 19)],
    14: [(2, 21)],
    15: [(2, 22)],
    16: [(1, 23)],
    17: [(1, 23)],
    18: [(1, 24)],
    19: [(1, 24)],
    # Cardigan Bay, a shallow bite in the Welsh west coast.
    20: [(2, 23)],
    21: [(3, 22)],
    22: [(3, 21)],
    # The Wash, east of Lincoln. East Anglia is the bulge south of it.
    23: [(2, 20)],
    24: [(1, 19)],
    25: [(2, 22)],
    26: [(2, 25)],
    27: [(2, 28)],
    28: [(2, 30)],
    29: [(3, 29)],
    # London. The Thames estuary cuts the east coast back.
    30: [(4, 22)],
    31: [(4, 18)],
    32: [(3, 20)],
    # Bristol Channel, open to the western sea around Pembrokeshire.
    33: [(2, 9), (15, 26)],
    34: [(3, 8), (12, 32)],
    35: [(12, 35)],
    36: [(8, 35)],
    37: [(6, 35)],
    # Sussex shore, with Cornwall and the Kent corner projecting south.
    38: [(4, 10), (16, 24), (26, 35)],
    39: [(3, 8), (12, 15), (30, 35)],
    40: [(2, 6), (12, 15), (32, 35)],
    41: [(1, 5), (33, 34)],
    42: [(1, 4)],
    43: [(1, 3)],
    44: [(1, 2)],
    45: [(1, 2)],
    # y=46 is open water on the mask. Boulogne, impassable, is painted there
    # afterwards so the strait can narrow without moving the latitude line.
    # Cotentin fist, wider at the knuckles, Seine bay, St-Valery headland.
    47: [(20, 26)],
    48: [(4, 16), (21, 28)],
    49: [(4, 17), (22, 30)],
    50: [(5, 16), (22, 30)],
    51: [(6, 16), (21, 30)],
    52: [(6, 15), (20, 30)],
    53: [(7, 16), (20, 30)],
    54: [(7, 17), (21, 30)],
    55: [(7, 18), (22, 30)],
    56: [(6, 30)],
    57: [(6, 30)],
    58: [(6, 29)],
    59: [(6, 28)],
    60: [(7, 28)],
    61: [(8, 27)],
    62: [(8, 27)],
}

TOWNS = [
    ("York", 16, 16, 15, "english"),
    ("Durham", 14, 6, 4, "english"),
    ("Lincoln", 16, 23, 6, "english"),
    ("Nottingham", 12, 20, 5, "english"),
    ("Norwich", 25, 28, 5, "english"),
    ("Stamford", 18, 25, 4, "english"),
    ("Oxford", 13, 31, 5, "english"),
    ("London", 16, 30, 25, "english"),
    ("Winchester", 14, 36, 15, "english"),
    ("Canterbury", 24, 36, 8, "english"),
    ("Dover", 35, 40, 8, "english"),
    ("Hastings", 22, 38, 6, "english"),
    ("Pevensey", 19, 38, 6, "english"),
    ("Chichester", 16, 38, 4, "english"),
    ("Exeter", 13, 36, 5, "english"),
    ("Gloucester", 12, 32, 5, "english"),
    ("Wallingford", 15, 30, 4, "english"),
    ("Thetford", 21, 27, 3, "english"),
    ("St-Valery", 22, 47, 4, "norman"),
    ("Bayeux", 11, 55, 3, "norman"),
    ("Caen", 12, 57, 6, "norman"),
    ("Rouen", 26, 57, 8, "norman"),
    ("Dives", 15, 52, 3, "norman"),
]

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

SPINE_X = 16
SPINE_Y0, SPINE_Y1 = 16, 30


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
        if iy == dy or (ix < dx and (ix + 1) * dy <= (iy + 1) * dx):
            x += sx
            ix += 1
        else:
            y += sy
            iy += 1
        pts.append((x, y))
    return pts


def neighbors(x, y, w=W, h=H):
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        xx, yy = x + dx, y + dy
        if 0 <= xx < w and 0 <= yy < h:
            yield xx, yy


def fill_land(grid):
    for y, spans in LAND.items():
        for west, east in spans:
            for x in range(west, east + 1):
                if not (0 <= x < W and 0 <= y < H):
                    raise SystemExit(f"land span {x},{y} is off the playable mask")
                grid[y][x] = CLEAR


def apply_beaches(grid):
    for y in range(H):
        for x in range(W):
            if grid[y][x] not in (CLEAR, HILL, FOREST, MARSH):
                continue
            sea_n = y > 0 and grid[y - 1][x] == SEA
            sea_s = y + 1 < H and grid[y + 1][x] == SEA
            sea_e = x + 1 < W and grid[y][x + 1] == SEA
            sea_w = x > 0 and grid[y][x - 1] == SEA
            # Channel-facing English shore, including the Cornish arm.
            if 36 <= y <= 45 and sea_s:
                grid[y][x] = BEACH
            # Kent's corner, sea to the east as well as the south.
            elif x >= 26 and 36 <= y <= 42 and (sea_s or sea_e):
                grid[y][x] = BEACH
            # Norman shore facing England, and the Cotentin fist.
            elif y >= 47 and (sea_n or (x <= 18 and (sea_e or sea_w))):
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

    # Inland only. The coastline is the mask.
    stamp(grid, 16, 4, 2, 2, HILL)  # Cheviots
    stamp(grid, 10, 15, 2, 4, HILL)  # Pennines, west of the Vale
    stamp(grid, 6, 20, 2, 4, HILL)  # Welsh massif
    stamp(grid, 14, 32, 2, 1, HILL)  # Cotswolds
    stamp(grid, 11, 36, 2, 1, HILL)  # Dartmoor
    stamp(grid, 20, 36, 3, 1, HILL)  # Downs
    stamp(grid, 12, 54, 3, 2, HILL)  # Norman bocage
    stamp(grid, 22, 36, 2, 1, FOREST)  # the Weald
    stamp(grid, 12, 37, 2, 1, FOREST)  # New Forest
    stamp(grid, 13, 20, 2, 2, FOREST)  # Sherwood, west of Ermine Street
    stamp(grid, 6, 18, 2, 2, FOREST)  # Welsh woods
    stamp(grid, 24, 27, 2, 1, FOREST)  # East Anglia
    stamp(grid, 24, 58, 2, 1, FOREST)  # Norman woods
    stamp(grid, 20, 25, 2, 1, MARSH)  # the Fens
    stamp(grid, 13, 35, 2, 1, MARSH)  # Somerset levels
    stamp(grid, 22, 37, 2, 1, MARSH)  # Romney
    stamp(grid, 20, 15, 1, 1, MARSH)  # Humber levels

    apply_beaches(grid)

    towns = []
    for name, x, y, value, owner in TOWNS:
        if not (0 <= x < W and 0 <= y < H) or grid[y][x] == SEA:
            raise SystemExit(f"{name} ({x},{y}) is not on land")
        grid[y][x] = TOWN
        towns.append(
            {"name": name, "x": x, "y": y, "value": value, "owner": owner, "port": False}
        )

    # Rivers reach the sea and stay off the Ermine column except at the towns.
    paint_line(
        grid,
        [town_xy(towns, "London"), (20, 30), (22, 30)],
        RIVER,
        WALKABLE,
    )
    paint_line(grid, [town_xy(towns, "York"), (23, 16)], RIVER, WALKABLE)
    paint_line(
        grid,
        [(8, 28), (10, 30), town_xy(towns, "Gloucester"), (12, 33)],
        RIVER,
        WALKABLE,
    )

    roads = [
        ["London", "Lincoln", "York"],
        ["York", "Durham"],
        ["Dover", (33, 38), (30, 37), "Canterbury", (20, 34), (18, 32), "London"],
        ["London", "Wallingford", "Oxford"],
        ["Oxford", "Gloucester"],
        ["Exeter", (12, 36), "Winchester", (18, 36), (18, 32), "London"],
        ["Chichester", "Pevensey", "Hastings", (24, 37), (26, 37), "Canterbury", (30, 38), (33, 39), "Dover"],
        ["Winchester", "Chichester"],
        ["London", (18, 28), "Thetford", "Norwich"],
        ["Nottingham", "Lincoln"],
        ["Caen", "Bayeux"],
        ["Dives", (12, 54), "Caen"],
        ["Caen", "Rouen"],
        ["Rouen", (28, 52), (24, 48), "St-Valery"],
        ["Dives", (12, 56), (24, 56), (24, 48), "St-Valery"],
    ]
    for path in roads:
        coords = [town_xy(towns, p) if isinstance(p, str) else p for p in path]
        paint_road(grid, coords)

    # The Seine is painted after the roads so the Caen–Rouen pavement cannot
    # seal Rouen off from the bay.
    paint_line(
        grid,
        [(27, 57), (27, 54), (21, 54)],
        RIVER,
        WALKABLE,
    )

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


def sea_reachable(grid, x, y):
    """How much open sea a ship can reach from a town's water."""
    from collections import deque

    q = deque()
    seen = set()
    for xx, yy in neighbors(x, y):
        if grid[yy][xx] in (SEA, BEACH, RIVER):
            q.append((xx, yy))
            seen.add((xx, yy))
    nsea = 0
    while q:
        cx, cy = q.popleft()
        if grid[cy][cx] == SEA:
            nsea += 1
        for xx, yy in neighbors(cx, cy):
            if (xx, yy) in seen:
                continue
            if grid[yy][xx] in (SEA, BEACH, RIVER):
                seen.add((xx, yy))
                q.append((xx, yy))
    return nsea


def _xs(grid, y):
    return [x for x in range(W) if grid[y][x] != SEA]


def _components(grid, pred):
    from collections import deque

    seen = set()
    parts = []
    for y in range(H):
        for x in range(W):
            if (x, y) in seen or not pred(x, y):
                continue
            q = deque([(x, y)])
            seen.add((x, y))
            cells = [(x, y)]
            while q:
                cx, cy = q.popleft()
                for xx, yy in neighbors(cx, cy):
                    if (xx, yy) in seen or not pred(xx, yy):
                        continue
                    seen.add((xx, yy))
                    q.append((xx, yy))
                    cells.append((xx, yy))
            parts.append(cells)
    return parts


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
        need(weeks == 2, f"London–York road is {len(costs)} steps, {weeks} fair weeks (want 2)")
        on_road = road_costs(grid, (london["x"], london["y"]), (lincoln["x"], lincoln["y"]))
        need(on_road is not None, "Lincoln is off Ermine Street")

    hastings, pevensey, dover = by["Hastings"], by["Pevensey"], by["Dover"]
    need(pevensey["x"] < hastings["x"] < dover["x"], "Sussex shore should run Pevensey, Hastings, Dover west to east")
    for name in ("Pevensey", "Hastings", "Chichester"):
        t = by[name]
        sea_s = t["y"] + 1 < H and grid[t["y"] + 1][t["x"]] == SEA
        need(sea_s, f"{name} should have open sea immediately south, facing the Channel")

    stv = by["St-Valery"]
    dives = by["Dives"]
    need(stv["y"] > hastings["y"], "St-Valery should lie across the Channel from Hastings")
    need(abs(stv["x"] - hastings["x"]) <= 4, "St-Valery should stand opposite Hastings")
    need(stv["y"] > ENGLAND_Y and dives["y"] > ENGLAND_Y, "Norman ports must stay south of the England latitude line")

    for t in towns:
        if t["owner"] == "norman":
            need(t["y"] > ENGLAND_Y, f"{t['name']} is on the England side of the latitude line")
        else:
            need(t["y"] <= ENGLAND_Y, f"{t['name']} is south of the England latitude line")

    sea_between = sum(1 for y in range(hastings["y"] + 1, stv["y"]) if grid[y][hastings["x"]] == SEA)
    need(sea_between >= 7, f"the Channel on the Hastings meridian is only {sea_between} rows of sea")

    win = by["Winchester"]
    need(win["x"] < london["x"] and win["y"] > london["y"], "Winchester should sit in Wessex, southwest of London")
    need(dover["x"] > by["Canterbury"]["x"], "Dover should be east of Canterbury, on the Kent corner")
    need(dover["x"] + 1 < W and grid[dover["y"]][dover["x"] + 1] == SEA, "Dover should have sea immediately east")
    need(dover["y"] + 1 < H and grid[dover["y"] + 1][dover["x"]] == SEA, "Dover should have sea immediately south")

    steps = channel_steps(
        grid,
        (stv["x"], stv["y"]),
        [(pevensey["x"], pevensey["y"]), (hastings["x"], hastings["y"])],
    )
    need(steps is not None and 6 <= steps <= 8, f"Channel crossing is {steps} fleet steps (want 6..8, one fair week)")

    for name in REQUIRED_PORTS:
        need(by[name]["port"], f"{name} is not a port")
        reach = sea_reachable(grid, by[name]["x"], by[name]["y"])
        need(reach >= 12, f"{name} does not open onto the sea (reachable sea {reach})")

    # --- silhouette, on the playable mask ---
    english = [(x, y) for y in range(ENGLAND_Y + 1) for x in range(W) if grid[y][x] != SEA]
    need(bool(english), "England missing")
    south_y = max(y for _, y in english)
    tip = [x for x, y in english if y == south_y]
    need(south_y >= hastings["y"] + 5, f"Cornwall only reaches y={south_y}, not a southwestern arm")
    need(max(tip) <= 6 and max(tip) - min(tip) <= 2, f"Cornwall tip {tip} should be a narrow southwestern point")
    arm = []
    for y in range(hastings["y"] + 1, south_y + 1):
        xs = _xs(grid, y)
        if not xs:
            continue
        run = [xs[0]]
        for x in xs[1:]:
            if x == run[-1] + 1:
                run.append(x)
            else:
                break
        if max(run) <= 10 and min(run) <= 4:
            arm.append(y)
    need(len(arm) >= 6, f"Cornwall arm is only {len(arm)} rows south of Sussex")

    wales_rows = list(range(16, 24))
    wales_west = min(min(_xs(grid, y)) for y in wales_rows)
    north_west = min(min(_xs(grid, y)) for y in range(1, 6))
    need(wales_west <= 4, f"Wales west edge is x={wales_west}, not a western mass")
    need(north_west - wales_west >= 7, "Wales should stand well west of Northumbria")
    wales_width = max(max(_xs(grid, y)) - min(_xs(grid, y)) for y in wales_rows)
    need(wales_width >= 18, f"Wales latitude is only {wales_width} cells wide")

    wash_east = min(max(_xs(grid, y)) for y in range(23, 26))
    anglia_east = max(max(_xs(grid, y)) for y in range(26, 30))
    thames_east = min(max(_xs(grid, y)) for y in range(30, 33))
    need(anglia_east >= wash_east + 7, f"East Anglia ({anglia_east}) does not bulge east of the Wash ({wash_east})")
    need(anglia_east >= thames_east + 4, f"the Thames ({thames_east}) should cut back west of East Anglia ({anglia_east})")

    kent_east = max(max(_xs(grid, y)) for y in range(38, 42))
    need(kent_east >= anglia_east + 3, f"Kent ({kent_east}) should project east of East Anglia ({anglia_east})")
    need(dover["x"] >= kent_east - 1 and dover["y"] >= 39, "Dover should sit on the southeastern corner")

    # Bristol Channel: a west-open inlet, not a lake.
    channel_rows = []
    for y in range(32, 37):
        row = grid[y]
        seen_land = False
        seen_gap = False
        for x in range(W):
            if row[x] == SEA and seen_land:
                seen_gap = True
            elif row[x] != SEA and seen_gap:
                channel_rows.append(y)
                break
            elif row[x] != SEA:
                seen_land = True
    need(len(channel_rows) >= 2, "the Bristol Channel should separate South Wales from Devon")
    mouth = any(grid[y][0] == SEA and any(grid[y][x] != SEA for x in range(W)) for y in range(33, 36))
    need(mouth, "the Bristol Channel should open on the western sea")

    # Isle of Wight: a small island in the Solent, west of the Sussex shore.
    parts = _components(grid, lambda x, y: grid[y][x] != SEA and y <= ENGLAND_Y)
    parts.sort(key=len, reverse=True)
    need(len(parts) == 2, f"England should be the main island plus Wight, found {len(parts)} pieces")
    if len(parts) >= 2:
        wight = parts[1]
        wx = [x for x, _ in wight]
        wy = [y for _, y in wight]
        need(3 <= len(wight) <= 16, f"Wight should be a small island, has {len(wight)} cells")
        need(max(wy) > hastings["y"] and max(wx) < hastings["x"], "Wight should lie in the Solent, southwest of Hastings")

    norman_parts = _components(grid, lambda x, y: grid[y][x] != SEA and y > ENGLAND_Y)
    need(len(norman_parts) == 1, f"Normandy should be one coast, found {len(norman_parts)} pieces")

    # Cotentin: a bulky peninsula pointing north, sea on both sides, Seine bay to the east.
    fist_rows = []
    for y in range(47, 58):
        xs = _xs(grid, y)
        if not xs:
            continue
        runs = []
        start = prev = xs[0]
        for x in xs[1:]:
            if x == prev + 1:
                prev = x
            else:
                runs.append((start, prev))
                start = prev = x
        runs.append((start, prev))
        west_run = runs[0]
        if west_run[1] < 20 and (west_run[0] == 0 or grid[y][west_run[0] - 1] == SEA):
            if west_run[1] + 1 < W and grid[y][west_run[1] + 1] == SEA:
                fist_rows.append((y, west_run))
    need(len(fist_rows) >= 6, f"Cotentin is only {len(fist_rows)} rows of peninsula")
    if fist_rows:
        tip_y, (tip_w, tip_e) = fist_rows[0]
        tip_width = tip_e - tip_w + 1
        need(tip_width >= 8, f"Cotentin tip is {tip_width} cells wide, not a fist")
        need(by["Caen"]["y"] - tip_y >= 6, "Cotentin should point well north of Caen")
        need(tip_y <= 49, f"Cotentin tip at y={tip_y} does not reach toward England")
        bay = any(grid[tip_y][x] == SEA for x in range(tip_e + 1, stv["x"]))
        need(bay, "the Seine bay should separate the Cotentin from the St-Valery shore")
        need(all(grid[tip_y - 1][x] == SEA for x in range(tip_w, tip_e + 1)), "sea should lie immediately north of the Cotentin")

    if errors:
        raise SystemExit("map check failed:\n- " + "\n- ".join(errors))
    return {"ermine_steps": len(costs) if costs else None, "ermine_weeks": weeks, "channel_steps": steps}


def _paint_out(grid, spans):
    """Paint impassable land. Coordinates are small-grid, and may fall in the padding."""
    painted = 0
    for y, ranges in spans.items():
        by = y + OY
        if not (0 <= by < BIG_H):
            raise SystemExit(f"out-of-play row {y} is off the map")
        for west, east in ranges:
            for x in range(west, east + 1):
                bx = x + OX
                if not (0 <= bx < BIG_W):
                    raise SystemExit(f"out-of-play cell {x},{y} is off the map")
                if grid[by][bx] == SEA:
                    grid[by][bx] = OUT
                    painted += 1
    return painted


def _shift_towns(towns):
    moved = []
    for t in towns:
        copy = dict(t)
        copy["x"] += OX
        copy["y"] += OY
        moved.append(copy)
    return moved


def outline_spans():
    """Scotland, Brittany, Maine, and Flanders in small-grid coordinates.

    Negative coordinates fall in the padding. Painting only replaces sea, so
    the playable coast, the Seine bay, and the open Channel stay as they are.
    """
    # Scotland continues the Northumbrian shoulder (y=1 is x=12..22), widens
    # slightly through the Highlands, then tapers to a northern cape.
    scotland = {
        -15: [(18, 20)],
        -14: [(17, 21)],
        -13: [(16, 22)],
        -12: [(15, 23)],
        -11: [(14, 24)],
        -10: [(13, 25)],
        -9: [(12, 26)],
        -8: [(12, 26)],
        -7: [(11, 26)],
        -6: [(11, 25)],
        -5: [(11, 25)],
        -4: [(11, 24)],
        -3: [(11, 24)],
        -2: [(11, 23)],
        -1: [(11, 23)],
        0: [(11, 23)],
    }

    # Brittany points west under the wide western Channel. The western rows
    # are the narrow end; the base, further east, joins Maine. Sea stays
    # south of the point. The Gulf of Saint-Malo stays open.
    brittany = {
        60: [(2, 6)],
        61: [(-2, 6)],
        62: [(-6, 7)],
        63: [(-10, 7)],
        64: [(-13, 6)],
        65: [(-15, 5)],
        66: [(-15, 6)],
        67: [(-12, 7)],
        68: [(-8, 8)],
        69: [(-4, 8)],
    }

    # Interior France abuts Normandy on the south and Brittany at its base.
    # It does not wrap the Cotentin or fill in the sea south of the Breton point.
    maine = {}
    for y in range(63, 70):
        maine[y] = [(8, 36)]
    for y in range(70, H + SOUTH):
        maine[y] = [(0, 36)]

    # Flanders and Boulogne. The headland comes north toward Dover; the rest
    # continues the continental coast east of the Somme.
    flanders = {
        44: [(30, 32 + EAST)],
        45: [(28, 32 + EAST)],
        46: [(26, 32 + EAST)],
        47: [(27, 32 + EAST)],
        48: [(29, 32 + EAST)],
        49: [(31, 32 + EAST)],
        52: [(31, 32 + EAST)],
        56: [(31, 32 + EAST)],
        60: [(30, 32 + EAST)],
    }
    # Fill the eastern padding beside Flanders so the coast is a region.
    for y in range(46, 63):
        flanders.setdefault(y, [])
        flanders[y] = list(flanders[y]) + [(34, 32 + EAST)]
    return scotland, brittany, maine, flanders


def compose(small, towns):
    """Copy the playable mask onto a larger map and outline the rest."""
    big = [[SEA for _ in range(BIG_W)] for _ in range(BIG_H)]
    for y in range(H):
        for x in range(W):
            big[y + OY][x + OX] = small[y][x]

    scotland, brittany, maine, flanders = outline_spans()
    counts = {
        "scotland": _paint_out(big, scotland),
        "brittany": _paint_out(big, brittany),
        "maine": _paint_out(big, maine),
        "flanders": _paint_out(big, flanders),
    }
    moved = _shift_towns(towns)
    check_outline(small, big, moved, counts)
    return big, moved, counts


def _gap_south_of_england(big, x):
    """Sea cells between English land and the next French shore in this column."""
    limit = OY + ENGLAND_Y
    last = None
    for y in range(limit + 1):
        if 0 <= x < BIG_W and big[y][x] not in (SEA, OUT):
            last = y
    if last is None:
        return None
    sea = 0
    y = last + 1
    while y < BIG_H and big[y][x] == SEA:
        sea += 1
        y += 1
    if y >= BIG_H:
        return None
    return sea


def check_outline(small, big, towns, counts):
    import re
    from collections import deque

    errors = []

    def need(cond, msg):
        if not cond:
            errors.append(msg)

    for y in range(H):
        for x in range(W):
            src = small[y][x]
            dst = big[y + OY][x + OX]
            if src != SEA and dst != src:
                errors.append(f"playable cell changed at {x},{y}")
                break
            if src == SEA and dst not in (SEA, OUT):
                errors.append(f"sea beside the playable mask became {dst} at {x},{y}")
                break

    for name, n in counts.items():
        need(n >= 40, f"{name} outline is only {n} cells")

    # Scotland meets the shoulder on the same coasts, with no sea gap and no neck.
    border = OY + 1
    shoulder = [x for x in range(BIG_W) if big[border][x] not in (SEA, OUT)]
    above = [x for x in range(BIG_W) if big[border - 1][x] == OUT]
    need(len(shoulder) >= 10, "the playable north should be a shoulder, not a neck")
    if shoulder and above:
        need(min(above) >= min(shoulder) - 2 and max(above) <= max(shoulder) + 2, "Scotland's coast should continue the Northumbrian shoulder")
        need(any(x in set(above) for x in shoulder) or any(x - 1 in set(above) or x + 1 in set(above) for x in shoulder), "Scotland does not touch the island")
        joined = any(big[border - 1][x] == OUT for x in shoulder)
        need(joined, "a sea gap separates Scotland from England")

    # The far north is a cape of the same island, not a blob sitting on the border.
    cape_y = 1
    cape = [x for x in range(BIG_W) if big[cape_y][x] == OUT]
    need(bool(cape) and max(cape) - min(cape) <= 6, "Scotland should taper to a northern cape")

    by = {t["name"]: t for t in towns}
    dover_x = by["Dover"]["x"]
    hastings_x = by["Hastings"]["x"]
    # Cornwall's tip is the southernmost English land.
    limit = OY + ENGLAND_Y
    south_cells = [
        (x, y)
        for y in range(limit + 1)
        for x in range(BIG_W)
        if big[y][x] not in (SEA, OUT)
    ]
    tip_y = max(y for _, y in south_cells)
    tip_xs = [x for x, y in south_cells if y == tip_y]
    corn_x = tip_xs[0]

    gap_dover = _gap_south_of_england(big, dover_x)
    gap_sussex = _gap_south_of_england(big, hastings_x)
    gap_west = _gap_south_of_england(big, corn_x)
    need(gap_dover is not None and gap_dover <= 3, f"Dover strait gap is {gap_dover}, want <= 3")
    need(gap_sussex is not None and 7 <= gap_sussex <= 10, f"Sussex Channel gap is {gap_sussex}, want 7..10")
    need(gap_west is not None and gap_west >= 12, f"western Channel gap is {gap_west}, want >= 12")
    need(gap_dover < gap_sussex < gap_west, "the Channel should narrow toward Dover")

    # Brittany: west of the Cotentin, the point facing west, sea to its north.
    cotentin_west = OX + 6
    brit_cells = [
        (x, y)
        for y in range(BIG_H)
        for x in range(BIG_W)
        if big[y][x] == OUT and x < cotentin_west and y > OY + 50
    ]
    need(len(brit_cells) >= 40, "Brittany outline missing")
    if brit_cells:
        tip = min(x for x, _ in brit_cells)
        base = max(x for x, _ in brit_cells)
        need(base - tip >= 10, "Brittany should extend west as a peninsula")
        tip_rows = {y for x, y in brit_cells if x <= tip + 1}
        mid_x = tip + 8
        mid_rows = {y for x, y in brit_cells if abs(x - mid_x) <= 1}
        need(len(tip_rows) <= len(mid_rows), "Brittany's western end should be the narrow point")
        north_of_tip = min(y for x, y in brit_cells if x == tip)
        sea_north = 0
        y = north_of_tip - 1
        while y >= 0 and big[y][tip] == SEA:
            sea_north += 1
            y -= 1
        need(sea_north >= 8, "Brittany should lie under the Channel, pointing west, with sea to the north")
        # Gulf of Saint-Malo: sea between Brittany and the Cotentin.
        gulf = False
        for y in range(OY + 48, OY + 57):
            if any(big[y][x] == SEA for x in range(OX + 1, OX + 6)):
                gulf = True
        need(gulf, "the Gulf of Saint-Malo should keep Brittany off the Cotentin")

    # Maine abuts Normandy on the south. Flanders abuts the Picard coast on the east.
    need(any(big[OY + 64][x] == OUT for x in range(OX + 10, OX + 30)), "Maine should continue south of Normandy")
    need(any(big[OY + 45][x] == OUT for x in range(OX + 28, OX + 36)), "Boulogne should stand across the strait from Dover")

    # Impassable land must not seal the Seine bay or the water north of the fist.
    dives = by["Dives"]
    need(big[dives["y"] + 0][dives["x"] + 1] in (SEA, BEACH) or big[dives["y"] - 1][dives["x"]] in (SEA, BEACH, RIVER), "Dives lost the Seine bay")
    fist_y = OY + 48
    need(any(big[fist_y - 1][x] == SEA for x in range(OX + 6, OX + 15)), "out-of-play land swallowed the north side of the Cotentin")

    # Boulogne joins the French shore rather than floating in the strait.
    cape = None
    for y in range(OY + 44, OY + 47):
        for x in range(BIG_W - 1, OX + 20, -1):
            if big[y][x] == OUT:
                cape = (x, y)
                break
        if cape:
            break
    need(cape is not None, "Boulogne headland missing")
    if cape:
        seen = {cape}
        q = deque([cape])
        joined = False
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if not (0 <= xx < BIG_W and 0 <= yy < BIG_H):
                    continue
                if big[yy][xx] not in (SEA, OUT):
                    joined = True
                if big[yy][xx] == OUT and (xx, yy) not in seen:
                    seen.add((xx, yy))
                    q.append((xx, yy))
        need(joined, "Boulogne should join the French shore")

    for name in REQUIRED_PORTS:
        t = by[name]
        wet = False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, yy = t["x"] + dx, t["y"] + dy
            if 0 <= xx < BIG_W and 0 <= yy < BIG_H and big[yy][xx] in (SEA, BEACH, RIVER):
                wet = True
        need(wet, f"{name} lost its water when the outline was added")

    root = Path(__file__).resolve().parents[1]
    world = (root / "src" / "world.js").read_text(encoding="utf-8")
    match = re.search(r"ENGLAND_LAT = (\d+)", world)
    need(
        match is not None and int(match.group(1)) == ENGLAND_Y + OY,
        "ENGLAND_LAT in src/world.js must equal the England row plus the Scotland padding",
    )
    for t in towns:
        if t["owner"] == "norman":
            need(t["y"] > ENGLAND_Y + OY, f"{t['name']} is on the England side of the shifted latitude line")

    if errors:
        raise SystemExit("outline check failed:\n- " + "\n- ".join(errors))
    return {"dover": gap_dover, "sussex": gap_sussex, "west": gap_west}


def main():
    grid, towns = build()
    stats = validate(grid, towns)
    big, moved, counts = compose(grid, towns)
    gaps = check_outline(grid, big, moved, counts)
    lines = ["".join(CH[c] for c in row) for row in big]
    debug = "--debug" in sys.argv
    if debug:
        ruler = "   " + "".join(str((x // 10) % 10) for x in range(BIG_W))
        print(ruler)
        lines = [f"{y:02d} {line}" for y, line in enumerate(lines)]
    print("\n".join(lines))
    print("--- towns ---")
    for t in moved:
        print(f"{t['name']:14} {t['x']:2},{t['y']:2} port={t['port']} {CH[big[t['y']][t['x']]]}")
    print(
        f"Ermine Street {stats['ermine_steps']} steps, "
        f"{stats['ermine_weeks']} fair weeks for housecarls. "
        f"Channel {stats['channel_steps']} fleet steps, St-Valery to Sussex."
    )
    print(
        "Channel gaps: "
        f"Dover {gaps['dover']}, Sussex {gaps['sussex']}, west {gaps['west']}."
    )
    print(
        "Out of play: "
        + ", ".join(f"{name} {n}" for name, n in counts.items())
        + f". Map {BIG_W}x{BIG_H}."
    )
    out = {
        "w": BIG_W,
        "h": BIG_H,
        "terrain": [cell for row in big for cell in row],
        "towns": moved,
    }
    dest = Path(__file__).resolve().parents[1] / "data" / "map.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out), encoding="utf-8")
    print("wrote", dest)


if __name__ == "__main__":
    main()
