"""Build data/board.jpg and tools/coast.json for the campaign grid.

Reads a Natural Earth 1:10m hypsometric GeoTIFF (HYP_HR_SR_W_DR) and the
Natural Earth 1:10m land shapefile. The picture is resampled into the
equidistant-cylindrical window declared in gen_map.py, so cell edges fall
on pixel boundaries. Coastline rings are clipped to that window for the
land mask.

    python tools/build_board_image.py HYP_HR_SR_W_DR.tif ne_10m_land.shp

Both inputs are public domain Natural Earth:
https://www.naturalearthdata.com/about/terms-of-use/
"""
from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
import shapefile
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_map as gm


def tiff_u32(path, offset, count):
    with path.open("rb") as f:
        f.seek(offset)
        return struct.unpack("<" + "I" * count, f.read(4 * count))


def tiff_crop(path):
    """Return the source window covering the campaign bounds, plus its geo origin.

    Natural Earth 1:10m rasters are uncompressed RGB, one strip per row,
    plate carrée, 1/60 degree pixels, upper-left pixel centered on
    (-179.9916667, 89.9916667).
    """
    with path.open("rb") as f:
        hdr = f.read(8)
        if hdr[:2] != b"II" or struct.unpack("<H", hdr[2:4])[0] != 42:
            raise SystemExit(f"{path} is not a little-endian TIFF")
        ifd = struct.unpack("<I", hdr[4:8])[0]
        f.seek(ifd)
        n = struct.unpack("<H", f.read(2))[0]
        tags = {}
        for _ in range(n):
            tag, typ, count, val = struct.unpack("<HHII", f.read(12))
            tags[tag] = (typ, count, val)
    width = tags[256][2]
    height = tags[257][2]
    if tags[259][2] != 1 or tags[277][2] != 3 or tags[278][2] != 1:
        raise SystemExit("expected an uncompressed 3-band TIFF with one row per strip")
    offsets = tiff_u32(path, tags[273][2], height)
    counts = tiff_u32(path, tags[279][2], height)
    with path.open("rb") as f:
        f.seek(tags[33550][2])
        scale = struct.unpack("<3d", f.read(24))
    # Pixel size in degrees. Tiepoint is not required; the world file that
    # ships beside this raster puts the first pixel's center at ±(180-1/120).
    pix = scale[0]
    if abs(pix - 1 / 60) > 1e-9 or abs(scale[1] - 1 / 60) > 1e-9:
        raise SystemExit(f"unexpected pixel scale {scale}")
    origin_lon = -180.0 + pix / 2
    origin_lat = 90.0 - pix / 2

    def col_of(lon):
        return int(math.floor((lon - (origin_lon - pix / 2)) / pix))

    def row_of(lat):
        return int(math.floor(((origin_lat + pix / 2) - lat) / pix))

    c0 = max(0, col_of(gm.LON_W) - 2)
    c1 = min(width, col_of(gm.LON_E) + 3)
    r0 = max(0, row_of(gm.LAT_N) - 2)
    r1 = min(height, row_of(gm.LAT_S) + 3)
    rows = r1 - r0
    cols = c1 - c0
    buf = np.empty((rows, cols, 3), dtype=np.uint8)
    with path.open("rb") as f:
        for i, row in enumerate(range(r0, r1)):
            f.seek(offsets[row] + c0 * 3)
            raw = f.read(cols * 3)
            if len(raw) != cols * 3 or counts[row] < (c0 + cols) * 3:
                raise SystemExit(f"short TIFF row {row}")
            buf[i] = np.frombuffer(raw, dtype=np.uint8).reshape(cols, 3)
    west = origin_lon - pix / 2 + c0 * pix
    north = origin_lat + pix / 2 - r0 * pix
    return buf, west, north, pix


