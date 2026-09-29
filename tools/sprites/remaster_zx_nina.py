#!/usr/bin/env python3
"""Remaster the original ZX Nina frames in the style of the modern cast.

The Spectrum sprites are 1-bit silhouettes in 48x56 cells. Their poses are
the animation, so the silhouette is kept and only the rendering changes:

- Scale2x lifts every frame to the 96x112 cell used by the guard sheet.
- Volume comes from the silhouette itself: a blurred mask gives a normal
  and a key light from the front-top cel-shades it in three flat tones,
  with cast shadows under the head and sash. The far leg of a stride is
  a tone darker.
- The contour is rounded; small inner gaps close into 1 px creases, the
  edge gets a 1 px dark outline.
- The tiny Spectrum head is replaced by a drawn masked head (front, side
  or back). Per-frame hints place it and mark the headband tails, the
  sash, the bare fists and the boots.

The Spectrum has fewer frames than the scene plays. The missing ones are
built from the real poses: distance-field blends for small moves, a
clipped arm for the punch wind-up, 45 degree turns of one tuck for the
somersault and roll, and a fall for death. Shading runs after that, so
the light stays world-fixed on turned frames.

    python tools/sprites/remaster_zx_nina.py             # sheets + scenes
    python tools/sprites/remaster_zx_nina.py --preview   # preview only
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SPRITES = ROOT / "assets" / "sprites"
MAIN_SRC = SPRITES / "saboteur93_player.png"
MOVES_SRC = SPRITES / "saboteur93_player_moves.png"
PREVIEW = SPRITES / "_source" / "nina_zx_remaster_preview.png"

FW, FH = 48, 56
SCALE = 2
CELL_W, CELL_H = FW * SCALE, FH * SCALE

# Sheet order; the counts match the timings in player.gd and the tests.
MAIN = [
    ("idle", 4),
    ("run", 4),
    ("punch", 3),
    ("kick", 4),
    ("jump", 2),
    ("jump_kick", 4),
    ("climb", 6),
    ("crouch", 2),
    ("death", 3),
]
MOVES = [
    ("crouch_punch", 3),
    ("somersault", 8),
    ("roll", 8),
]
SPEEDS = {
    "idle": (True, 4.0),
    "run": (True, round(4 / 0.6, 2)),
    "punch": (False, round(3 / 0.32, 2)),
    "kick": (False, round(4 / 0.42, 2)),
    "jump": (False, 8.0),
    "jump_kick": (False, round(4 / 0.42, 2)),
    "climb": (True, 8.0),
    "crouch": (True, 3.0),
    "death": (False, 6.0),
    "crouch_punch": (False, round(3 / 0.32, 2)),
    "somersault": (True, 12.0),
    "roll": (True, 14.0),
}

OUTLINE = (8, 9, 18)
CREASE = (16, 18, 34)
SUIT = [(16, 18, 34), (30, 34, 60), (48, 54, 90), (80, 90, 134)]
SKIN = [(168, 108, 78), (218, 160, 120), (240, 196, 156)]
RED = [(110, 20, 32), (178, 34, 46), (230, 74, 72)]
BOOT = [(12, 14, 26), (28, 32, 52), (48, 56, 84)]

SUIT_L, HEAD_L, TAIL_L, SASH_L, BOOT_L, FIST_L, FAR_SUIT_L, FAR_BOOT_L = range(1, 9)
# Labels from FIXED on are hand-drawn head pixels with their own colour.
FIXED = 20

# Direction to the key light in y-down cell space: front and above.
KEY = np.array([0.6, -0.8])

# The Spectrum head is 7x6 pixels; these replace it at the guard's head
# size. One character is one pixel of the 2x cell. Key light is top-right.
HEAD_INK = {
    "o": OUTLINE,
    "1": SUIT[1],
    "2": SUIT[2],
    "3": SUIT[3],
    "4": (112, 124, 170),
    "r": RED[0],
    "R": RED[1],
    "P": RED[2],
    "s": SKIN[0],
    "S": SKIN[1],
    "L": SKIN[2],
    "W": (240, 236, 228),
    "E": (16, 14, 30),
}
HEADS = {
    "front": [
        ".......12233......",
        ".....1122333344...",
        "....112223333444..",
        "...11222233333444.",
        "...11222223333344.",
        "..rrRRRRRRRRRRPPR.",
        "..rrRRRRRRRRRRRRr.",
        "..112sSSSSSSSSL32.",
        "..11sWEsSSSSWELS2.",
        "..11sWEsSSSSWELS2.",
        "..112ssSSSSSSSS32.",
        "..11122222223333..",
        "...1112222223333..",
        "...1112222222332..",
        "....11122222332...",
        ".....111222233....",
        "......1112223.....",
        "......1112223.....",
        ".....111122233....",
        ".....111122233....",
    ],
    "side": [
        "........122333....",
        "......1122333344..",
        ".....112223333444.",
        "....1122223333344.",
        "....1122222333334.",
        ".rRr1rRRRRRRRRRPP.",
        "rRrRrrRRRRRRRRRRRr",
        ".rRr.1122223sSSSL.",
        "..Rr.1122222sSWES.",
        "..rR.1122222sSWES.",
        "...r.1122222ssSSs.",
        "...R.111222223333.",
        "......11122223333.",
        "......1112222333..",
        ".......111222333..",
        ".......11122233...",
        "........1112223...",
        "........1112223...",
        ".......111122233..",
        ".......111122233..",
    ],
    "back": [
        ".......12233......",
        ".....1122233334...",
        "....112222333344..",
        "...11222223333344.",
        "...11222222333334.",
        "..rrRRRRrrRRRRPPR.",
        "..rrRRRrRRrRRRRRr.",
        "..1112222rR223333.",
        "..111222rRRr23333.",
        "..111222rR.r22333.",
        "..11122r2R.r22333.",
        "..11122r1R..r2333.",
        "...1112r1R..r333..",
        "...1112221..2332..",
        "....1112222.332...",
        ".....111222233....",
        "......1112223.....",
        "......1112223.....",
        ".....111122233....",
        ".....111122233....",
    ],
}
HEAD_CHARS = sorted(HEAD_INK)
HEAD_COLORS = {FIXED + i: HEAD_INK[c] for i, c in enumerate(HEAD_CHARS)}

# Per-frame hints in ZX pixels, boxes are (x0, y0, x1, y1) inclusive.
# head: Spectrum head box. view: front, side or back head drawing.
# tails: headband strands. sash: (top row, x0, x1), two rows tall.
# fists: boxes painted as bare hands. boots: sole rows, 0 in the air.
# smooth: contour rounding radius at 2x, 1 unless the frame is noisy.
# far: boxes of the limb on the far side, drawn a tone darker.
_RUN = {
    "head": (25, 12, 31, 17), "view": "side", "tails": (16, 15, 24, 22),
    "sash": (29, 21, 31), "fists": [(31, 21, 32, 22), (32, 24, 33, 25)], "boots": 3,
}
# The rear leg of each stride, one tone darker so the legs do not merge.
_RUN_FAR = {
    2: [(22, 40, 25, 43), (17, 44, 23, 51)],
    3: [(18, 40, 27, 45), (17, 46, 23, 55)],
    4: [(11, 40, 26, 55)],
    5: [(8, 40, 25, 55)],
}
_CROUCH = {"head": (16, 25, 22, 30), "sash": (40, 13, 23), "boots": 2}
_KICK = {"head": (16, 9, 22, 14), "sash": (32, 17, 25), "fists": [(24, 13, 25, 15), (28, 12, 30, 14)]}
MAIN_HINTS: dict[int, dict] = {
    0: {"head": (19, 9, 25, 14), "sash": (27, 16, 26), "fists": [(28, 15, 30, 18), (14, 20, 16, 23)], "boots": 3},
    1: {"head": (19, 10, 25, 15), "sash": (28, 16, 26), "fists": [(28, 16, 30, 19), (14, 21, 16, 24)], "boots": 3},
    2: {**_RUN, "far": _RUN_FAR[2]},
    3: {**_RUN, "far": _RUN_FAR[3]},
    4: {**_RUN, "far": _RUN_FAR[4]},
    5: {**_RUN, "far": _RUN_FAR[5]},
    6: {"head": (16, 9, 22, 14), "sash": (27, 16, 26), "fists": [(40, 17, 42, 19)], "boots": 3},
    7: {**_KICK, "boots": 2},
    8: {**_KICK, "boots": 0},
    9: {"head": (13, 5, 20, 10), "view": "side", "tails": (7, 7, 12, 13), "fists": [(33, 6, 35, 8)], "boots": 0},
    10: {"head": (20, 9, 26, 14), "view": "back", "sash": (26, 19, 28), "fists": [(24, 0, 27, 2)], "boots": 3},
    11: {"head": (21, 9, 27, 14), "view": "back", "sash": (26, 19, 29), "fists": [(20, 0, 23, 2)], "boots": 3},
    12: _CROUCH,
    13: {**_CROUCH, "head": (16, 26, 22, 31), "sash": (41, 13, 23)},
}
MOVES_HINTS: dict[int, dict] = {
    0: {**_CROUCH, "fists": [(40, 33, 43, 35)]},
    1: {"head": (14, 9, 21, 15), "view": "side", "boots": 0, "smooth": 2},
}
MOVES_HINTS.update({i: {"boots": 0} for i in range(2, 9)})


def _cells(path: Path) -> list[np.ndarray]:
    img = np.array(Image.open(path).convert("RGBA"))
    count = img.shape[1] // FW
    return [img[:, i * FW : (i + 1) * FW, 3] > 0 for i in range(count)]


def _shift(a: np.ndarray, dy: int, dx: int, fill=False) -> np.ndarray:
    out = np.full_like(a, fill)
    h, w = a.shape
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = a[ys, xs]
    return out


def _scale2x(m: np.ndarray) -> np.ndarray:
    a = _shift(m, 1, 0)
    b = _shift(m, 0, -1)
    c = _shift(m, 0, 1)
    d = _shift(m, -1, 0)
    e0 = np.where((c == a) & (c != d) & (a != b), a, m)
    e1 = np.where((a == b) & (a != c) & (b != d), b, m)
    e2 = np.where((d == c) & (d != b) & (c != a), c, m)
    e3 = np.where((b == d) & (b != a) & (d != c), d, m)
    out = np.zeros((m.shape[0] * 2, m.shape[1] * 2), dtype=bool)
    out[0::2, 0::2] = e0
    out[0::2, 1::2] = e1
    out[1::2, 0::2] = e2
    out[1::2, 1::2] = e3
    return out


def _outside(m: np.ndarray) -> np.ndarray:
    """Transparent pixels connected to the cell border."""
    out = np.zeros_like(m)
    out[0, :] = ~m[0, :]
    out[-1, :] = ~m[-1, :]
    out[:, 0] = ~m[:, 0]
    out[:, -1] = ~m[:, -1]
    while True:
        grown = out | _shift(out, 1, 0) | _shift(out, -1, 0) | _shift(out, 0, 1) | _shift(out, 0, -1)
        grown &= ~m
        if np.array_equal(grown, out):
            return out
        out = grown


def _blur(a: np.ndarray, r: int) -> np.ndarray:
    out = a.astype(np.float64)
    for axis in (0, 1):
        acc = np.zeros_like(out)
        for k in range(-r, r + 1):
            acc += np.roll(out, k, axis=axis)
        out = acc / (2 * r + 1)
    return out


def _depth(m: np.ndarray, cap: int = 6) -> np.ndarray:
    depth = np.zeros(m.shape, dtype=np.int32)
    cur = m.copy()
    for step in range(1, cap + 1):
        depth[cur] = step
        cur = cur & _shift(cur, 1, 0) & _shift(cur, -1, 0) & _shift(cur, 0, 1) & _shift(cur, 0, -1)
    return depth


def _box(m: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    out = np.zeros_like(m)
    out[max(0, y0) : y1 + 1, max(0, x0) : x1 + 1] = True
    return out


def _labels(m: np.ndarray, hint: dict) -> np.ndarray:
    lab = np.where(m, SUIT_L, 0).astype(np.int32)
    holes = ~m & ~_outside(m)
    head = hint.get("head")
    if head:
        box = _box(m, head)
        lab[box & (m | holes)] = HEAD_L
    for fist in hint.get("fists", []):
        lab[_box(m, fist) & m] = FIST_L
    tails = hint.get("tails")
    if tails:
        lab[_box(m, tails) & m] = TAIL_L
    sash = hint.get("sash")
    if sash:
        y, x0, x1 = sash
        belt = _box(m, (x0, y, x1, y + 1)) & (lab == SUIT_L)
        lab[belt] = SASH_L
    boots = hint.get("boots", 0)
    if boots:
        rows = np.flatnonzero(m.any(axis=1))
        bottom = int(rows[-1])
        for y in range(bottom - boots + 1, bottom + 1):
            lab[y][lab[y] == SUIT_L] = BOOT_L
    for far in hint.get("far", []):
        box = _box(m, far)
        lab[box & (lab == SUIT_L)] = FAR_SUIT_L
        lab[box & (lab == BOOT_L)] = FAR_BOOT_L
    return lab


def _upscale_labels(lab: np.ndarray, big: np.ndarray) -> np.ndarray:
    up = np.repeat(np.repeat(lab, SCALE, axis=0), SCALE, axis=1)
    up[~big] = 0
    missing = big & (up == 0)
    for _ in range(4):
        if not missing.any():
            break
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            src = _shift(up, dy, dx, fill=0)
            take = missing & (src > 0)
            up[take] = src[take]
            missing &= ~take
    up[missing] = SUIT_L
    return up


def _pose(small: np.ndarray, hint: dict) -> np.ndarray:
    """Label map at the 2x cell: 0 is empty, the rest are the *_L parts."""
    lab_small = _labels(small, hint)
    big = _scale2x(lab_small > 0)
    lab = _upscale_labels(lab_small, big)
    # Round off the Scale2x stair steps: a pixel stays if most of its 3x3 does.
    smooth = _blur(lab > 0, hint.get("smooth", 1)) > 0.5
    lab = _fill_labels(lab, smooth)
    if hint.get("head"):
        lab = _stamp_head(lab, hint["head"], hint.get("view", "front"))
    return lab


def _stamp_head(lab: np.ndarray, box: tuple[int, int, int, int], view: str) -> np.ndarray:
    rows = HEADS[view]
    h, w = len(rows), len(rows[0])
    x0, y0, x1, y1 = (v * SCALE for v in box)
    x1 += SCALE - 1
    y1 += SCALE - 1
    out = lab.copy()
    region = out[y0 : y1 + 1, x0 : x1 + 1]
    region[region == HEAD_L] = 0
    bottom = y1 + 3
    left = x1 + 3 - w if view == "side" else int(round((x0 + x1) / 2.0 - (w - 1) / 2.0))
    top = bottom - h + 1
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            y, x = top + dy, left + dx
            if ch != "." and 0 <= y < CELL_H and 0 <= x < CELL_W:
                out[y, x] = FIXED + HEAD_CHARS.index(ch)
    return out


def _components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """4-connected pixel groups."""
    seen = np.zeros_like(mask)
    parts = []
    h, w = mask.shape
    for sy, sx in zip(*np.nonzero(mask)):
        if seen[sy, sx]:
            continue
        stack = [(sy, sx)]
        seen[sy, sx] = True
        part = []
        while stack:
            y, x = stack.pop()
            part.append((y, x))
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        parts.append(part)
    return parts


def _creases(lab: np.ndarray, max_px: int = 14) -> tuple[np.ndarray, np.ndarray]:
    """Close the small gaps the Spectrum used as inner lines. Each gap keeps
    a 1 px crease along its top-left edge; wide gaps stay open."""
    body = lab > 0
    holes = ~body & ~_outside(body)
    closed = body.copy()
    crease = np.zeros_like(body)
    for part in _components(holes):
        if len(part) > max_px:
            continue
        ys, xs = (np.array(v) for v in zip(*part))
        closed[ys, xs] = True
        member = np.zeros_like(body)
        member[ys, xs] = True
        edge = member & ~(_shift(member, 1, 0) & _shift(member, 0, 1))
        crease |= edge
    return _fill_labels(lab, closed), crease


def _sdf(mask: np.ndarray, cap: int = 48) -> np.ndarray:
    """Signed step distance to the edge, positive inside."""
    inside = np.zeros(mask.shape, dtype=np.int32)
    outside = np.zeros(mask.shape, dtype=np.int32)
    cur_in = mask.copy()
    cur_out = mask.copy()
    for step in range(1, cap + 1):
        inside[cur_in] = step
        dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
        if step % 2 == 0:
            dirs += ((1, 1), (1, -1), (-1, 1), (-1, -1))
        grown = cur_out.copy()
        shrunk = cur_in.copy()
        for dy, dx in dirs:
            grown |= _shift(cur_out, dy, dx)
            shrunk &= _shift(cur_in, dy, dx)
        outside[grown & ~cur_out] = step
        cur_in = shrunk
        cur_out = grown
    outside[~cur_out] = cap + 1
    return np.where(mask, inside, -outside).astype(np.float64)


def _fill_labels(lab: np.ndarray, mask: np.ndarray) -> np.ndarray:
    lab = np.where(mask, lab, 0)
    missing = mask & (lab == 0)
    for _ in range(24):
        if not missing.any():
            break
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            src = _shift(lab, dy, dx, fill=0)
            take = missing & (src > 0)
            lab[take] = src[take]
            missing &= ~take
    lab[missing] = SUIT_L
    return lab


def _despeckle(mask: np.ndarray, min_px: int = 16, share: float = 0.1) -> np.ndarray:
    """Drop islands a blend leaves behind, e.g. a hand between two grips.
    An island survives if it has min_px pixels and share of the largest."""
    seen = np.zeros_like(mask)
    parts = []
    h, w = mask.shape
    for sy, sx in zip(*np.nonzero(mask)):
        if seen[sy, sx]:
            continue
        stack = [(sy, sx)]
        seen[sy, sx] = True
        part = []
        while stack:
            y, x = stack.pop()
            part.append((y, x))
            for ny in (y - 1, y, y + 1):
                for nx in (x - 1, x, x + 1):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        parts.append(part)
    keep = np.zeros_like(mask)
    if not parts:
        return keep
    floor = max(min_px, share * max(len(part) for part in parts))
    for part in parts:
        if len(part) >= floor:
            ys, xs = zip(*part)
            keep[list(ys), list(xs)] = True
    return keep


def _mix(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    """In-between of two poses: blend their distance fields."""
    mask = _despeckle((1.0 - t) * _sdf(a > 0) + t * _sdf(b > 0) > 0.0)
    near, far = (a, b) if t < 0.5 else (b, a)
    lab = np.where(near > 0, near, far)
    return _fill_labels(lab, mask)


def _clip(lab: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    """Erase a ZX-pixel box, e.g. the far half of an extended arm."""
    out = lab.copy()
    x0, y0, x1, y1 = box
    out[y0 * SCALE : (y1 + 1) * SCALE, x0 * SCALE : (x1 + 1) * SCALE] = 0
    return out


def _bbox(lab: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(lab)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _turn(lab: np.ndarray, degrees: float, center: tuple[float, float] | None = None, floor: bool = False) -> np.ndarray:
    """Rotate clockwise about the pose centre, then re-place it.

    The turn runs at 4x: the outline is rotated smooth and thresholded back,
    the parts are rotated nearest, which keeps edges clean without new colours.
    """
    x0, y0, x1, y1 = _bbox(lab)
    crop = lab[y0 : y1 + 1, x0 : x1 + 1].astype(np.uint8)
    up = 4
    big = np.repeat(np.repeat(crop, up, axis=0), up, axis=1)
    shape = Image.fromarray(np.where(big > 0, 255, 0).astype(np.uint8), "L")
    shape = np.array(shape.rotate(-degrees, resample=Image.Resampling.BILINEAR, expand=True))
    parts = np.array(Image.fromarray(big, "L").rotate(-degrees, resample=Image.Resampling.NEAREST, expand=True))
    h4 = shape.shape[0] // up * up
    w4 = shape.shape[1] // up * up
    cover = shape[:h4, :w4].reshape(h4 // up, up, w4 // up, up).mean(axis=(1, 3)) > 127
    picked = parts[up // 2 : h4 : up, up // 2 : w4 : up][: cover.shape[0], : cover.shape[1]]
    spun = _fill_labels(picked.astype(np.int32), _despeckle(cover, 6, 0.0))
    ys, xs = np.nonzero(spun)
    spun = spun[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = spun.shape
    cx, cy = center if center else ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    left = int(round(cx - (w - 1) / 2.0))
    top = CELL_H - h if floor else int(round(cy - (h - 1) / 2.0))
    left = max(0, min(CELL_W - w, left))
    top = max(0, min(CELL_H - h, top))
    out = np.zeros((CELL_H, CELL_W), dtype=np.int32)
    out[top : top + h, left : left + w] = spun[: CELL_H - top, : CELL_W - left]
    return out


def _render(lab: np.ndarray) -> np.ndarray:
    lab, crease = _creases(lab)
    big = lab > 0
    # Cel shading, not a gradient: flat base, a shadow band on the edges
    # facing away from the light, a 1 px highlight on the lit edges.
    soft = _blur(_blur(big, 2), 2)
    gy, gx = np.gradient(soft)
    mag = np.hypot(gx, gy) + 1e-9
    toward = (-gx * KEY[0] - gy * KEY[1]) / (mag * np.hypot(KEY[0], KEY[1]))
    depth = _depth(big)
    tone = np.ones(big.shape, dtype=np.int32)
    tone[(depth <= 3) & (toward < -0.2)] = 0
    tone[(depth <= 2) & (toward > 0.35)] = 2
    # Cast shadows under the head and the sash, and along each crease.
    head = lab >= FIXED
    under = (_shift(head, 1, 0) | _shift(head, 2, 0)) & ~head
    sash = lab == SASH_L
    under |= _shift(sash, 1, 0) & ~sash
    under |= _shift(crease, 1, 0) | _shift(crease, 0, -1)
    tone[under & (tone > 0)] = 0
    deep = (depth <= 1) & (toward < -0.6)

    rgba = np.zeros(big.shape + (4,), dtype=np.uint8)

    def paint(mask: np.ndarray, ramp: list[tuple[int, int, int]]) -> None:
        # Ramps run dark to light; SUIT has an extra deepest step.
        off = len(ramp) - 3
        for i in range(3):
            sel = mask & (tone == i)
            rgba[sel, :3] = ramp[i + off]
            rgba[sel, 3] = 255
        if off:
            rgba[mask & deep, :3] = ramp[0]

    paint((lab == SUIT_L) | (lab == HEAD_L), SUIT)
    paint(lab == BOOT_L, BOOT)
    far = (lab == FAR_SUIT_L) | (lab == FAR_BOOT_L)
    paint(lab == FAR_SUIT_L, [SUIT[0], SUIT[0], SUIT[1], SUIT[2]])
    paint(lab == FAR_BOOT_L, [BOOT[0], BOOT[0], BOOT[1]])
    near = big & ~far
    behind = far & (_shift(near, 1, 0) | _shift(near, -1, 0) | _shift(near, 0, 1) | _shift(near, 0, -1))
    rgba[behind, :3] = CREASE
    paint((lab == SASH_L) | (lab == TAIL_L), RED)
    paint(lab == FIST_L, SKIN)
    for label, color in HEAD_COLORS.items():
        rgba[lab == label, :3] = color
        rgba[lab == label, 3] = 255
    rgba[crease & (lab < FIXED), :3] = CREASE

    edge = ~big & (_shift(big, 1, 0) | _shift(big, -1, 0) | _shift(big, 0, 1) | _shift(big, 0, -1))
    rgba[edge, :3] = OUTLINE
    rgba[edge, 3] = 255
    return rgba


def _poses() -> list[np.ndarray]:
    """ZX poses 0-13 from the main sheet, 14-22 from the moves sheet."""
    out = []
    for cells, hints in ((_cells(MAIN_SRC), MAIN_HINTS), (_cells(MOVES_SRC), MOVES_HINTS)):
        for i, small in enumerate(cells):
            out.append(_pose(small, hints.get(i, {})))
    return out


def _center(lab: np.ndarray) -> tuple[float, float]:
    x0, y0, x1, y1 = _bbox(lab)
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def _spin(tuck: np.ndarray, floor: bool) -> list[np.ndarray]:
    """Eight clockwise 45 degree steps of one tuck. The Spectrum's four
    quarters are the same ball turned, but only the first has a known head."""
    center = _center(tuck)
    return [tuck] + [_turn(tuck, 45.0 * k, center, floor) for k in range(1, 8)]


PUNCH_REACH = (33, 15, 47, 21)
CROUCH_PUNCH_REACH = (33, 31, 47, 37)


def _animations(p: list[np.ndarray]) -> dict[str, list[np.ndarray]]:
    return {
        "idle": [p[0], _mix(p[0], p[1], 0.5), p[1], _mix(p[1], p[0], 0.5)],
        # Only the drawn strides: a blended stride melts the legs together.
        "run": [p[2], p[3], p[4], p[5]],
        "punch": [_clip(p[6], PUNCH_REACH), p[6], _clip(p[6], PUNCH_REACH)],
        # The jump tuck doubles as the kick chamber, as on the Spectrum.
        "kick": [p[8], p[7], p[7], p[8]],
        "jump": [p[13], p[8]],
        "jump_kick": [p[8], p[9], p[9], p[9]],
        # The ladder steps through six frames per two rungs; the Spectrum
        # swaps grips once per rung, so each grip holds for three.
        "climb": [p[10], p[10], p[10], p[11], p[11], p[11]],
        "crouch": [p[12], p[13]],
        "death": [
            _mix(p[0], p[12], 0.5),
            _turn(p[12], -40.0, _center(p[12]), floor=True),
            _turn(p[0], -90.0, _center(p[0]), floor=True),
        ],
        "crouch_punch": [_clip(p[14], CROUCH_PUNCH_REACH), p[14], _clip(p[14], CROUCH_PUNCH_REACH)],
        "somersault": _spin(p[15], floor=False),
        "roll": _spin(_turn(p[15], 0.0, floor=True), floor=True),
    }


def _strip(frames: list[np.ndarray]) -> Image.Image:
    sheet = Image.new("RGBA", (CELL_W * len(frames), CELL_H), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        sheet.alpha_composite(Image.fromarray(frame, "RGBA"), (i * CELL_W, 0))
    return sheet


def _preview(anims: dict[str, list[np.ndarray]], zoom: int = 2) -> Image.Image:
    per_row = max(len(frames) for frames in anims.values())
    rows = list(anims.values())
    guard = SPRITES / "saboteur26_guard.png"
    canvas = Image.new("RGBA", ((per_row + 1) * CELL_W, len(rows) * CELL_H), (24, 34, 52, 255))
    for r, frames in enumerate(rows):
        for c, frame in enumerate(frames):
            canvas.alpha_composite(Image.fromarray(frame, "RGBA"), (c * CELL_W, r * CELL_H))
    if guard.exists():
        g = Image.open(guard).convert("RGBA").crop((2 * CELL_W, 0, 3 * CELL_W, CELL_H))
        canvas.alpha_composite(g, (per_row * CELL_W, 0))
    return canvas.resize((canvas.width * zoom, canvas.height * zoom), Image.Resampling.NEAREST)


def _scene_block() -> tuple[str, int]:
    order = [
        "idle", "jump", "jump_kick", "kick", "run", "punch",
        "climb", "crouch", "crouch_punch", "somersault", "roll", "death",
    ]
    sheets: dict[str, tuple[int, int, int]] = {}
    for sheet_id, spec in ((2, MAIN), (3, MOVES)):
        x = 0
        for name, count in spec:
            sheets[name] = (sheet_id, x, count)
            x += CELL_W * count
    atlases: list[str] = []
    anims: list[str] = []
    for name in order:
        sheet_id, origin, count = sheets[name]
        ids = []
        for i in range(count):
            tex_id = f"AtlasTexture_{name}{i}"
            ids.append(tex_id)
            atlases.append(
                f'[sub_resource type="AtlasTexture" id="{tex_id}"]\n'
                f'atlas = ExtResource("{sheet_id}")\n'
                f"region = Rect2({origin + i * CELL_W}, 0, {CELL_W}, {CELL_H})\n"
            )
        loop, speed = SPEEDS[name]
        frames = ", ".join(
            f'{{"duration": 1.0, "texture": SubResource("{tex_id}")}}' for tex_id in ids
        )
        anims.append(
            "{\n"
            f'"frames": [{frames}],\n'
            f'"loop": {"true" if loop else "false"},\n'
            f'"name": &"{name}",\n'
            f'"speed": {speed}\n'
            "}"
        )
    body = "\n".join(atlases)
    body += '\n[sub_resource type="SpriteFrames" id="SpriteFrames_player"]\n'
    body += "animations = [" + ", ".join(anims) + "]\n"
    return body, len(atlases)


def _patch_player() -> None:
    path = ROOT / "scenes" / "player" / "player.tscn"
    text = path.read_text(encoding="utf-8")
    head, rest = text.split('[sub_resource type="AtlasTexture"', 1)
    node = '[node name="Player"' + rest.split('[node name="Player"', 1)[1]
    node = re.sub(
        r'(\[node name="AnimatedSprite2D"[^\[]*?)position = Vector2\([^)]*\)\nscale = Vector2\([^)]*\)',
        r"\1position = Vector2(24, 28)\nscale = Vector2(0.5, 0.5)",
        node,
        count=1,
    )
    block, atlas_count = _scene_block()
    first, _, tail = head.partition("\n")
    first = re.sub(r"load_steps=\d+", f"load_steps={3 + 3 + atlas_count + 1}", first, count=1)
    path.write_text(first + "\n" + tail + block + "\n" + node, encoding="utf-8", newline="\n")
    print(f"player.tscn atlases={atlas_count}")


def _patch_title(idle: np.ndarray) -> None:
    ys, xs = np.nonzero(idle[:, :, 3])
    x0, y0 = max(0, int(xs.min()) - 1), max(0, int(ys.min()) - 1)
    x1, y1 = min(CELL_W, int(xs.max()) + 2), min(CELL_H, int(ys.max()) + 2)
    region = f"Rect2({x0}, {y0}, {x1 - x0}, {y1 - y0})"
    path = ROOT / "scenes" / "main.tscn"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"region = Rect2\([^)]+\)", f"region = {region}", text, count=1)
    path.write_text(text, encoding="utf-8", newline="\n")
    print("title", region)


def main() -> None:
    poses = _poses()
    anims = {name: [_render(lab) for lab in labs] for name, labs in _animations(poses).items()}
    for name, count in MAIN + MOVES:
        if len(anims[name]) != count:
            raise SystemExit(f"{name}: {len(anims[name])} frames, sheet expects {count}")
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    _preview(anims).save(PREVIEW)
    if "--preview" in sys.argv:
        print(f"preview -> {PREVIEW.relative_to(ROOT).as_posix()}")
        return
    _strip([f for name, _ in MAIN for f in anims[name]]).save(SPRITES / "saboteur26_player.png")
    _strip([f for name, _ in MOVES for f in anims[name]]).save(SPRITES / "saboteur26_player_moves.png")
    _patch_player()
    _patch_title(anims["idle"][0])


if __name__ == "__main__":
    main()
