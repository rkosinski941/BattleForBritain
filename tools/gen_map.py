"""Generate the 1066 grid aligned to a Natural Earth relief image.

The board image is equidistant cylindrical with true scale at 51.5°N, so a
cell that is square on the picture is square on the ground along that
parallel. tools/coast.json is the Natural Earth 1:10m land polygons clipped
to this window. Each cell is land when most of nine interior samples fall
on land, so the grid shore sits on the coastline in the picture.

London–York is a straight cardinal march of about fourteen road steps, two
fair-weather housecarl weeks. The same cell size puts St-Valery about five
fleet steps from the Sussex beaches. That is still one fair-weather week
(a fleet has eight orders and spends three ticks on sea). Seven steps would
need a finer grid, and London–York would then take a third week: two town
cells on the road leave room for only fifteen steps inside two weeks of
eight orders. Costs are unchanged.

Scotland north of the Tweed, Ireland's clipped east coast, Brittany, Maine,
and Flanders stay impassable. The England line in src/world.js is the row
between the English towns and the Norman ports.
"""
from __future__ import annotations

import heapq
import json
import math
import re
import struct
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COAST_PATH = ROOT / "tools" / "coast.json"
BOARD_PATH = ROOT / "data" / "board.jpg"
MAP_PATH = ROOT / "data" / "map.json"
WORLD_PATH = ROOT / "src" / "world.js"

# Equidistant cylindrical, true scale at 51.5°N. x grows east, y grows south.
LAT0 = 51.5
CELL = 0.20
LON_CELL = CELL / math.cos(math.radians(LAT0))
LAT_N = 57.0
LAT_S = 47.4
LON_W = -6.25
W = 31
H = int(round((LAT_N - LAT_S) / CELL))
LON_E = LON_W + W * LON_CELL
CELL_PX = 40
BOARD_W = W * CELL_PX
BOARD_H = H * CELL_PX

# A cell is land when most of its nine interior samples hit a polygon, so the
# painted shore sits on the picture's coastline rather than a cell out to sea.
LAND_HITS = 5
SAMPLES = (0.25, 0.5, 0.75)

SEA, BEACH, CLEAR, FOREST, HILL, MARSH, RIVER, ROAD, TOWN, OUT = range(10)
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
WALKABLE = {CLEAR, FOREST, HILL, MARSH, BEACH, RIVER, ROAD, TOWN}

# name, lat, lon, value, owner, kind. kind is coast (snap to sea), river, or inland.
TOWNS = [
    ("York", 53.9591, -1.0815, 15, "english", "river"),
    ("Durham", 54.7761, -1.5733, 4, "english", "inland"),
    ("Lincoln", 53.2307, -0.5406, 6, "english", "inland"),
    ("Nottingham", 52.9548, -1.1581, 5, "english", "inland"),
    ("Norwich", 52.6309, 1.2974, 5, "english", "inland"),
    ("Stamford", 52.6522, -0.4798, 4, "english", "inland"),
    ("Oxford", 51.7520, -1.2577, 5, "english", "inland"),
    ("London", 51.5074, -0.1278, 25, "english", "river"),
    ("Winchester", 51.0632, -1.3080, 15, "english", "inland"),
    ("Canterbury", 51.2802, 1.0789, 8, "english", "inland"),
    ("Dover", 51.1279, 1.3134, 8, "english", "coast"),
    ("Hastings", 50.8543, 0.5735, 6, "english", "coast"),
    ("Pevensey", 50.8194, 0.3386, 6, "english", "coast"),
    ("Chichester", 50.8367, -0.7792, 4, "english", "coast"),
    ("Exeter", 50.7184, -3.5339, 5, "english", "inland"),
    ("Gloucester", 51.8642, -2.2382, 5, "english", "inland"),
    ("Wallingford", 51.5990, -1.1250, 4, "english", "inland"),
    ("Thetford", 52.4126, 0.7464, 3, "english", "inland"),
    ("St-Valery", 50.1886, 1.6292, 4, "norman", "coast"),
    ("Bayeux", 49.2765, -0.7026, 3, "norman", "inland"),
    ("Caen", 49.1829, -0.3707, 6, "norman", "inland"),
    ("Rouen", 49.4432, 1.0993, 8, "norman", "river"),
    ("Dives", 49.2853, -0.1006, 3, "norman", "coast"),
]

