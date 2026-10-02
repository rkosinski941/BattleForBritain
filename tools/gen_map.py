"""Generate a square-grid operational map of Britain and Normandy, 1066."""
from __future__ import annotations

import json
import math
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

WEST = [
    (2, 20),
    (6, 18),
    (10, 17),
    (14, 16),
    (18, 13),
    (22, 7),
    (26, 5),
    (30, 8),
    (34, 11),
    (38, 7),
    (42, 4),
    (44, 9),
    (46, 17),
]
EAST = [
    (2, 29),
    (6, 31),
    (10, 33),
    (14, 34),
    (16, 31),
    (18, 28),
    (21, 33),
    (24, 39),
    (28, 41),
    (32, 37),
    (36, 39),
    (40, 42),
    (43, 39),
    (46, 33),
]


def lerp_keys(keys, y):
    i = 0
    while i + 1 < len(keys) and keys[i + 1][0] < y:
        i += 1
    a = keys[i]
    b = keys[min(i + 1, len(keys) - 1)]
    if a[0] == b[0]:
        return a[1]
    t = (y - a[0]) / (b[0] - a[0])
    return a[1] + t * (b[1] - a[1])


def in_england(x, y):
    if y < 2 or y > 46:
        return False
    west = lerp_keys(WEST, y)
    east = lerp_keys(EAST, y)
    if west <= x <= east:
        return True
    # Isle of Wight
    if 50 <= y <= 52 and 19 <= x <= 26:
        return True
    return False


def in_france(x, y):
    if y < 53 or y > 62:
        return False
    coast = 53
    if 30 <= x <= 36:
        coast = 54  # Somme mouth
    if y < coast:
        return False
    return 9 <= x <= 41


def stamp(grid, cx, cy, rx, ry, terr, pred=None):
    for y in range(max(0, cy - ry - 1), min(H, cy + ry + 2)):
        for x in range(max(0, cx - rx - 1), min(W, cx + rx + 2)):
            if ((x - cx) / max(rx, 0.5)) ** 2 + ((y - cy) / max(ry, 0.5)) ** 2 <= 1:
                if grid[y][x] in (CLEAR, HILL, FOREST, MARSH, BEACH, ROAD):
                    if pred is None or pred(x, y, grid[y][x]):
                        grid[y][x] = terr


def bresenham(x0, y0, x1, y1):
    pts = []
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        pts.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return pts


def nearest(grid, x, y, allowed):
    best = None
    bd = 99
    for yy in range(H):
        for xx in range(W):
            if grid[yy][xx] in allowed:
                d = abs(xx - x) + abs(yy - y)
                if d < bd:
                    bd = d
                    best = (xx, yy)
    return best or (x, y)


