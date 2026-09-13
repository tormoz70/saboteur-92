#!/usr/bin/env python3
"""Slice saboteur2_world2.png into Godot TileSet atlases and RLE grids.

Classifies each 8x8 ZX cell as sky / earth / structure / wallpaper / mosaic
or leftover (skip). Sky is a ColorRect, not unique tiles.
Fan-map chrome (logo, mission legend, ninja art) is painted to sky first.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "world" / "saboteur2_world2.png"
# Pavero chrome on the original mosaic — cell rects, x1/y1 exclusive.
FAN_SKY_CELLS = (
    (0, 0, 140, 112),     # loading-screen logo, Pavero credit, maps.speccy.cz
    (936, 0, 1024, 500),  # mission list + ninja; ground belt starts ~y=500
)
OUT_WORLD = ROOT / "assets" / "world"
OUT_TILESETS = ROOT / "assets" / "tilesets"
OUT_REPORT = ROOT / "docs" / "audit_views"

CELL = 8
SCALE = 2
SCREEN = (256, 192)

SKY_BLUE = (0, 0, 206)
SKY_BLUE_B = (0, 0, 255)
BLACK = (0, 0, 0)
GREEN = (0, 251, 0)
RED = (255, 0, 0)

CLS_SKY = "sky"
CLS_EARTH = "earth"
CLS_STRUCTURE = "structure"
CLS_WALLPAPER = "wallpaper"
CLS_MOSAIC = "mosaic"
CLS_SKIP = "skip"

VISUAL_LAYERS = ("earth", "structure", "wallpaper", "mosaic")
LAYER_Z = {
    "earth": -20,
    "structure": -10,
    "wallpaper": -5,
    "mosaic": -4,
}

OVERLAY_COLORS = {
    CLS_SKY: (0, 40, 160),
    CLS_EARTH: (48, 48, 48),
    CLS_STRUCTURE: (220, 0, 0),
    CLS_WALLPAPER: (40, 80, 255),
    CLS_MOSAIC: (0, 200, 0),
    CLS_SKIP: (255, 0, 255),
}

KNOWN = {
    (0, 0): CLS_SKY,
    (10, 10): CLS_SKY,
    (222, 52): CLS_STRUCTURE,
    (280, 90): CLS_MOSAIC,
    (108, 280): CLS_WALLPAPER,
    (700, 350): CLS_EARTH,
    (150, 350): CLS_EARTH,
    (226, 44): CLS_SKIP,
    (321, 111): CLS_SKIP,
}


def _is_sky_blue_rgb(r: int, g: int, b: int) -> bool:
    return (r, g, b) == SKY_BLUE or (r, g, b) == SKY_BLUE_B


def cell_bytes(raw: memoryview, width: int, cx: int, cy: int) -> bytes:
    chunks: list[bytes] = []
    x0 = cx * CELL
    for y in range(CELL):
        row = ((cy * CELL + y) * width + x0) * 3
        chunks.append(bytes(raw[row : row + CELL * 3]))
    return b"".join(chunks)


def _count_ink(buf: bytes, ink: tuple[int, int, int]) -> int:
    ir, ig, ib = ink
    n = 0
    for i in range(0, len(buf), 3):
        if buf[i] == ir and buf[i + 1] == ig and buf[i + 2] == ib:
            n += 1
    return n


def _row_ink(buf: bytes, y: int, ink: tuple[int, int, int]) -> int:
    ir, ig, ib = ink
    n = 0
    off = y * CELL * 3
    for x in range(CELL):
        i = off + x * 3
        if buf[i] == ir and buf[i + 1] == ig and buf[i + 2] == ib:
            n += 1
    return n


def _is_zx_brick(buf: bytes, ink: tuple[int, int, int]) -> bool:
    if _count_ink(buf, ink) < 20:
        return False
    brick_rows = 0
    mortar_rows = 0
    for y in range(CELL):
        n = _row_ink(buf, y, ink)
        if n >= 6:
            brick_rows += 1
        elif n == 0:
            mortar_rows += 1
    return brick_rows >= 4 and mortar_rows >= 1


def _pix(buf: bytes, x: int, y: int) -> tuple[int, int, int]:
    i = (y * CELL + x) * 3
    return buf[i], buf[i + 1], buf[i + 2]


def _is_checker_lattice(buf: bytes) -> bool:
    alt = 0
    for y in range(CELL - 1):
        for x in range(CELL - 1):
            a = _is_sky_blue_rgb(*_pix(buf, x, y))
            b = _is_sky_blue_rgb(*_pix(buf, x + 1, y))
            c = _is_sky_blue_rgb(*_pix(buf, x, y + 1))
            d = _is_sky_blue_rgb(*_pix(buf, x + 1, y + 1))
            if a and d and not b and not c:
                alt += 1
            elif b and c and not a and not d:
                alt += 1
    return alt >= 8


def _color_counts(buf: bytes) -> tuple[int, int, int, int, int]:
    red_n = 0
    green_n = 0
    blue_n = 0
    black_n = 0
    other_n = 0
    for i in range(0, len(buf), 3):
        p = (buf[i], buf[i + 1], buf[i + 2])
        if p == RED:
            red_n += 1
        elif p == GREEN:
            green_n += 1
        elif _is_sky_blue_rgb(*p):
            blue_n += 1
        elif p == BLACK:
            black_n += 1
        else:
            other_n += 1
    return red_n, green_n, blue_n, black_n, other_n


def _is_pure(red_n: int, green_n: int, blue_n: int, other_n: int, ink: str) -> bool:
    if other_n:
        return False
    if ink == "green":
        return green_n > 0 and red_n == 0 and blue_n == 0
    if ink == "blue":
        return blue_n > 0 and red_n == 0 and green_n == 0
    return False


def _is_structure_architecture(buf: bytes, red_n: int, green_n: int, other_n: int) -> bool:
    if _is_zx_brick(buf, RED):
        return True
    # Solid red wall fill, not a chair/table fragment.
    return red_n >= 56 and green_n == 0 and other_n == 0


def classify_cell(buf: bytes) -> str:
    red_n, green_n, blue_n, black_n, other_n = _color_counts(buf)

    if other_n >= 4:
        return CLS_SKIP
    if black_n == 64:
        return CLS_EARTH
    if blue_n >= 60 and red_n == 0 and green_n == 0:
        return CLS_SKY
    if _is_structure_architecture(buf, red_n, green_n, other_n):
        return CLS_STRUCTURE
    if green_n >= 20 and _is_pure(red_n, green_n, blue_n, other_n, "green"):
        return CLS_MOSAIC
    if (
        (_is_zx_brick(buf, SKY_BLUE) or _is_zx_brick(buf, SKY_BLUE_B))
        and _is_pure(red_n, green_n, blue_n, other_n, "blue")
    ):
        return CLS_WALLPAPER
    if _is_checker_lattice(buf):
        return CLS_SKIP
    if other_n == 0 and green_n == 0 and red_n == 0 and black_n >= 40:
        return CLS_EARTH
    return CLS_SKIP


_DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def allowed_glyphs(
    labels: list[str],
    bufs: list[bytes],
    kind: str,
    min_count: int,
    max_keep: int | None = None,
) -> set[bytes]:
    freq: Counter[bytes] = Counter()
    for i, label in enumerate(labels):
        if label == kind:
            freq[bufs[i]] += 1
    items = [(buf, count) for buf, count in freq.items() if count >= min_count]
    items.sort(key=lambda item: -item[1])
    if max_keep is not None:
        items = items[:max_keep]
    return {buf for buf, _ in items}


def _fill_rgb(buf: bytearray, color: tuple[int, int, int]) -> None:
    r, g, b = color
    for i in range(0, len(buf), 3):
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def _blit_cell(dest: bytearray, width: int, cx: int, cy: int, tile: bytes) -> None:
    x0 = cx * CELL
    src_row = CELL * 3
    for y in range(CELL):
        dst = ((cy * CELL + y) * width + x0) * 3
        src = y * src_row
        dest[dst : dst + src_row] = tile[src : src + src_row]


def demote_uncommon_background(
    labels: list[str], bufs: list[bytes], allowed: dict[str, set[bytes]]
) -> int:
    """Rare mosaic/wallpaper stamps are furniture crumbs — send them to skip."""
    demoted = 0
    for i, kind in enumerate(labels):
        allow = allowed.get(kind)
        if allow is None:
            continue
        if bufs[i] not in allow:
            labels[i] = CLS_SKIP
            demoted += 1
    return demoted


def demote_furniture_structure(
    labels: list[str], bufs: list[bytes], cw: int, ch: int
) -> int:
    """Red chairs/tables sit on brick floors; they must not stay structure."""
    demoted = 0
    for y in range(ch):
        for x in range(cw):
            i = y * cw + x
            if labels[i] != CLS_STRUCTURE:
                continue
            red_n, green_n, _blue_n, _black_n, other_n = _color_counts(bufs[i])
            if _is_structure_architecture(bufs[i], red_n, green_n, other_n):
                continue
            touches_bg = False
            for dx, dy in _DIRS:
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                    continue
                nk = labels[ny * cw + nx]
                if nk in (CLS_MOSAIC, CLS_WALLPAPER):
                    touches_bg = True
                    break
            if touches_bg:
                labels[i] = CLS_SKIP
                demoted += 1
    return demoted


def fill_skip_sky_with_background(labels: list[str], cw: int, ch: int) -> int:
    """Paint skip holes that sit inside mosaic or wallpaper.

    Sky is never converted here. Skip cells that touch sky stay leftover:
    outdoor grass, trees and sprites must not become room wallpaper.
    """
    filled = 0
    changed = True
    while changed:
        changed = False
        updates: list[tuple[int, str]] = []
        for y in range(ch):
            for x in range(cw):
                i = y * cw + x
                if labels[i] != CLS_SKIP:
                    continue
                mosaic_n = 0
                wallpaper_n = 0
                sky_n = 0
                for dx, dy in _DIRS:
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                        sky_n += 1
                        continue
                    nk = labels[ny * cw + nx]
                    if nk == CLS_MOSAIC:
                        mosaic_n += 1
                    elif nk == CLS_WALLPAPER:
                        wallpaper_n += 1
                    elif nk == CLS_SKY:
                        sky_n += 1
                if sky_n or mosaic_n + wallpaper_n == 0:
                    continue
                winner = CLS_MOSAIC if mosaic_n >= wallpaper_n else CLS_WALLPAPER
                updates.append((i, winner))
        for i, winner in updates:
            if labels[i] != winner:
                labels[i] = winner
                filled += 1
                changed = True
    return filled


def demote_exposed_mosaic(labels: list[str], cw: int, ch: int) -> int:
    """Outdoor grass: a mosaic row with sky above and earth below is leftover."""
    demoted = 0
    for y in range(1, ch - 1):
        for x in range(cw):
            i = y * cw + x
            if labels[i] != CLS_MOSAIC:
                continue
            if labels[(y - 1) * cw + x] != CLS_SKY:
                continue
            if labels[(y + 1) * cw + x] != CLS_EARTH:
                continue
            labels[i] = CLS_SKIP
            demoted += 1
    return demoted


def demote_mosaic_islands(labels: list[str], cw: int, ch: int, max_size: int = 96) -> int:
    """Trees and bushes: small mosaic CCs whose border is mostly sky/earth/skip."""
    seen = [False] * (cw * ch)
    demoted = 0
    for start in range(cw * ch):
        if labels[start] != CLS_MOSAIC or seen[start]:
            continue
        stack = [start]
        seen[start] = True
        comp: list[int] = []
        border: Counter[str] = Counter()
        while stack:
            i = stack.pop()
            comp.append(i)
            x, y = i % cw, i // cw
            for dx, dy in _DIRS:
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                    border[CLS_SKY] += 1
                    continue
                ni = ny * cw + nx
                nk = labels[ni]
                if nk == CLS_MOSAIC:
                    if not seen[ni]:
                        seen[ni] = True
                        stack.append(ni)
                    continue
                border[nk] += 1
        if len(comp) > max_size or not border:
            continue
        outdoor = border[CLS_SKY] + border[CLS_SKIP] + border[CLS_EARTH]
        if outdoor * 2 < sum(border.values()):
            continue
        for i in comp:
            labels[i] = CLS_SKIP
            demoted += 1
    return demoted


def secret_basement_cells(labels: list[str], cw: int, ch: int) -> set[int]:
    """Invincibility room: a tall red-brick mass in earth, not HQ floor strips.

    That brick is room wallpaper, not solid structure.
    """
    seen = [False] * (cw * ch)
    out: set[int] = set()
    for start in range(cw * ch):
        if labels[start] != CLS_STRUCTURE or seen[start]:
            continue
        stack = [start]
        seen[start] = True
        comp: list[int] = []
        while stack:
            i = stack.pop()
            comp.append(i)
            x, y = i % cw, i // cw
            for dx, dy in _DIRS:
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                    continue
                ni = ny * cw + nx
                if seen[ni] or labels[ni] != CLS_STRUCTURE:
                    continue
                seen[ni] = True
                stack.append(ni)
        ys = [i // cw for i in comp]
        height = max(ys) - min(ys) + 1
        if len(comp) < 50 or height < 8:
            continue
        earth_n = 0
        mosaic_n = 0
        for i in comp:
            x, y = i % cw, i // cw
            for dx, dy in _DIRS:
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                    continue
                nk = labels[ny * cw + nx]
                if nk == CLS_EARTH:
                    earth_n += 1
                elif nk == CLS_MOSAIC:
                    mosaic_n += 1
        if earth_n > mosaic_n * 2:
            out.update(comp)
    return out


def _peel_basement_ladder(
    extra: set[int],
    crate_fill: set[int],
    labels: list[str],
    original: list[str],
    bufs: list[bytes],
    basement: set[int],
    cw: int,
) -> None:
    """Keep the room ladder as leftover; fill its shaft with mode brick."""
    paper = basement | extra
    if not paper:
        return
    y_lo = min(i // cw for i in basement)
    y_hi = max(i // cw for i in basement)
    span = y_hi - y_lo + 1
    xs = [i % cw for i in paper]
    cols: dict[int, list[int]] = defaultdict(list)
    for y in range(y_lo, y_hi + 1):
        for x in range(min(xs), max(xs) + 1):
            i = y * cw + x
            if original[i] != CLS_SKIP:
                continue
            red_n, green_n, _blue_n, _black_n, other_n = _color_counts(bufs[i])
            if green_n or other_n or not red_n:
                continue
            cols[x].append(i)
    ladder: set[int] = set()
    for cells in cols.values():
        col_ys = [i // cw for i in cells]
        if max(col_ys) - min(col_ys) + 1 >= span - 1 and len(cells) >= span - 2:
            ladder.update(cells)
    for i in ladder:
        extra.discard(i)
        labels[i] = CLS_WALLPAPER
        crate_fill.add(i)


def restore_secret_basement(
    labels: list[str],
    original: list[str],
    bufs: list[bytes],
    basement: set[int],
    cw: int,
    ch: int,
) -> tuple[int, set[int], set[int]]:
    """Put the red-paper room back, grow brick drips, hide leftover on earth."""
    restored = 0
    for i in basement:
        if labels[i] != CLS_WALLPAPER:
            restored += 1
        labels[i] = CLS_WALLPAPER
    extra: set[int] = set()
    crate_fill: set[int] = set()
    if not basement:
        return restored, extra, crate_fill
    dirs8 = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)
    ys = [i // cw for i in basement]
    y_min = min(ys)
    frontier = set(basement)
    while frontier:
        nxt: set[int] = set()
        for i in frontier:
            x, y = i % cw, i // cw
            for dx, dy in dirs8:
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= cw or ny >= ch or ny < y_min:
                    continue
                ni = ny * cw + nx
                if ni in basement or ni in extra:
                    continue
                if labels[ni] != CLS_SKIP:
                    continue
                red_n, green_n, _blue_n, _black_n, other_n = _color_counts(bufs[ni])
                if green_n or other_n or red_n < 1:
                    continue
                labels[ni] = CLS_WALLPAPER
                extra.add(ni)
                nxt.add(ni)
        frontier = nxt
    paper = basement | extra
    xs = [i % cw for i in paper]
    ys = [i // cw for i in paper]
    x0, x1 = min(xs) - 2, max(xs) + 2
    y0, y1 = min(ys), max(ys) + 8
    for y in range(max(0, y0), min(ch, y1 + 1)):
        for x in range(max(0, x0), min(cw, x1 + 1)):
            i = y * cw + x
            if i in paper or i in crate_fill:
                continue
            if labels[i] == CLS_WALLPAPER and original[i] == CLS_EARTH:
                labels[i] = CLS_EARTH
            red_n, green_n, _blue_n, _black_n, other_n = _color_counts(bufs[i])
            if original[i] == CLS_SKIP and red_n and not green_n and not other_n:
                labels[i] = CLS_WALLPAPER
                extra.add(i)
                continue
            if original[i] == CLS_SKIP and y <= max(ys):
                labels[i] = CLS_WALLPAPER
                crate_fill.add(i)
                continue
            if labels[i] == CLS_SKIP:
                labels[i] = CLS_EARTH
    _peel_basement_ladder(extra, crate_fill, labels, original, bufs, basement, cw)
    return restored, extra, crate_fill


def fill_small_islands(
    labels: list[str],
    cw: int,
    ch: int,
    kind: str,
    into: set[str],
    max_size: int,
    prefer: tuple[str, ...] = (),
) -> int:
    """Paint a small CC of `kind` as the majority border label, if that label is in `into`."""
    seen = [False] * (cw * ch)
    filled = 0
    for start in range(cw * ch):
        if labels[start] != kind or seen[start]:
            continue
        stack = [start]
        seen[start] = True
        comp: list[int] = []
        border: Counter[str] = Counter()
        while stack:
            i = stack.pop()
            comp.append(i)
            x, y = i % cw, i // cw
            for dx, dy in _DIRS:
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                    continue
                ni = ny * cw + nx
                nk = labels[ni]
                if nk == kind:
                    if not seen[ni]:
                        seen[ni] = True
                        stack.append(ni)
                    continue
                border[nk] += 1
        if len(comp) > max_size or not border:
            continue
        winner = None
        for p in prefer:
            if p in into and border[p]:
                winner = p
                break
        if winner is None:
            winner, votes = border.most_common(1)[0]
            if winner not in into or votes * 2 < sum(border.values()):
                continue
        paint = CLS_SKY if winner == CLS_SKIP else winner
        for i in comp:
            labels[i] = paint
            filled += 1
    return filled


def erode_into(
    labels: list[str],
    cw: int,
    ch: int,
    kind: str,
    bg: str,
    min_votes: int = 5,
    max_passes: int = 3,
) -> int:
    """Peel `kind` cells that are mostly surrounded by `bg`."""
    dirs8 = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)
    filled = 0
    for _ in range(max_passes):
        updates: list[int] = []
        for y in range(ch):
            for x in range(cw):
                i = y * cw + x
                if labels[i] != kind:
                    continue
                votes = 0
                for dx, dy in dirs8:
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                        if bg == CLS_SKY:
                            votes += 1
                        continue
                    if labels[ny * cw + nx] == bg:
                        votes += 1
                if votes >= min_votes:
                    updates.append(i)
        if not updates:
            break
        for i in updates:
            labels[i] = bg
            filled += 1
    return filled


def trim_thin_earth_strips(labels: list[str], cw: int, ch: int) -> int:
    """1-cell vertical earth bars inside rooms — leftover object stems.

    Horizontal earth ledges stay: they are indoor dirt stairs, not furniture.
    """
    bg = {CLS_WALLPAPER, CLS_MOSAIC}
    filled = 0
    changed = True
    while changed:
        changed = False
        updates: list[tuple[int, str]] = []
        for y in range(ch):
            for x in range(cw):
                i = y * cw + x
                if labels[i] != CLS_EARTH:
                    continue

                def neigh(dx: int, dy: int) -> str:
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                        return CLS_SKY
                    return labels[ny * cw + nx]

                left, right = neigh(-1, 0), neigh(1, 0)
                if left in bg and right in bg:
                    updates.append((i, left))
        for i, winner in updates:
            if labels[i] != winner:
                labels[i] = winner
                filled += 1
                changed = True
    return filled


def close_room_gaps(
    labels: list[str], cw: int, ch: int, room: str, max_gap: int
) -> int:
    """Fill short skip gaps between room tiles on the same row.

    Objects on a tunnel floor sit in the wallpaper/mosaic band with room tiles
    on both sides. Dirt stairs and ledges stay earth.
    """
    plug = {CLS_SKIP}
    filled = 0
    for y in range(ch):
        base = y * cw
        x = 0
        while x < cw:
            while x < cw and labels[base + x] != room:
                x += 1
            if x >= cw:
                break
            while x < cw and labels[base + x] == room:
                x += 1
            gap_start = x
            while x < cw and labels[base + x] in plug:
                x += 1
            gap_end = x
            if 1 <= (gap_end - gap_start) <= max_gap and x < cw and labels[base + x] == room:
                # Roof terraces have sky above; indoor floors do not.
                if y > 0 and any(
                    labels[(y - 1) * cw + g] == CLS_SKY
                    for g in range(gap_start, gap_end)
                ):
                    continue
                for g in range(gap_start, gap_end):
                    labels[base + g] = room
                    filled += 1
    return filled


def fill_boxed_into_room(
    labels: list[str], cw: int, ch: int, room: str, max_passes: int = 8
) -> int:
    """Skip boxed by room tiles: wall alcoves and 1-cell-tall shelves."""
    plug = {CLS_SKIP}
    filled = 0
    for _ in range(max_passes):
        updates: list[int] = []
        for y in range(ch):
            for x in range(cw):
                i = y * cw + x
                if labels[i] not in plug:
                    continue

                def at(dx: int, dy: int) -> str | None:
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                        return None
                    return labels[ny * cw + nx]

                up, down, left, right = at(0, -1), at(0, 1), at(-1, 0), at(1, 0)
                room_n = sum(1 for s in (up, down, left, right) if s == room)
                on_brick_floor = up == room and down == CLS_STRUCTURE
                if room_n >= 3 or (up == room and down == room) or on_brick_floor:
                    updates.append(i)
        if not updates:
            break
        for i in updates:
            labels[i] = room
            filled += 1
    return filled


def fill_wallpaper_in_structure(labels: list[str], cw: int, ch: int) -> int:
    """Blue brick crumbs stuck inside red brick (lift/object leftovers)."""
    filled = 0
    changed = True
    while changed:
        changed = False
        for y in range(ch):
            for x in range(cw):
                i = y * cw + x
                if labels[i] != CLS_WALLPAPER:
                    continue

                def at(dx: int, dy: int) -> str | None:
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                        return None
                    return labels[ny * cw + nx]

                up, down, left, right = at(0, -1), at(0, 1), at(-1, 0), at(1, 0)
                if (left == CLS_STRUCTURE and right == CLS_STRUCTURE) or (
                    up == CLS_STRUCTURE and down == CLS_STRUCTURE
                ):
                    labels[i] = CLS_STRUCTURE
                    filled += 1
                    changed = True
    return filled


def fill_edge_notches(
    labels: list[str], cw: int, ch: int, room: str, max_depth: int = 16
) -> int:
    """Fill skip bites in a room facade: this row's edge is indented vs both neighbours."""
    plug = {CLS_SKIP}
    left: list[int | None] = [None] * ch
    right: list[int | None] = [None] * ch
    for y in range(ch):
        for x in range(cw):
            if labels[y * cw + x] == room:
                if left[y] is None:
                    left[y] = x
                right[y] = x
    filled = 0
    for y in range(ch):
        if left[y] is None:
            continue
        nearby_l = [
            left[y + d]
            for d in range(-4, 5)
            if d != 0 and 0 <= y + d < ch and left[y + d] is not None
        ]
        if len(nearby_l) >= 3:
            nearby_l.sort()
            med = nearby_l[len(nearby_l) // 2]
            if 2 <= left[y] - med <= max_depth:
                for x in range(med, left[y]):
                    i = y * cw + x
                    if labels[i] in plug:
                        labels[i] = room
                        filled += 1
        nearby_r = [
            right[y + d]
            for d in range(-4, 5)
            if d != 0 and 0 <= y + d < ch and right[y + d] is not None
        ]
        if right[y] is not None and len(nearby_r) >= 3:
            nearby_r.sort()
            med_r = nearby_r[len(nearby_r) // 2]
            if 2 <= med_r - right[y] <= max_depth:
                for x in range(right[y] + 1, med_r + 1):
                    i = y * cw + x
                    if labels[i] in plug:
                        labels[i] = room
                        filled += 1
    return filled


def fill_wallpaper_near_structure(labels: list[str], cw: int, ch: int) -> int:
    """Wallpaper shaft stuck in red brick leftover."""
    dirs8 = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)
    filled = 0
    changed = True
    while changed:
        changed = False
        updates: list[int] = []
        for y in range(ch):
            for x in range(cw):
                i = y * cw + x
                if labels[i] != CLS_WALLPAPER:
                    continue
                votes = 0
                for dx, dy in dirs8:
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
                        continue
                    if labels[ny * cw + nx] == CLS_STRUCTURE:
                        votes += 1
                if votes >= 3:
                    updates.append(i)
        for i in updates:
            labels[i] = CLS_STRUCTURE
            filled += 1
            changed = True
    return filled


def rle_encode(ids: list[int]) -> list[int]:
    if not ids:
        return []
    out: list[int] = []
    prev = ids[0]
    count = 1
    for value in ids[1:]:
        if value == prev:
            count += 1
        else:
            out.append(prev)
            out.append(count)
            prev = value
            count = 1
    out.append(prev)
    out.append(count)
    return out


def pack_atlas(tiles: list[Image.Image], cols: int) -> Image.Image:
    n = len(tiles)
    rows = max(1, math.ceil(n / cols))
    atlas = Image.new("RGBA", (cols * CELL, rows * CELL), (0, 0, 0, 0))
    for i, tile in enumerate(tiles):
        x = (i % cols) * CELL
        y = (i // cols) * CELL
        atlas.paste(tile.convert("RGBA"), (x, y))
    return atlas


def write_tileset_tres(path: Path, texture_res: str, cols: int, n_tiles: int) -> None:
    rows = max(1, math.ceil(n_tiles / cols))
    lines = [
        '[gd_resource type="TileSet" load_steps=2 format=3]',
        "",
        f'[ext_resource type="Texture2D" path="{texture_res}" id="1"]',
        "",
        '[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_1"]',
        "texture = ExtResource(\"1\")",
        "texture_region_size = Vector2i(8, 8)",
        "use_texture_padding = true",
    ]
    for i in range(n_tiles):
        x = i % cols
        y = i // cols
        lines.append(f"{x}:{y}/0 = 0")
    lines.extend(
        [
            "",
            "[resource]",
            "tile_size = Vector2i(8, 8)",
            'sources/0 = SubResource("TileSetAtlasSource_1")',
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    _ = rows


def write_collision_tres(path: Path) -> None:
    lines = [
        '[gd_resource type="TileSet" load_steps=2 format=3]',
        "",
        '[ext_resource type="Texture2D" path="res://assets/tilesets/s2_collision_tileset.png" id="1"]',
        "",
        '[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_1"]',
        "texture = ExtResource(\"1\")",
        "texture_region_size = Vector2i(8, 8)",
        "use_texture_padding = true",
        '0:0/0 = 0',
        '0:0/0/custom_data_0 = "empty"',
        '1:0/0 = 0',
        '1:0/0/custom_data_0 = "solid"',
        '2:0/0 = 0',
        '2:0/0/custom_data_0 = "ladder"',
        '3:0/0 = 0',
        '3:0/0/custom_data_0 = "oneway"',
        "",
        "[resource]",
        "tile_size = Vector2i(8, 8)",
        'custom_data_layer_0/name = "collision_type"',
        "custom_data_layer_0/type = 4",
        'sources/0 = SubResource("TileSetAtlasSource_1")',
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_collision_png(path: Path) -> None:
    img = Image.new("RGBA", (CELL * 4, CELL), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = [
        (0, 0, 0, 0),
        (200, 40, 40, 255),
        (220, 200, 40, 255),
        (40, 180, 220, 255),
    ]
    for i, color in enumerate(colors):
        if color[3] == 0:
            continue
        x0 = i * CELL
        draw.rectangle([x0, 0, x0 + CELL - 1, CELL - 1], fill=color)
    img.save(path)


def _empty_tile() -> Image.Image:
    return Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))


def paint_fan_chrome(img: Image.Image) -> None:
    """Erase Pavero logo, legend and ninja art so they never become tiles."""
    draw = ImageDraw.Draw(img)
    for cx0, cy0, cx1, cy1 in FAN_SKY_CELLS:
        draw.rectangle(
            [cx0 * CELL, cy0 * CELL, cx1 * CELL - 1, cy1 * CELL - 1],
            fill=SKY_BLUE,
        )


def check_known(raw: memoryview, width: int) -> None:
    errors: list[str] = []
    for (cx, cy), want in KNOWN.items():
        got = classify_cell(cell_bytes(raw, width, cx, cy))
        if got != want:
            errors.append(f"cell {cx},{cy}: want {want}, got {got}")
    if errors:
        raise SystemExit("classification self-check failed:\n  " + "\n  ".join(errors))


def _tile_from_bytes(buf: bytes) -> Image.Image:
    return Image.frombytes("RGB", (CELL, CELL), buf).convert("RGBA")


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")
    src = Image.open(SRC).convert("RGB")
    width, height = src.size
    if width % CELL or height % CELL:
        raise SystemExit(f"{SRC} size {width}x{height} is not divisible by {CELL}")
    paint_fan_chrome(src)
    cw = width // CELL
    ch = height // CELL
    raw = memoryview(src.tobytes())
    check_known(raw, width)

    labels = [CLS_SKIP] * (cw * ch)
    cell_bufs = [b""] * (cw * ch)
    for cy in range(ch):
        for cx in range(cw):
            i = cy * cw + cx
            buf = cell_bytes(raw, width, cx, cy)
            cell_bufs[i] = buf
            labels[i] = classify_cell(buf)

    original = list(labels)
    basement = secret_basement_cells(original, cw, ch)
    allowed = {
        # HQ mosaic is one repeating 8x8. Extra green+black stamps are furniture legs.
        CLS_MOSAIC: allowed_glyphs(labels, cell_bufs, CLS_MOSAIC, 1, max_keep=1),
        CLS_WALLPAPER: allowed_glyphs(labels, cell_bufs, CLS_WALLPAPER, 100, max_keep=2),
    }
    n_uncommon = demote_uncommon_background(labels, cell_bufs, allowed)
    n_furniture = demote_furniture_structure(labels, cell_bufs, cw, ch)
    n_roof_mosaic = demote_exposed_mosaic(labels, cw, ch)
    n_mosaic_sky = demote_mosaic_islands(labels, cw, ch)
    n_skip_fill = fill_skip_sky_with_background(labels, cw, ch)
    n_earth_fill = fill_small_islands(
        labels, cw, ch, CLS_EARTH, {CLS_MOSAIC, CLS_WALLPAPER}, 12
    )
    n_earth_sky = fill_small_islands(
        labels, cw, ch, CLS_EARTH, {CLS_SKY, CLS_SKIP}, 32
    )
    n_wp_earth = fill_small_islands(
        labels, cw, ch, CLS_WALLPAPER, {CLS_EARTH}, 8
    )
    n_mosaic_earth = fill_small_islands(
        labels, cw, ch, CLS_MOSAIC, {CLS_EARTH}, 8
    )
    n_skip_earth = fill_small_islands(
        labels,
        cw,
        ch,
        CLS_SKIP,
        {CLS_EARTH, CLS_MOSAIC, CLS_WALLPAPER},
        16,
        prefer=(CLS_MOSAIC, CLS_WALLPAPER),
    )
    n_erode = 0
    n_erode += erode_into(labels, cw, ch, CLS_EARTH, CLS_SKY)
    n_erode += erode_into(labels, cw, ch, CLS_EARTH, CLS_WALLPAPER)
    n_erode += erode_into(
        labels, cw, ch, CLS_STRUCTURE, CLS_EARTH, min_votes=5, max_passes=8
    )
    n_erode += erode_into(
        labels, cw, ch, CLS_WALLPAPER, CLS_EARTH, min_votes=5, max_passes=6
    )
    n_hang = 0
    changed = True
    while changed:
        changed = False
        for y in range(1, ch):
            for x in range(cw):
                i = y * cw + x
                if labels[i] != CLS_STRUCTURE:
                    continue
                if labels[(y - 1) * cw + x] != CLS_EARTH:
                    continue
                earth_n = 0
                for dx, dy in _DIRS:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < cw and 0 <= ny < ch and labels[ny * cw + nx] == CLS_EARTH:
                        earth_n += 1
                if earth_n >= 2:
                    labels[i] = CLS_EARTH
                    n_hang += 1
                    changed = True
    n_erode += n_hang
    n_wp_earth += fill_small_islands(
        labels, cw, ch, CLS_WALLPAPER, {CLS_EARTH}, 40
    )
    n_erode += trim_thin_earth_strips(labels, cw, ch)
    n_room_gaps = 0
    n_room_gaps += close_room_gaps(labels, cw, ch, CLS_WALLPAPER, 12)
    n_room_gaps += close_room_gaps(labels, cw, ch, CLS_MOSAIC, 20)
    n_boxed = 0
    n_boxed += fill_boxed_into_room(labels, cw, ch, CLS_MOSAIC)
    n_boxed += fill_boxed_into_room(labels, cw, ch, CLS_WALLPAPER)
    n_notch = 0
    n_notch += fill_edge_notches(labels, cw, ch, CLS_MOSAIC)
    n_notch += fill_edge_notches(labels, cw, ch, CLS_WALLPAPER)
    n_room_gaps += close_room_gaps(labels, cw, ch, CLS_MOSAIC, 24)
    n_wp_in_brick = fill_wallpaper_in_structure(labels, cw, ch)
    n_wp_in_brick += fill_small_islands(
        labels, cw, ch, CLS_WALLPAPER, {CLS_STRUCTURE}, 48
    )
    n_wp_mosaic = fill_small_islands(
        labels, cw, ch, CLS_WALLPAPER, {CLS_MOSAIC}, 16
    )
    n_mosaic_sky += demote_exposed_mosaic(labels, cw, ch)
    n_mosaic_sky += demote_mosaic_islands(labels, cw, ch)
    n_sky_rooms = fill_small_islands(
        labels,
        cw,
        ch,
        CLS_SKY,
        {CLS_MOSAIC, CLS_WALLPAPER},
        80,
        prefer=(CLS_MOSAIC, CLS_WALLPAPER),
    )
    n_skip_fill += fill_skip_sky_with_background(labels, cw, ch)
    n_earth_fill += fill_small_islands(
        labels, cw, ch, CLS_EARTH, {CLS_MOSAIC, CLS_WALLPAPER}, 12
    )
    n_basement, drip_cells, basement_fill = restore_secret_basement(
        labels, original, cell_bufs, basement, cw, ch
    )
    basement |= drip_cells
    n_wp_earth += fill_small_islands(
        labels, cw, ch, CLS_WALLPAPER, {CLS_EARTH}, 12
    )
    n_skip_earth += fill_small_islands(
        labels, cw, ch, CLS_SKIP, {CLS_EARTH}, 128
    )
    # Motorcycle / chrome crumbs classify as ZX red brick but sit in cave tunnels.
    n_st_wp = fill_small_islands(
        labels, cw, ch, CLS_STRUCTURE, {CLS_WALLPAPER}, 8
    )
    object_mask = [
        i not in basement
        and (
            original[i] == CLS_SKIP
            or labels[i] == CLS_SKIP
            or (
                original[i] != labels[i]
                and original[i] in (CLS_EARTH, CLS_STRUCTURE, CLS_WALLPAPER, CLS_SKY)
            )
        )
        for i in range(cw * ch)
    ]
    counts = Counter(labels)

    mode_tile: dict[str, bytes] = {}
    earth_freq: Counter[bytes] = Counter()
    for i, kind in enumerate(original):
        if kind == CLS_EARTH:
            earth_freq[cell_bufs[i]] += 1
    mode_tile[CLS_EARTH] = (
        earth_freq.most_common(1)[0][0] if earth_freq else b"\x00" * (CELL * CELL * 3)
    )
    for name in (CLS_MOSAIC, CLS_WALLPAPER):
        raw_freq: Counter[bytes] = Counter()
        for i, kind in enumerate(original):
            if kind == name and cell_bufs[i] in allowed[name]:
                raw_freq[cell_bufs[i]] += 1
        mode_tile[name] = (
            raw_freq.most_common(1)[0][0]
            if raw_freq
            else b"\x00" * (CELL * CELL * 3)
        )
    basement_mode = (
        Counter(cell_bufs[i] for i in basement).most_common(1)[0][0]
        if basement
        else mode_tile[CLS_WALLPAPER]
    )

    layer_tiles: dict[str, dict[bytes, int]] = {name: {} for name in VISUAL_LAYERS}
    layer_images: dict[str, list[Image.Image]] = {name: [_empty_tile()] for name in VISUAL_LAYERS}
    layer_ids: dict[str, list[int]] = {name: [0] * (cw * ch) for name in VISUAL_LAYERS}
    collision_ids = [0] * (cw * ch)
    leftover_buf = bytearray(width * height * 3)
    overlay_buf = bytearray(cw * ch * 3)
    rebuild_buf = bytearray(width * height * 3)
    _fill_rgb(rebuild_buf, SKY_BLUE)

    for cy in range(ch):
        for cx in range(cw):
            i = cy * cw + cx
            kind = labels[i]
            oc = OVERLAY_COLORS[kind]
            o = i * 3
            overlay_buf[o] = oc[0]
            overlay_buf[o + 1] = oc[1]
            overlay_buf[o + 2] = oc[2]
            raw_kind = original[i]
            if kind == CLS_SKIP or object_mask[i]:
                x0 = cx * CELL
                for y in range(CELL):
                    src_off = ((cy * CELL + y) * width + x0) * 3
                    leftover_buf[src_off : src_off + CELL * 3] = raw[
                        src_off : src_off + CELL * 3
                    ]
            if kind == CLS_SKIP:
                continue
            if kind == CLS_SKY:
                continue
            if kind in (CLS_EARTH, CLS_STRUCTURE):
                collision_ids[i] = 1
            buf = cell_bufs[i]
            if kind == CLS_MOSAIC:
                buf = mode_tile[kind]
            elif kind == CLS_WALLPAPER and i in basement:
                buf = cell_bufs[i]
            elif kind == CLS_WALLPAPER and i in basement_fill:
                buf = basement_mode
            elif kind == CLS_WALLPAPER and (
                raw_kind != kind or buf not in allowed[kind]
            ):
                buf = mode_tile[kind]
            elif kind == CLS_EARTH and raw_kind != kind:
                buf = mode_tile[kind]
            atlas = layer_tiles[kind]
            tid = atlas.get(buf)
            if tid is None:
                tid = len(layer_images[kind])
                atlas[buf] = tid
                layer_images[kind].append(_tile_from_bytes(buf))
            layer_ids[kind][i] = tid
            _blit_cell(rebuild_buf, width, cx, cy, buf)
    leftover = Image.frombytes("RGB", (width, height), bytes(leftover_buf))
    overlay = Image.frombytes("RGB", (cw, ch), bytes(overlay_buf))
    rebuild = Image.frombytes("RGB", (width, height), bytes(rebuild_buf))

    OUT_TILESETS.mkdir(parents=True, exist_ok=True)
    OUT_WORLD.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.mkdir(parents=True, exist_ok=True)

    layers_json: dict[str, dict] = {}
    unique_report: dict[str, int] = {}
    for name in VISUAL_LAYERS:
        tiles = layer_images[name]
        n = len(tiles)
        cols = min(32, max(1, n))
        atlas = pack_atlas(tiles, cols)
        png = OUT_TILESETS / f"s2_{name}_tileset.png"
        tres = OUT_TILESETS / f"s2_{name}_tileset.tres"
        atlas.save(png)
        write_tileset_tres(tres, f"res://assets/tilesets/s2_{name}_tileset.png", cols, n)
        unique_report[name] = n - 1
        layers_json[name] = {
            "z": LAYER_Z[name],
            "tileset": f"res://assets/tilesets/s2_{name}_tileset.tres",
            "atlas_tiles": [cols, max(1, math.ceil(n / cols))],
            "empty": 0,
            "rle": rle_encode(layer_ids[name]),
        }

    collision_png = OUT_TILESETS / "s2_collision_tileset.png"
    write_collision_png(collision_png)
    write_collision_tres(OUT_TILESETS / "s2_collision_tileset.tres")

    tiles_doc = {
        "scale": SCALE,
        "cell": CELL,
        "screen": list(SCREEN),
        "size": [width, height],
        "grid": [cw, ch],
        "sky_color": list(SKY_BLUE),
        "layers": layers_json,
    }
    (OUT_WORLD / "s2_world_tiles.json").write_text(
        json.dumps(tiles_doc, separators=(",", ":")), encoding="utf-8"
    )

    collision_doc = {
        "tileset": "res://assets/tilesets/s2_collision_tileset.tres",
        "cell": CELL,
        "grid": [cw, ch],
        "empty": 0,
        "atlas_tiles": [4, 1],
        "collision_source": "collision_tiles",
        "rle": rle_encode(collision_ids),
        "ladder_rle": [],
    }
    (OUT_WORLD / "s2_collision_tiles.json").write_text(
        json.dumps(collision_doc, separators=(",", ":")), encoding="utf-8"
    )

    leftover.save(OUT_REPORT / "slice_leftover.png")
    overlay.save(OUT_REPORT / "slice_overlay.png")
    rebuild_path = OUT_REPORT / "slice_rebuild.png"
    rebuild.save(rebuild_path)
    overview = rebuild.resize((width // 4, height // 4), Image.Resampling.NEAREST)
    overview_path = OUT_REPORT / "slice_rebuild_quarter.png"
    overview.save(overview_path)
    report = {
        "source": SRC.as_posix(),
        "grid": [cw, ch],
        "cells": cw * ch,
        "counts": dict(counts),
        "unique_tiles": unique_report,
        "sky_color": list(SKY_BLUE),
        "solid_cells": sum(1 for v in collision_ids if v == 1),
        "filled_skip_sky": n_skip_fill,
        "filled_earth_holes": n_earth_fill,
        "filled_earth_in_sky": n_earth_sky,
        "filled_sky_rooms": n_sky_rooms,
        "filled_wallpaper_in_earth": n_wp_earth,
        "filled_mosaic_in_earth": n_mosaic_earth,
        "filled_skip_crumbs": n_skip_earth,
        "filled_structure_in_wallpaper": n_st_wp,
        "eroded_earth": n_erode,
        "demoted_uncommon_bg": n_uncommon,
        "demoted_furniture_structure": n_furniture,
        "leftover_cells": sum(1 for v in object_mask if v),
        "allowed_mosaic_tiles": len(allowed[CLS_MOSAIC]),
        "allowed_wallpaper_tiles": len(allowed[CLS_WALLPAPER]),
        "rebuild": rebuild_path.as_posix(),
        "rebuild_quarter": overview_path.as_posix(),
    }
    (OUT_REPORT / "slice_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("slice_world_tiles:")
    for key in (CLS_SKY, CLS_EARTH, CLS_STRUCTURE, CLS_WALLPAPER, CLS_MOSAIC, CLS_SKIP):
        print(f"  {key:10} {counts[key]}")
    print("  unique", unique_report)
    print("  filled skip/sky", n_skip_fill, "earth holes", n_earth_fill)
    print("  earth-in-sky", n_earth_sky, "sky rooms", n_sky_rooms)
    print("  wallpaper-in-earth", n_wp_earth, "mosaic-in-earth", n_mosaic_earth)
    print("  wallpaper-in-mosaic", n_wp_mosaic, "skip crumbs", n_skip_earth, "eroded earth", n_erode)
    print("  room gaps", n_room_gaps, "boxed", n_boxed, "notches", n_notch)
    print("  wallpaper-in-brick", n_wp_in_brick, "structure-in-wallpaper", n_st_wp)
    print("  demoted uncommon", n_uncommon, "furniture structure", n_furniture)
    print("  demoted roof mosaic", n_roof_mosaic, "mosaic islands", n_mosaic_sky)
    print("  secret basement", n_basement, "cells", len(basement))
    print("  allowed mosaic", len(allowed[CLS_MOSAIC]), "wallpaper", len(allowed[CLS_WALLPAPER]))
    print("  wrote", OUT_WORLD / "s2_world_tiles.json")
    print("  leftover", OUT_REPORT / "slice_leftover.png")
    print("  rebuild", rebuild_path)
    print("  rebuild quarter", overview_path)


if __name__ == "__main__":
    main()