RIVER_MOUTH = {
    "London": (51.48, 0.80),
    "York": (53.62, 0.12),
    "Rouen": (49.47, 0.12),
}

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

BOARD_IMAGE = {
    "path": "data/board.jpg",
    "width": BOARD_W,
    "height": BOARD_H,
    "left": 0,
    "top": 0,
    "right": BOARD_W,
    "bottom": BOARD_H,
    "projection": "equidistant cylindrical",
    "standard_parallel": LAT0,
    "lon_min": LON_W,
    "lon_max": LON_E,
    "lat_min": LAT_S,
    "lat_max": LAT_N,
    "source_url": "https://naciscdn.org/naturalearth/10m/raster/HYP_HR_SR_W_DR.zip",
    "coast_url": "https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip",
    "author": "Tom Patterson, Nathaniel Vaughn Kelso, and Natural Earth contributors",
    "license": "Public domain",
    "license_url": "https://www.naturalearthdata.com/about/terms-of-use/",
}


def cell_ll(x, y):
    """Longitude and latitude of a cell center."""
    return LON_W + (x + 0.5) * LON_CELL, LAT_N - (y + 0.5) * CELL


def ll_cell(lon, lat):
    x = int(math.floor((lon - LON_W) / LON_CELL))
    y = int(math.floor((LAT_N - lat) / CELL))
    return x, y


def neighbors(x, y):
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        xx, yy = x + dx, y + dy
        if 0 <= xx < W and 0 <= yy < H:
            yield xx, yy


def point_in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            denom = (yj - yi) or 1e-18
            if x < (xj - xi) * (y - yi) / denom + xi:
                inside = not inside
        j = i
    return inside


def load_rings():
    data = json.loads(COAST_PATH.read_text(encoding="utf-8"))
    rings = []
    for raw in data["rings"]:
        pts = [(p[0], p[1]) for p in raw]
        if len(pts) < 3:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        rings.append((min(xs), min(ys), max(xs), max(ys), pts))
    if not rings:
        raise SystemExit(f"no coastline rings in {COAST_PATH}")
    return rings


def is_land(lon, lat, rings):
    for x0, y0, x1, y1, pts in rings:
        if lon < x0 or lon > x1 or lat < y0 or lat > y1:
            continue
        if point_in_ring(lon, lat, pts):
            return True
    return False


def cell_is_land(x, y, rings):
    hits = 0
    for iy in SAMPLES:
        for ix in SAMPLES:
            lon = LON_W + (x + ix) * LON_CELL
            lat = LAT_N - (y + iy) * CELL
            if is_land(lon, lat, rings):
                hits += 1
                if hits >= LAND_HITS:
                    return True
    return False


def out_region(lon, lat):
    """Impassable land. None means the cell stays in the campaign."""
    if lat >= 55.70:
        return "scotland"
    # The east coast of Ireland clips the left edge. It is not a theatre.
    if lon <= -5.35 and 52.70 <= lat <= 55.50:
        return "ireland"
    # Brittany, west of the Couesnon and south of the Norman coast.
    if lon <= -1.15 and lat <= 48.95:
        return "brittany"
    # Maine and the interior, south of Falaise and Caen.
    if lat <= 48.70 and lon > -1.15:
        return "maine"
    # Boulogne and Calais, the shore across the Strait from Dover.
    # The latitude cap keeps this off East Anglia, which is just as far east.
    if 50.40 <= lat <= 51.05 and lon >= 1.48:
        return "flanders"
    # Flanders and Picardy east of the Somme.
    if lon >= 1.95:
        return "flanders"
    return None


def touches(grid, x, y, kinds):
    return any(grid[yy][xx] in kinds for xx, yy in neighbors(x, y))


