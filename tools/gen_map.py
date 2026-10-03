"""Generate a square-grid operational map of Britain and Normandy, 1066.

The playable land mask follows the Norman Conquest reference: a long island
(Scotland tip, Wales bulging west, Cornwall to the southwest), a broad Channel,
and Normandy with the Cotentin thumb west of a Seine bay and Saint-Valery
opposite Hastings. On that mask England stays on y <= 43. Rows 44-46 are open
water. Normandy and Ponthieu start at y >= 47, south of the latitude
src/world.js treats as England.

Scotland, Brittany, Maine, Anjou, and Flanders are drawn around that mask as
out-of-play land (terrain 9). They are hatched and impassable. The playable
cells, towns, roads, and the Channel band are copied through unchanged, then
shifted by the padding that makes room for the outline. ENGLAND_LAT in
src/world.js moves with that north padding.

Ermine Street is the straight north road London–Lincoln–York. In fair weather
a housecarl spends four ticks on a road cell and five on a town, with 32 ticks
and eight orders a week, and that road is two weeks long.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W, H = 46, 64

# Padding around the playable mask. North is Scotland, west is Brittany,
# east is Flanders and Boulogne, south is Maine and Anjou.
OX, OY = 14, 16
EAST, SOUTH = 16, 18
BIG_W, BIG_H = W + OX + EAST, H + OY + SOUTH

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

# Inclusive west-east spans, traced from the reference coastline.
# Spine x=26: York y=16, Lincoln y=22, London y=30.
LAND = {
    # Northern shoulder. Wide enough that out-of-play Scotland can continue
    # the same coasts instead of sitting on a four-cell neck.
    1: [(23, 30)],
    2: [(22, 31)],
    3: [(22, 32)],
    4: [(22, 32)],
    5: [(21, 33)],
    6: [(20, 33)],
    7: [(19, 34)],
    8: [(18, 34)],
    9: [(17, 35)],
    # Solway Firth, then the Cumbrian shoulder.
    10: [(20, 35)],
    11: [(16, 35)],
    12: [(14, 35)],
    13: [(15, 35)],
    14: [(12, 35)],
    # Wales bulges west, one cell shy of the previous mask. The Humber is a
    # short funnel east of York.
    15: [(9, 35)],
    16: [(7, 31)],
    17: [(5, 30)],
    18: [(4, 35)],
    19: [(4, 36)],
    20: [(4, 36)],
    # The Wash, west of the later East Anglian bulge. Lincoln is x=26.
    21: [(4, 33)],
    22: [(4, 29)],
    23: [(4, 28)],
    24: [(4, 30)],
    25: [(4, 36)],
    # East Anglia, then the Thames estuary east of London.
    26: [(4, 40)],
    27: [(4, 40)],
    28: [(5, 38)],
    29: [(5, 35)],
    30: [(5, 32)],
    31: [(6, 31)],
    # Bristol Channel: South Wales, open water, Somerset, then Kent.
    32: [(5, 13), (18, 33)],
    33: [(6, 11), (20, 39)],
    34: [(14, 41)],
    # Devon closes the channel. The east end is Dover's cliff.
    35: [(8, 39)],
    36: [(5, 37)],
    # Sussex shore. Sea is immediately south of the eastern span.
    37: [(3, 14), (19, 34)],
    # Cornwall continues southwest. The second span is the Isle of Wight.
    # Row 43 lengthens the point without entering the open Channel.
    38: [(2, 12)],
    39: [(2, 10), (22, 26)],
    40: [(3, 8), (23, 25)],
    41: [(4, 7)],
    42: [(5, 6)],
    43: [(4, 6)],
    # 44-46 the Manche: open water from Cornwall's point to Ponthieu.
    # Cotentin thumb, Seine bay, and the Ponthieu shore at St-Valery.
    47: [(16, 21), (30, 37)],
    48: [(15, 23), (29, 39)],
    49: [(14, 25), (29, 40)],
    50: [(8, 13), (16, 26), (30, 41)],
    51: [(6, 42)],
    52: [(6, 42)],
    53: [(7, 41)],
    54: [(8, 40)],
    55: [(9, 39)],
    56: [(11, 37)],
    57: [(13, 35)],
    58: [(15, 33)],
    59: [(17, 31)],
}

TOWNS = [
    ("York", 26, 16, 15, "english"),
    ("Durham", 22, 8, 4, "english"),
    ("Lincoln", 26, 22, 6, "english"),
    ("Nottingham", 20, 21, 5, "english"),
    ("Norwich", 38, 27, 5, "english"),
    ("Stamford", 27, 25, 4, "english"),
    ("Oxford", 20, 31, 5, "english"),
    ("London", 26, 30, 25, "english"),
    ("Winchester", 22, 35, 15, "english"),
    ("Canterbury", 34, 35, 8, "english"),
    ("Dover", 41, 34, 8, "english"),
    ("Hastings", 32, 37, 6, "english"),
    ("Pevensey", 27, 37, 6, "english"),
    ("Chichester", 22, 37, 4, "english"),
    ("Exeter", 8, 37, 5, "english"),
    ("Gloucester", 20, 32, 5, "english"),
    ("Wallingford", 22, 31, 4, "english"),
    ("Thetford", 34, 26, 3, "english"),
    ("St-Valery", 32, 47, 4, "norman"),
    ("Bayeux", 18, 51, 3, "norman"),
    ("Caen", 22, 54, 6, "norman"),
    ("Rouen", 33, 55, 8, "norman"),
    ("Dives", 24, 49, 3, "norman"),
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
SPINE_X = 26
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
            # South coast facing the Channel, including Cornwall and Wight.
            if 36 <= y <= 43 and sea_s:
                grid[y][x] = BEACH
            # Dover's cliff, east and south.
            elif 33 <= y <= 36 and x >= 36 and (sea_s or sea_e):
                grid[y][x] = BEACH
            # Norman, Cotentin, and Ponthieu shore facing the Channel.
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

    # Uplands and woods sit inland. The coastline is the mask, not these stamps.
    stamp(grid, 26, 4, 2, 2, HILL)  # Cheviots
    stamp(grid, 18, 13, 3, 5, HILL)  # Pennines, west of the Vale of York
    stamp(grid, 8, 20, 3, 5, HILL)  # Welsh massif
    stamp(grid, 16, 33, 2, 1, HILL)  # Cotswolds
    stamp(grid, 10, 36, 2, 1, HILL)  # Dartmoor
    stamp(grid, 28, 36, 4, 1, HILL)  # Downs
    stamp(grid, 24, 55, 5, 2, HILL)  # Norman bocage

    stamp(grid, 28, 36, 3, 1, FOREST)  # the Weald
    stamp(grid, 16, 36, 2, 1, FOREST)  # New Forest
    stamp(grid, 22, 20, 2, 2, FOREST)  # Sherwood, west of Ermine Street
    stamp(grid, 8, 24, 2, 2, FOREST)  # Welsh woods
    stamp(grid, 36, 26, 2, 1, FOREST)  # East Anglia
    stamp(grid, 28, 54, 3, 2, FOREST)  # Norman woods

    stamp(grid, 30, 23, 2, 1, MARSH)  # the Fens, east of Ermine Street
    stamp(grid, 12, 35, 2, 1, MARSH)  # Somerset levels
    stamp(grid, 30, 36, 2, 1, MARSH)  # Romney Marsh
    stamp(grid, 29, 17, 1, 1, MARSH)  # Humber levels

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
        [
            town_xy(towns, "Gloucester"),
            (22, 31),
            town_xy(towns, "Oxford"),
            town_xy(towns, "Wallingford"),
            town_xy(towns, "London"),
            (32, 30),
        ],
        RIVER,
        WALKABLE,
    )
    paint_line(grid, [town_xy(towns, "York"), (31, 16)], RIVER, WALKABLE)
    paint_line(
        grid,
        [(10, 28), (18, 30), (20, 31), town_xy(towns, "Gloucester"), (17, 32)],
        RIVER,
        WALKABLE,
    )
    # East of the road from Rouen to St-Valery, so the pavement does not erase it.
    paint_line(grid, [(34, 55), (36, 55), (36, 48), (37, 47)], RIVER, WALKABLE)
    paint_line(grid, [(33, 47), (33, 50)], RIVER, WALKABLE)  # Somme

    roads = [
        ["London", "Lincoln", "York"],
        ["York", "Durham"],
        ["Dover", (39, 34), (36, 35), "Canterbury", (30, 33), (27, 31), "London"],
        ["London", "Wallingford", "Oxford"],
        ["Oxford", "Gloucester"],
        ["Exeter", (10, 36), (22, 36), "Winchester", (22, 32), "London"],
        ["Chichester", "Pevensey", "Hastings", (34, 36), (37, 35), (39, 34), "Dover"],
        ["Winchester", "Chichester"],
        ["London", (28, 28), "Thetford", "Norwich"],
        ["Nottingham", "Lincoln"],
        ["Caen", "Bayeux"],
        ["Dives", "Caen"],
        ["Caen", "Rouen"],
        ["Rouen", (32, 50), "St-Valery"],
        ["Dives", (24, 52), (32, 52), "St-Valery"],
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
    need(stv["y"] > 46 and dives["y"] > 46, "Norman ports must stay south of the England latitude line")

    # The Manche is a band of open water, not a one-row ditch.
    for y in range(44, 47):
        for x in range(W):
            if grid[y][x] != SEA:
                errors.append(f"land in the Channel at {x},{y}")
                break
    sea_between = sum(1 for y in range(hastings["y"] + 1, stv["y"]) if grid[y][hastings["x"]] == SEA)
    need(sea_between >= 7, f"the Channel on the Hastings meridian is only {sea_between} rows of sea")

    for t in towns:
        if t["owner"] == "norman":
            need(t["y"] > 46, f"{t['name']} is on the England side of the latitude line")

    win = by["Winchester"]
    need(win["x"] < london["x"] and win["y"] > london["y"], "Winchester should sit in Wessex, southwest of London")
    need(dover["x"] > by["Canterbury"]["x"], "Dover should be east of Canterbury, on the Kent corner")

    steps = channel_steps(
        grid,
        (stv["x"], stv["y"]),
        [(pevensey["x"], pevensey["y"]), (hastings["x"], hastings["y"])],
    )
    need(steps is not None and steps <= 8, f"Channel crossing is {steps} fleet steps (want <= 8)")

    for name in REQUIRED_PORTS:
        need(by[name]["port"], f"{name} is not a port")

    # Shape locks taken from the reference, not from the previous notch list.
    need(bool(_xs(grid, 1)) and max(_xs(grid, 1)) - min(_xs(grid, 1)) < 8, "Scotland should come to a narrow northern tip")
    wales = min((x for y in range(16, 21) for x in _xs(grid, y)), default=99)
    need(wales <= 4, "Wales should bulge to the western sea")
    need(max(_xs(grid, 23)) <= 30 and max(_xs(grid, 27)) >= 38, "the Wash should bite, and East Anglia should bulge east of it")
    need(max(_xs(grid, 30)) <= 33 and max(_xs(grid, 27)) >= 38, "the Thames should open east of London")
    need(grid[32][8] != SEA and grid[32][16] == SEA and grid[32][22] != SEA, "the Bristol Channel should separate South Wales from Somerset")
    corn = _xs(grid, 42)
    need(bool(corn) and min(corn) <= 6 and max(corn) <= 10, "Cornwall should be a narrow southwestern point")
    need(grid[39][24] != SEA and grid[38][24] == SEA and grid[41][24] == SEA and grid[39][20] == SEA and grid[39][28] == SEA, "the Isle of Wight should be an island in the Solent")
    need(grid[47][18] != SEA and grid[47][33] != SEA and grid[48][26] == SEA, "Cotentin and the St-Valery shore should face England with the Seine bay between")
    need(len(_xs(grid, 53)) >= 30, "Normandy should be a solid coast, not a thin island")

    if errors:
        raise SystemExit("map check failed:\n- " + "\n- ".join(errors))
    return {"ermine_steps": len(costs) if costs else None, "ermine_weeks": weeks, "channel_steps": steps}


def _paint_out(grid, spans):
    painted = 0
    for y, ranges in spans.items():
        if not (0 <= y < BIG_H):
            raise SystemExit(f"out-of-play row {y} is off the map")
        for west, east in ranges:
            for x in range(west, east + 1):
                if not (0 <= x < BIG_W):
                    raise SystemExit(f"out-of-play cell {x},{y} is off the map")
                if grid[y][x] == SEA:
                    grid[y][x] = OUT
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
    """Scotland and the rest of northern France, in big-map coordinates.

    Spans are inclusive. Painting only replaces sea, so the playable mask,
    the Seine bay, and the open Channel survive wherever they already are land
    or wherever these spans deliberately stop short of them.
    """
    # Scotland, north of the playable shoulder (small y=1, x=23..30).
    # The east coast is nearly straight. The west coast steps out, then the
    # whole island tapers to a northern cape. It meets the shoulder on the
    # row above the playable tip.
    west, east = OX + 23, OX + 30
    scotland = {
        1: [(west + 6, east - 1)],
        2: [(west + 5, east)],
        3: [(west + 4, east)],
        4: [(west + 3, east + 1)],
        5: [(west + 2, east + 2)],
        6: [(west + 1, east + 2)],
        7: [(west, east + 2)],
        8: [(west - 2, east + 2)],
        9: [(west - 4, east + 2)],
        10: [(west - 5, east + 2)],
        11: [(west - 5, east + 2)],
        12: [(west - 4, east + 2)],
        13: [(west - 3, east + 2)],
        14: [(west - 2, east + 2)],
        15: [(west - 1, east + 2)],
        OY: [(west - 1, east + 1)],
    }

    # Brittany, west of the Cotentin, with the Gulf of Saint-Malo kept as sea
    # between this outline and the playable west coast (small x about 6..16).
    brittany = {
        OY + 49: [(2, OX + 4)],
        OY + 50: [(1, OX + 5)],
        OY + 51: [(1, OX + 4)],
        OY + 52: [(1, OX + 3)],
        OY + 53: [(2, OX + 4)],
        OY + 54: [(2, OX + 6)],
        OY + 55: [(3, OX + 8)],
        OY + 56: [(4, OX + 9)],
        OY + 57: [(5, OX + 10)],
        OY + 58: [(6, OX + 12)],
        OY + 59: [(8, OX + 13)],
    }

    # Maine and Anjou south of Normandy, wide enough to read as the rest of
    # the French interior rather than a second thin coast.
    maine = {
        OY + 60: [(4, OX + 36)],
        OY + 61: [(6, OX + 38)],
        OY + 62: [(8, OX + 40)],
        OY + 63: [(10, OX + 40)],
        OY + 64: [(12, OX + 38)],
        OY + 65: [(14, OX + 36)],
        OY + 66: [(16, OX + 34)],
        OY + 67: [(18, OX + 32)],
        OY + 68: [(20, OX + 30)],
        OY + 69: [(22, OX + 28)],
        OY + 70: [(24, OX + 26)],
        OY + 71: [(26, OX + 24)],
        OY + 72: [(28, OX + 22)],
        OY + 73: [(30, OX + 18)],
    }

    # Flanders and Boulogne continue the continental coast east of Ponthieu.
    # The headland north of the French shore stays east of the playable
    # rectangle, so the open Channel in front of Hastings is untouched and the
    # strait still narrows toward Dover.
    # Solid Boulogne headland. It stays east of the playable rectangle, opposite
    # Dover, and joins the continental shore on the next row.
    flanders = {
        OY + 32: [(OX + W + 8, BIG_W - 2)],
        OY + 33: [(OX + W + 7, BIG_W - 2)],
        OY + 34: [(OX + W + 6, BIG_W - 2)],
        OY + 35: [(OX + W + 5, BIG_W - 2)],
        OY + 36: [(OX + W + 4, BIG_W - 2)],
        OY + 37: [(OX + W + 4, BIG_W - 2)],
        OY + 38: [(OX + W + 3, BIG_W - 2)],
        OY + 39: [(OX + W + 3, BIG_W - 2)],
        OY + 40: [(OX + W + 2, BIG_W - 2)],
        OY + 41: [(OX + W + 2, BIG_W - 2)],
        OY + 42: [(OX + W + 1, BIG_W - 2)],
        OY + 43: [(OX + W + 1, BIG_W - 2)],
        OY + 44: [(OX + W, BIG_W - 2)],
        OY + 45: [(OX + W, BIG_W - 2)],
        OY + 46: [(OX + W, BIG_W - 2)],
        OY + 47: [(OX + 38, BIG_W - 2)],
        OY + 48: [(OX + 40, BIG_W - 3)],
        OY + 49: [(OX + 41, BIG_W - 3)],
        OY + 50: [(OX + 42, BIG_W - 3)],
        OY + 51: [(OX + 43, BIG_W - 4)],
        OY + 52: [(OX + 43, BIG_W - 4)],
        OY + 53: [(OX + 42, BIG_W - 5)],
        OY + 54: [(OX + 41, BIG_W - 6)],
        OY + 55: [(OX + 40, BIG_W - 8)],
        OY + 56: [(OX + 38, BIG_W - 10)],
        OY + 57: [(OX + 36, BIG_W - 12)],
        OY + 58: [(OX + 34, BIG_W - 14)],
        OY + 59: [(OX + 32, BIG_W - 16)],
    }
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


def check_outline(small, big, towns, counts):
    import re

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

    # The Manche in front of the playable coasts stays water, including the
    # rows that the Flanders headland is allowed to approach only further east.
    for y in range(44, 47):
        for x in range(W):
            if big[y + OY][x + OX] != SEA:
                errors.append(f"out-of-play land in the Channel at {x + OX},{y + OY}")
                break

    for name, n in counts.items():
        need(n >= 40, f"{name} outline is only {n} cells")

    # The playable tip's northern neighbour is Scotland, not a blank edge.
    tip_y = OY + 1
    tip_xs = [x for x in range(BIG_W) if big[tip_y][x] not in (SEA, OUT)]
    need(bool(tip_xs), "playable northern tip missing")
    if tip_xs:
        joined = any(big[tip_y - 1][x] == OUT for x in tip_xs)
        need(joined, "Scotland does not touch the playable island")

    # Brittany stays west of the Cotentin, Maine south of Normandy, Flanders
    # east of Ponthieu. These are existence checks, not a redraw of the coast.
    need(any(big[OY + 52][x] == OUT for x in range(0, OX)), "Brittany should lie west of Normandy")
    need(any(big[OY + 64][x] == OUT for x in range(BIG_W)), "Maine should lie south of Normandy")
    need(any(big[OY + 47][x] == OUT for x in range(OX + 42, BIG_W)), "Flanders should lie east of Ponthieu")

    # Boulogne is the same coast as Ponthieu, not a striped island in the Strait.
    from collections import deque

    cape = None
    for y in range(OY + 32, OY + 47):
        for x in range(BIG_W - 1, OX + W - 1, -1):
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

    by = {t["name"]: t for t in towns}
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
    need(match is not None and int(match.group(1)) == 46 + OY, "ENGLAND_LAT in src/world.js must equal 46 + the Scotland padding")
    for t in towns:
        if t["owner"] == "norman":
            need(t["y"] > 46 + OY, f"{t['name']} is on the England side of the shifted latitude line")

    if errors:
        raise SystemExit("outline check failed:\n- " + "\n- ".join(errors))


def main():
    grid, towns = build()
    stats = validate(grid, towns)
    big, moved, counts = compose(grid, towns)
    lines = ["".join(CH[c] for c in row) for row in big]
    debug = "--debug" in sys.argv
    if debug:
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