def write_image(tif_path):
    src, west, north, pix = tiff_crop(Path(tif_path))
    rows, cols, _ = src.shape
    ys = (np.arange(gm.BOARD_H) + 0.5) / gm.BOARD_H
    xs = (np.arange(gm.BOARD_W) + 0.5) / gm.BOARD_W
    lat = gm.LAT_N - ys * (gm.LAT_N - gm.LAT_S)
    lon = gm.LON_W + xs * (gm.LON_E - gm.LON_W)
    lon_g, lat_g = np.meshgrid(lon, lat)
    x = np.clip((lon_g - west) / pix - 0.5, 0, cols - 1.001)
    y = np.clip((north - lat_g) / pix - 0.5, 0, rows - 1.001)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.minimum(x0 + 1, cols - 1)
    y1 = np.minimum(y0 + 1, rows - 1)
    tx = (x - x0)[..., None]
    ty = (y - y0)[..., None]
    a = src[y0, x0].astype(np.float32)
    b = src[y0, x1].astype(np.float32)
    c = src[y1, x0].astype(np.float32)
    d = src[y1, x1].astype(np.float32)
    out = ((a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty).astype(np.uint8)
    image = Image.fromarray(out, "RGB")
    gm.BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(gm.BOARD_PATH, format="JPEG", quality=92, subsampling=0, optimize=True)
    print(f"wrote {gm.BOARD_PATH} {gm.BOARD_W}x{gm.BOARD_H}")


def clip_ring(ring, xmin, ymin, xmax, ymax):
    def clip_edge(pts, inside, intersect):
        if not pts:
            return []
        out = []
        prev = pts[-1]
        for cur in pts:
            if inside(cur):
                if not inside(prev):
                    out.append(intersect(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(intersect(prev, cur))
            prev = cur
        return out

    def lerp(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    pts = [(p[0], p[1]) for p in ring]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    pts = clip_edge(pts, lambda p: p[0] >= xmin, lambda a, b: lerp(a, b, (xmin - a[0]) / (b[0] - a[0] or 1e-12)))
    pts = clip_edge(pts, lambda p: p[0] <= xmax, lambda a, b: lerp(a, b, (xmax - a[0]) / (b[0] - a[0] or 1e-12)))
    pts = clip_edge(pts, lambda p: p[1] >= ymin, lambda a, b: lerp(a, b, (ymin - a[1]) / (b[1] - a[1] or 1e-12)))
    pts = clip_edge(pts, lambda p: p[1] <= ymax, lambda a, b: lerp(a, b, (ymax - a[1]) / (b[1] - a[1] or 1e-12)))
    return pts


def douglas(pts, eps):
    if len(pts) < 3:
        return pts
    ax, ay = pts[0]
    bx, by = pts[-1]
    dx, dy = bx - ax, by - ay
    span = dx * dx + dy * dy
    worst = -1.0
    index = 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        if span == 0:
            dist = math.hypot(px - ax, py - ay)
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / span))
            dist = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        if dist > worst:
            worst = dist
            index = i
    if worst <= eps:
        return [pts[0], pts[-1]]
    left = douglas(pts[: index + 1], eps)
    right = douglas(pts[index:], eps)
    return left[:-1] + right


def write_coast(shp_path):
    margin = 0.15
    xmin, ymin = gm.LON_W - margin, gm.LAT_S - margin
    xmax, ymax = gm.LON_E + margin, gm.LAT_N + margin
    reader = shapefile.Reader(shp_path)
    rings = []
    for shp in reader.shapes():
        bb = shp.bbox
        if bb[2] < xmin or bb[0] > xmax or bb[3] < ymin or bb[1] > ymax:
            continue
        parts = list(shp.parts) + [len(shp.points)]
        for a, b in zip(parts, parts[1:]):
            raw = shp.points[a:b]
            if not raw:
                continue
            xs = [p[0] for p in raw]
            ys = [p[1] for p in raw]
            if max(xs) < xmin or min(xs) > xmax or max(ys) < ymin or min(ys) > ymax:
                continue
            ring = clip_ring(raw, xmin, ymin, xmax, ymax)
            ring = douglas(ring, 0.012)
            cleaned = []
            for p in ring:
                q = (round(p[0], 5), round(p[1], 5))
                if not cleaned or cleaned[-1] != q:
                    cleaned.append(q)
            if len(cleaned) >= 3:
                rings.append([[p[0], p[1]] for p in cleaned])
    payload = {
        "source": "Natural Earth 1:10m land",
        "source_url": "https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip",
        "author": "Tom Patterson, Nathaniel Vaughn Kelso, and Natural Earth contributors",
        "license": "Public domain",
        "license_url": "https://www.naturalearthdata.com/about/terms-of-use/",
        "note": "Clipped to the campaign window and simplified to about 1 km. gen_map.py samples these rings.",
        "rings": rings,
    }
    gm.COAST_PATH.write_text(json.dumps(payload), encoding="utf-8")
    points = sum(len(r) for r in rings)
    print(f"wrote {gm.COAST_PATH} rings {len(rings)} points {points}")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_board_image.py HYP_HR_SR_W_DR.tif ne_10m_land.shp")
    write_coast(sys.argv[2])
    write_image(sys.argv[1])


if __name__ == "__main__":
    main()