def nearest(grid, x, y, pred, limit=10):
    if pred(x, y):
        return x, y
    q = deque([(x, y, 0)])
    seen = {(x, y)}
    while q:
        cx, cy, dist = q.popleft()
        if dist >= limit:
            continue
        for xx, yy in neighbors(cx, cy):
            if (xx, yy) in seen:
                continue
            if pred(xx, yy):
                return xx, yy
            seen.add((xx, yy))
            q.append((xx, yy, dist + 1))
    return None


def route(grid, start, goal, blocked, sea_penalty=0):
    """Cardinal A*. sea_penalty keeps a road off the beach when another way exists."""
    if start == goal:
        return [start]
    gx, gy = goal

    def step_cost(x, y):
        extra = sea_penalty if sea_penalty and touches(grid, x, y, {SEA}) else 0
        return 1 + extra

    openq = [(0, 0, start[0], start[1])]
    came = {start: None}
    gscore = {start: 0}
    while openq:
        _, g, x, y = heapq.heappop(openq)
        if g != gscore.get((x, y)):
            continue
        if (x, y) == goal:
            path = [(x, y)]
            while came[path[-1]] is not None:
                path.append(came[path[-1]])
            path.reverse()
            return path
        for xx, yy in neighbors(x, y):
            if blocked(xx, yy) and (xx, yy) != goal:
                continue
            ng = g + step_cost(xx, yy)
            if ng < gscore.get((xx, yy), 1e9):
                gscore[(xx, yy)] = ng
                came[(xx, yy)] = (x, y)
                heapq.heappush(openq, (ng + abs(xx - gx) + abs(yy - gy), ng, xx, yy))
    return None


def stamp(grid, lon, lat, rx, ry, terr):
    for y in range(H):
        for x in range(W):
            if grid[y][x] != CLEAR:
                continue
            clon, clat = cell_ll(x, y)
            if ((clon - lon) / rx) ** 2 + ((clat - lat) / ry) ** 2 <= 1:
                grid[y][x] = terr


def place_towns(grid):
    taken = set()
    towns = []
    for name, lat, lon, value, owner, kind in TOWNS:
        ix, iy = ll_cell(lon, lat)
        ix = max(0, min(W - 1, ix))
        iy = max(0, min(H - 1, iy))

        def playable(x, y, taken=taken):
            return grid[y][x] not in (SEA, OUT) and (x, y) not in taken

        if kind == "coast":
            best = None
            for rad in range(0, 7):
                cands = []
                for y in range(max(0, iy - rad), min(H, iy + rad + 1)):
                    for x in range(max(0, ix - rad), min(W, ix + rad + 1)):
                        if rad and max(abs(x - ix), abs(y - iy)) != rad:
                            continue
                        if not playable(x, y) or not touches(grid, x, y, {SEA}):
                            continue
                        clon, clat = cell_ll(x, y)
                        dist = (clon - lon) ** 2 + ((clat - lat) * LON_CELL / CELL) ** 2
                        if owner == "english":
                            facing = y + 1 < H and grid[y + 1][x] == SEA
                        else:
                            facing = y > 0 and grid[y - 1][x] == SEA
                        cands.append((dist + (0 if facing else 0.02), x, y))
                if cands:
                    cands.sort()
                    best = (cands[0][1], cands[0][2])
                    break
            if best is None:
                best = nearest(grid, ix, iy, playable, 8)
            if best is None:
                raise SystemExit(f"no land for {name}")
            ix, iy = best
        elif not playable(ix, iy):
            found = nearest(grid, ix, iy, playable, 8)
            if found is None:
                raise SystemExit(f"no land for {name}")
            ix, iy = found
        taken.add((ix, iy))
        grid[iy][ix] = TOWN
        towns.append(
            {
                "name": name,
                "x": ix,
                "y": iy,
                "value": value,
                "owner": owner,
                "port": False,
                "kind": kind,
            }
        )
    return towns