def build():
    grid = [[SEA for _ in range(W)] for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if in_england(x, y) or in_france(x, y):
                grid[y][x] = CLEAR

    # Carves: Wash, Thames, Severn/Bristol, Humber, Solway
    for cx, cy, r in [(36, 24, 3), (38, 36, 3), (11, 34, 3), (30, 17, 2), (14, 7, 2)]:
        for y in range(H):
            for x in range(W):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r and grid[y][x] != TOWN:
                    if in_england(x, y) or True:
                        if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                            # only carve if near coast-ish
                            grid[y][x] = SEA

    # Re-fill obvious inland holes from over-carve by keeping england test
    for y in range(H):
        for x in range(W):
            if in_england(x, y) or in_france(x, y):
                if grid[y][x] == SEA:
                    # keep carve if adjacent to many seas toward the sea direction
                    seas = 0
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < W and 0 <= yy < H and grid[yy][xx] == SEA:
                            seas += 1
                    if seas <= 1:
                        grid[y][x] = CLEAR

    # Hills
    stamp(grid, 19, 12, 2, 8, HILL)  # Pennines
    stamp(grid, 10, 26, 4, 6, HILL)  # Wales
    stamp(grid, 18, 34, 3, 3, HILL)  # Cotswolds
    stamp(grid, 26, 42, 6, 2, HILL)  # Downs
    stamp(grid, 33, 40, 3, 2, HILL)  # Kent downs
    stamp(grid, 18, 58, 6, 3, HILL)  # Norman bocage
    stamp(grid, 8, 44, 3, 2, HILL)  # Dartmoor / devon

    # Forests
    stamp(grid, 28, 42, 5, 3, FOREST)  # Weald
    stamp(grid, 18, 43, 3, 2, FOREST)  # New Forest
    stamp(grid, 22, 22, 3, 3, FOREST)  # Sherwood / midlands
    stamp(grid, 12, 22, 3, 4, FOREST)  # Welsh woods
    stamp(grid, 34, 30, 3, 2, FOREST)  # East Anglian woods
    stamp(grid, 22, 57, 4, 2, FOREST)  # Norman woods

    # Marshes
    stamp(grid, 34, 26, 4, 3, MARSH)  # Fens
    stamp(grid, 14, 38, 3, 2, MARSH)  # Somerset
    stamp(grid, 36, 42, 2, 2, MARSH)  # Romney
    stamp(grid, 32, 18, 2, 1, MARSH)  # Humber levels

    # Beaches: English south coast and French north coast
    for y in range(H):
        for x in range(W):
            if grid[y][x] not in (CLEAR, HILL, FOREST, MARSH):
                continue
            adj_sea = False
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < W and 0 <= yy < H and grid[yy][xx] == SEA:
                    adj_sea = True
            if not adj_sea:
                continue
            south_england = y >= 42 and y <= 52
            french_coast = y >= 53 and y <= 55
            pevensey_bay = 27 <= x <= 36 and 43 <= y <= 47
            if south_england or french_coast or pevensey_bay:
                grid[y][x] = BEACH

    towns_spec = [
        ("York", 22, 14, 15, "english"),
        ("Durham", 20, 8, 4, "english"),
        ("Lincoln", 28, 20, 6, "english"),
        ("Nottingham", 22, 22, 5, "english"),
        ("Norwich", 36, 28, 5, "english"),
        ("Stamford", 26, 18, 4, "english"),
        ("Oxford", 20, 32, 5, "english"),
        ("London", 29, 36, 25, "english"),
        ("Winchester", 20, 40, 15, "english"),
        ("Canterbury", 36, 39, 8, "english"),
        ("Dover", 40, 41, 8, "english"),
        ("Hastings", 33, 45, 6, "english"),
        ("Pevensey", 30, 45, 6, "english"),
        ("Chichester", 24, 45, 4, "english"),
        ("Exeter", 10, 44, 5, "english"),
        ("Gloucester", 16, 33, 5, "english"),
        ("Wallingford", 24, 35, 4, "english"),
        ("Thetford", 33, 30, 3, "english"),
        ("St-Valery", 33, 54, 4, "norman"),
        ("Bayeux", 16, 57, 3, "norman"),
        ("Caen", 20, 58, 6, "norman"),
        ("Rouen", 28, 60, 8, "norman"),
        ("Dives", 24, 54, 3, "norman"),
    ]

    towns = []
    for name, x, y, value, owner in towns_spec:
        xx, yy = nearest(grid, x, y, {CLEAR, HILL, FOREST, BEACH, MARSH, ROAD})
        grid[yy][xx] = TOWN
        towns.append(
            {"name": name, "x": xx, "y": yy, "value": value, "owner": owner, "port": False}
        )

    # Rivers
    def town_xy(name):
        t = next(t for t in towns if t["name"] == name)
        return t["x"], t["y"]

    rivers = [
        [town_xy("Gloucester"), town_xy("Oxford"), town_xy("London"), (38, 36)],  # Thames
        [town_xy("York"), (30, 17)],  # Ouse to Humber
        [(12, 28), town_xy("Gloucester"), (11, 36)],  # Severn
        [town_xy("Canterbury"), (40, 38)],  # Stour / north kent
        [town_xy("Rouen"), (28, 53)],  # Seine
    ]
    for path in rivers:
        for i in range(len(path) - 1):
            for x, y in bresenham(*path[i], *path[i + 1]):
                if 0 <= x < W and 0 <= y < H and grid[y][x] in (CLEAR, HILL, FOREST, MARSH, BEACH, ROAD):
                    grid[y][x] = RIVER

    roads = [
        ["Dover", "Canterbury", "London"],  # Watling start
        ["London", "Wallingford", "Oxford"],
        ["London", "Lincoln", "York"],  # Ermine Street
        ["Exeter", "Winchester", "London"],
        ["Pevensey", "Hastings", "Dover"],
        ["Winchester", "Chichester"],
        ["Gloucester", "Oxford"],
        ["York", "Durham"],
        ["London", "Thetford", "Norwich"],
        ["Caen", "Bayeux"],
        ["Caen", "Rouen"],
        ["Dives", "St-Valery"],
        ["Rouen", "St-Valery"],
    ]
    for path in roads:
        coords = [town_xy(n) if isinstance(n, str) else n for n in path]
        for i in range(len(coords) - 1):
            for x, y in bresenham(*coords[i], *coords[i + 1]):
                if 0 <= x < W and 0 <= y < H and grid[y][x] in (CLEAR, HILL, FOREST, BEACH):
                    grid[y][x] = ROAD

    # Ports: towns next to sea, beach, or navigable river
    for t in towns:
        t["port"] = False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)):
            xx, yy = t["x"] + dx, t["y"] + dy
            if 0 <= xx < W and 0 <= yy < H and grid[yy][xx] in (SEA, BEACH, RIVER):
                t["port"] = True
        if t["name"] in ("London", "York", "Rouen", "Dives", "St-Valery", "Pevensey", "Hastings", "Dover"):
            t["port"] = True

    return grid, towns


def main():
    grid, towns = build()
    lines = ["".join(CH[c] for c in row) for row in grid]
    print("\n".join(lines))
    print("--- towns ---")
    for t in towns:
        print(f"{t['name']:14} {t['x']:2},{t['y']:2} port={t['port']} {CH[grid[t['y']][t['x']]]}")
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