def paint_roads(grid, towns):
    by = {t["name"]: (t["x"], t["y"]) for t in towns}
    town_cells = set(by.values())
    ermine = set()
    roads = [
        (["London", "Lincoln", "York"], 0, True),
        (["York", "Durham"], 0, False),
        (["Dover", "Canterbury", "London"], 3, False),
        (["London", "Wallingford", "Oxford"], 1, False),
        (["Oxford", "Gloucester"], 1, False),
        (["Exeter", "Winchester", "London"], 2, False),
        (["Chichester", "Pevensey", "Hastings", "Canterbury", "Dover"], 4, False),
        (["Winchester", "Chichester"], 3, False),
        (["London", "Thetford", "Norwich"], 2, False),
        (["Nottingham", "Lincoln"], 1, False),
        (["Caen", "Bayeux"], 1, False),
        (["Dives", "Caen"], 2, False),
        (["Caen", "Rouen"], 1, False),
        (["Rouen", "St-Valery"], 2, False),
        (["Dives", "St-Valery"], 2, False),
    ]
    for path, penalty, is_ermine in roads:
        for a, b in zip(path, path[1:]):
            start, goal = by[a], by[b]
            ends = {start, goal}

            def blocked(x, y, ends=ends, town_cells=town_cells):
                if (x, y) in town_cells and (x, y) not in ends:
                    return True
                return grid[y][x] in (SEA, OUT)

            found = route(grid, start, goal, blocked, sea_penalty=penalty)
            if not found:
                raise SystemExit(f"no road {a} -> {b}")
            for x, y in found:
                if is_ermine:
                    ermine.add((x, y))
                if grid[y][x] in WALKABLE and grid[y][x] != TOWN:
                    grid[y][x] = ROAD
    return ermine


def paint_beaches(grid):
    for y in range(H):
        for x in range(W):
            if grid[y][x] not in (CLEAR, HILL, FOREST, MARSH):
                continue
            lon, lat = cell_ll(x, y)
            sea_s = y + 1 < H and grid[y + 1][x] == SEA
            sea_n = y > 0 and grid[y - 1][x] == SEA
            sea_e = x + 1 < W and grid[y][x + 1] == SEA
            # English Channel shore, including the Cornish south coast and Kent's corner.
            if 50.05 <= lat <= 51.50 and sea_s:
                grid[y][x] = BEACH
            elif lon >= 1.05 and 50.90 <= lat <= 51.35 and sea_e:
                grid[y][x] = BEACH
            # Norman shore facing England, not the Flemish side.
            elif 48.85 <= lat <= 50.40 and sea_n and lon < 1.90:
                grid[y][x] = BEACH


def paint_rivers(grid, towns, ermine):
    by = {t["name"]: t for t in towns}
    for name, (mlat, mlon) in RIVER_MOUTH.items():
        town = by[name]
        start = (town["x"], town["y"])
        cands = []
        for y in range(H):
            for x in range(W):
                if grid[y][x] != SEA:
                    continue
                clon, clat = cell_ll(x, y)
                dist = (clon - mlon) ** 2 + (clat - mlat) ** 2
                if dist <= 0.45 ** 2:
                    cands.append((dist, x, y))
        cands.sort()
        found = None
        for _, sx, sy in cands[:16]:
            goal = (sx, sy)

            def blocked(x, y, goal=goal, start=start, ermine=ermine):
                if (x, y) in ermine and (x, y) != start:
                    return True
                if grid[y][x] in (SEA, OUT) and (x, y) != goal:
                    return True
                if grid[y][x] == TOWN and (x, y) != start:
                    return True
                return False

            found = route(grid, start, goal, blocked, sea_penalty=0)
            if found:
                break
        if not found:
            raise SystemExit(f"no river from {name} to the sea")
        for x, y in found[1:]:
            if grid[y][x] == SEA:
                break
            if grid[y][x] != TOWN:
                grid[y][x] = RIVER


def open_quays(grid, towns, ermine):
    for t in towns:
        if t["name"] not in REQUIRED_PORTS:
            continue
        if touches(grid, t["x"], t["y"], {SEA, BEACH, RIVER}):
            continue
        opened = False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, yy = t["x"] + dx, t["y"] + dy
            if not (0 <= xx < W and 0 <= yy < H):
                continue
            if grid[yy][xx] in (SEA, OUT, TOWN):
                continue
            if (xx, yy) in ermine:
                continue
            grid[yy][xx] = RIVER
            opened = True
            break
        if not opened:
            raise SystemExit(f"no quay for {t['name']}")


def mark_ports(grid, towns):
    for t in towns:
        t["port"] = touches(grid, t["x"], t["y"], {SEA, BEACH, RIVER})
        if t["name"] in REQUIRED_PORTS and not t["port"]:
            raise SystemExit(f"{t['name']} is flagged a port but touches no water")


def build():
    rings = load_rings()
    grid = [[SEA for _ in range(W)] for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if cell_is_land(x, y, rings):
                grid[y][x] = CLEAR

    stamp(grid, -2.20, 54.25, 0.55, 0.90, HILL)  # Pennines
    stamp(grid, -3.55, 52.50, 0.55, 0.80, HILL)  # Welsh massif
    stamp(grid, -2.25, 55.40, 0.40, 0.32, HILL)  # Cheviots
    stamp(grid, -3.95, 50.58, 0.38, 0.28, HILL)  # Dartmoor
    stamp(grid, -1.80, 51.85, 0.48, 0.32, HILL)  # Cotswolds
    stamp(grid, -0.25, 50.92, 0.75, 0.20, HILL)  # Downs
    stamp(grid, -0.15, 48.95, 0.50, 0.28, HILL)  # Norman hills
    stamp(grid, 0.40, 51.10, 0.48, 0.26, FOREST)  # the Weald
    stamp(grid, -1.58, 50.86, 0.32, 0.20, FOREST)  # New Forest
    stamp(grid, -1.15, 53.18, 0.32, 0.26, FOREST)  # Sherwood
    stamp(grid, -3.45, 52.15, 0.40, 0.36, FOREST)  # Welsh woods
    stamp(grid, 0.10, 52.70, 0.50, 0.32, MARSH)  # the Fens
    stamp(grid, -2.90, 51.15, 0.36, 0.20, MARSH)  # Somerset levels
    stamp(grid, 0.90, 50.95, 0.30, 0.16, MARSH)  # Romney

    counts = {"scotland": 0, "ireland": 0, "brittany": 0, "maine": 0, "flanders": 0}
    for y in range(H):
        for x in range(W):
            if grid[y][x] == SEA:
                continue
            region = out_region(*cell_ll(x, y))
            if region:
                grid[y][x] = OUT
                counts[region] += 1

    towns = place_towns(grid)
    ermine = paint_roads(grid, towns)
    paint_beaches(grid)
    paint_rivers(grid, towns, ermine)
    open_quays(grid, towns, ermine)
    mark_ports(grid, towns)
    return grid, towns, counts


def road_costs(grid, start, goal, via=()):
    """Tick costs along roads. Towns other than the goal and `via` are avoided.

    Entering a town spends five ticks, so a shortest step-path that merely
    brushes Stamford would spill the march into a third week. The road itself
    runs beside that town.
    """
    allowed = {goal, *via}
    q = deque([start])
    prev = {start: None}
    while q:
        x, y = q.popleft()
        if (x, y) == goal:
            break
        for xx, yy in neighbors(x, y):
            if (xx, yy) in prev:
                continue
            cell = grid[yy][xx]
            if (xx, yy) not in allowed and cell == TOWN:
                continue
            if cell not in (ROAD, TOWN) and (xx, yy) not in allowed:
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
    return [5 if grid[y][x] == TOWN else 4 for x, y in cells]


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
    starts = [(xx, yy) for xx, yy in neighbors(*origin) if grid[yy][xx] == SEA]
    if not starts:
        return None
    goals = set()
    for xy in landings:
        goals.add(xy)
        for xx, yy in neighbors(*xy):
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


def components(grid, pred):
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


def jpeg_size(path):
    with path.open("rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise SystemExit(f"{path} is not a JPEG")
        while True:
            marker = f.read(1)
            if not marker:
                break
            while marker != b"\xff":
                marker = f.read(1)
                if not marker:
                    return None
            code = f.read(1)
            if code in (b"\xd8", b"\xd9", b"\x00"):
                continue
            # stuffed padding
            while code == b"\xff":
                code = f.read(1)
            if code == b"\xda":
                break
            seglen = struct.unpack(">H", f.read(2))[0]
            if code in (b"\xc0", b"\xc1", b"\xc2"):
                f.read(1)
                height, width = struct.unpack(">HH", f.read(4))
                return width, height
            f.read(seglen - 2)
    return None


def validate(grid, towns, counts):
    by = {t["name"]: t for t in towns}
    errors = []

    def need(cond, msg):
        if not cond:
            errors.append(msg)

    for t in towns:
        need(grid[t["y"]][t["x"]] == TOWN, f"{t['name']} is not on a town cell")

    york, lincoln, london = by["York"], by["Lincoln"], by["London"]
    need(york["y"] < lincoln["y"] < london["y"], "Ermine Street should run York, Lincoln, London north to south")
    lincoln_xy = (lincoln["x"], lincoln["y"])
    costs = road_costs(grid, (london["x"], london["y"]), (york["x"], york["y"]), via=(lincoln_xy,))
    need(costs is not None, "no road connects London to York")
    weeks = None
    if costs is not None:
        weeks = weeks_for(costs)
        need(13 <= len(costs) <= 16, f"London–York road is {len(costs)} steps (want about 14, at most 16)")
        need(weeks == 2, f"London–York road is {len(costs)} steps, {weeks} fair weeks (want 2)")
        via = road_costs(grid, (london["x"], london["y"]), lincoln_xy)
        need(via is not None, "Lincoln is off Ermine Street")

    hastings, pevensey, dover = by["Hastings"], by["Pevensey"], by["Dover"]
    need(pevensey["x"] < hastings["x"] < dover["x"], "Sussex shore should run Pevensey, Hastings, Dover west to east")
    for name in ("Pevensey", "Hastings", "Chichester", "Dover"):
        t = by[name]
        wet = touches(grid, t["x"], t["y"], {SEA, BEACH})
        need(wet, f"{name} should touch the Channel")

    stv = by["St-Valery"]
    dives = by["Dives"]
    need(stv["y"] > hastings["y"], "St-Valery should lie across the Channel from Hastings")
    need(abs(stv["x"] - hastings["x"]) <= 6, "St-Valery should stand opposite the Sussex shore")

    english_south = max(t["y"] for t in towns if t["owner"] == "english")
    norman_north = min(t["y"] for t in towns if t["owner"] == "norman")
    need(english_south < norman_north, "an English town sits on or south of a Norman town")
    england_lat = norman_north - 1
    for t in towns:
        if t["owner"] == "norman":
            need(t["y"] > england_lat, f"{t['name']} is on the England side of the latitude line")
        else:
            need(t["y"] <= england_lat, f"{t['name']} is south of the England latitude line")

    steps = channel_steps(
        grid,
        (stv["x"], stv["y"]),
        [(pevensey["x"], pevensey["y"]), (hastings["x"], hastings["y"])],
    )
    # Five is the short end of one fleet week on this projection. A sixth step
    # would push Ermine Street past the fifteen steps that still fit in two weeks.
    need(steps is not None and 5 <= steps <= 8, f"Channel crossing is {steps} fleet steps (want 5..8, one fair week)")
    fleet_weeks = None
    if steps is not None:
        fleet_weeks = weeks_for([3] * steps)
        need(fleet_weeks == 1, f"Channel crossing takes {fleet_weeks} fleet weeks")

    for name in REQUIRED_PORTS:
        need(by[name]["port"], f"{name} is not a port")
        reach = sea_reachable(grid, by[name]["x"], by[name]["y"])
        need(reach >= 12, f"{name} does not open onto the sea (reachable sea {reach})")

    for name, n in counts.items():
        if name == "ireland":
            need(n >= 4, f"Ireland outline is only {n} cells")
        else:
            need(n >= 40, f"{name} outline is only {n} cells")

    def same(a, b, pred):
        parts = components(grid, pred)
        ca = next((p for p in parts if a in p), None)
        cb = next((p for p in parts if b in p), None)
        return ca is not None and ca is cb

    def landish(x, y):
        return grid[y][x] not in (SEA, OUT)

    london_xy = (london["x"], london["y"])
    need(same(london_xy, (york["x"], york["y"]), landish), "York is cut off from London")
    need(same(london_xy, (by["Exeter"]["x"], by["Exeter"]["y"]), landish), "Cornwall is cut off from London")
    need(same(london_xy, (dover["x"], dover["y"]), landish), "Dover is cut off from London")
    norman_ok = all(
        same((dives["x"], dives["y"]), (by[name]["x"], by[name]["y"]), landish)
        for name in ("Caen", "Bayeux", "Rouen", "St-Valery")
    )
    need(norman_ok, "the Norman ports are not on one playable coast")

    def any_land(x, y):
        return grid[y][x] != SEA

    britain = next(p for p in components(grid, any_land) if london_xy in p)
    need((by["Rouen"]["x"], by["Rouen"]["y"]) not in britain, "the Channel has closed between London and Rouen")
    corn = [
        (x, y)
        for y in range(H)
        for x in range(W)
        if grid[y][x] not in (SEA, OUT) and cell_ll(x, y)[0] < -4.4 and cell_ll(x, y)[1] < 50.9
    ]
    need(len(corn) >= 6, f"Cornwall is only {len(corn)} playable cells")
    wales = [
        (x, y)
        for y in range(H)
        for x in range(W)
        if grid[y][x] not in (SEA, OUT) and cell_ll(x, y)[0] < -3.6 and 51.6 < cell_ll(x, y)[1] < 53.2
    ]
    need(len(wales) >= 8, f"Wales is only {len(wales)} playable cells")

    world = WORLD_PATH.read_text(encoding="utf-8")
    match = re.search(r"ENGLAND_LAT = (\d+)", world)
    need(
        match is not None and int(match.group(1)) == england_lat,
        f"ENGLAND_LAT in src/world.js must be {england_lat}",
    )

    size = jpeg_size(BOARD_PATH) if BOARD_PATH.exists() else None
    need(size == (BOARD_W, BOARD_H), f"board image is {size}, want {(BOARD_W, BOARD_H)}")

    if errors:
        raise SystemExit("map check failed:\n- " + "\n- ".join(errors))
    return {
        "ermine_steps": len(costs) if costs else None,
        "ermine_weeks": weeks,
        "channel_steps": steps,
        "fleet_weeks": fleet_weeks,
        "england_lat": england_lat,
    }


def public_towns(towns):
    out = []
    for t in towns:
        out.append(
            {
                "name": t["name"],
                "x": t["x"],
                "y": t["y"],
                "value": t["value"],
                "owner": t["owner"],
                "port": t["port"],
            }
        )
    return out


def main():
    grid, towns, counts = build()
    stats = validate(grid, towns, counts)
    debug = "--debug" in sys.argv
    lines = ["".join(CH[c] for c in row) for row in grid]
    if debug:
        print("   " + "".join(str(x % 10) for x in range(W)))
        lines = [f"{y:02d} {line}" for y, line in enumerate(lines)]
    print("\n".join(lines))
    print("--- towns ---")
    for t in towns:
        print(f"{t['name']:14} {t['x']:2},{t['y']:2} port={t['port']}")
    print(
        f"Ermine Street {stats['ermine_steps']} steps, "
        f"{stats['ermine_weeks']} fair weeks for housecarls. "
        f"Channel {stats['channel_steps']} fleet steps, St-Valery to Sussex, "
        f"{stats['fleet_weeks']} fair week."
    )
    print(
        "Out of play: "
        + ", ".join(f"{name} {n}" for name, n in counts.items())
        + f". Map {W}x{H}. England line y<={stats['england_lat']}."
    )
    print(
        f"Board {BOARD_IMAGE['path']} {BOARD_W}x{BOARD_H}, "
        f"lon {LON_W:.4f}..{LON_E:.4f}, lat {LAT_S:.4f}..{LAT_N:.4f}, "
        f"equidistant cylindrical at {LAT0}N."
    )
    out = {
        "board_image": BOARD_IMAGE,
        "w": W,
        "h": H,
        "terrain": [cell for row in grid for cell in row],
        "towns": public_towns(towns),
    }
    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_PATH.write_text(json.dumps(out), encoding="utf-8")
    print("wrote", MAP_PATH)


if __name__ == "__main__":
    main()
