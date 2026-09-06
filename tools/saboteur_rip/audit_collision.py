#!/usr/bin/env python3
"""Сверяет s2_collision.json с картинкой мира и ищет дыры в проходимости.

Работает по отгружаемым файлам, а не по исходному рипу, поэтому проверяет ровно
то, что попадает в игру. Нужен, чтобы после правок в build_s2_world.py убедиться,
что грунт стал непроницаемым и при этом не замуровало лестницы.

    python tools/saboteur_rip/audit_collision.py
    python tools/saboteur_rip/audit_collision.py --screen 10 13
    python tools/saboteur_rip/audit_collision.py --screen 10 13 --png /tmp/screen.png
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, deque
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "assets" / "world" / "saboteur2_world.png"
TILES = ROOT / "assets" / "world" / "s2_world_tiles.json"
ATLAS = ROOT / "assets" / "tilesets" / "s2_world_tileset.png"
DATA = ROOT / "assets" / "world" / "s2_collision.json"
CELL = 8
SCREEN_W, SCREEN_H = 256, 192


def rle_decode(runs: list[int]) -> list[int]:
    out: list[int] = []
    for i in range(0, len(runs), 2):
        out.extend([runs[i]] * runs[i + 1])
    return out


def load_world_image() -> Image.Image:
    """Prefer the mosaic PNG; otherwise rebuild it from the visual tileset."""
    if WORLD.exists():
        return Image.open(WORLD).convert("RGB")
    if not TILES.exists() or not ATLAS.exists():
        raise SystemExit("need saboteur2_world.png or s2_world_tiles.json + s2_world_tileset.png")
    spec = json.loads(TILES.read_text())
    world = spec["world"]
    ids = rle_decode(world["rle"])
    cw, ch = spec["grid"]
    atlas_cols = world["atlas_tiles"][0]
    atlas = Image.open(ATLAS).convert("RGB")
    out = Image.new("RGB", (cw * CELL, ch * CELL))
    for i, tid in enumerate(ids):
        ax, ay = (tid % atlas_cols) * CELL, (tid // atlas_cols) * CELL
        cx, cy = i % cw, i // cw
        out.paste(atlas.crop((ax, ay, ax + CELL, ay + CELL)), (cx * CELL, cy * CELL))
    return out


def ink(r: int, g: int, b: int) -> str:
    """Та же классификация краски ZX, что в build_s2_world.py::_col."""
    if r == 0 and g == 0 and b == 0:
        return "k"
    if r == 0 and g == 0 and b >= 200:
        return "b"
    if r == 0 and g >= 200 and b < 40:
        return "g"
    if r == 0 and g >= 200 and b >= 200:
        return "c"
    if r >= 200 and g < 40 and b < 40:
        return "r"
    if r >= 200 and g >= 200 and b < 40:
        return "y"
    if r >= 200 and g >= 200 and b >= 200:
        return "w"
    if r >= 200 and g < 40 and b >= 200:
        return "m"
    return "o"


def is_speckled_earth(c: Counter) -> bool:
    return c["k"] >= 48 and 1 <= c["b"] <= 8 and c["g"] < 8 and c["r"] < 8 and c["c"] < 8


def is_red_brick(c: Counter) -> bool:
    return c["r"] >= 10 and c["k"] >= 4


class World:
    def __init__(self) -> None:
        self.im = load_world_image()
        self.px = self.im.load()
        self.w, self.h = self.im.size
        self.cw, self.ch = self.w // CELL, self.h // CELL
        self.data = json.loads(DATA.read_text())
        self.solid = self._grid(self.data["solids"])
        self.ladder = self._grid(self.data["ladders"])
        self.counts = [
            [self._cell_counts(cx, cy) for cx in range(self.cw)] for cy in range(self.ch)
        ]
        self.biomes = self._biomes()
        self.sx_n = self.w // SCREEN_W

    def _grid(self, rects: list) -> list[list[int]]:
        g = [[0] * self.cw for _ in range(self.ch)]
        for x, y, rw, rh in rects:
            for cy in range(max(0, y // CELL), min(self.ch, (y + rh) // CELL)):
                for cx in range(max(0, x // CELL), min(self.cw, (x + rw) // CELL)):
                    g[cy][cx] = 1
        return g

    def _cell_counts(self, cx: int, cy: int) -> Counter:
        c: Counter = Counter()
        x0, y0 = cx * CELL, cy * CELL
        for y in range(y0, y0 + CELL):
            for x in range(x0, x0 + CELL):
                c[ink(*self.px[x, y])] += 1
        return c

    def _biomes(self) -> list[str]:
        out = []
        n = SCREEN_W * SCREEN_H
        for sy in range(self.h // SCREEN_H):
            for sx in range(self.w // SCREEN_W):
                sky = grn = 0
                for y in range(sy * SCREEN_H, (sy + 1) * SCREEN_H):
                    for x in range(sx * SCREEN_W, (sx + 1) * SCREEN_W):
                        k = ink(*self.px[x, y])
                        if k == "b":
                            sky += 1
                        elif k == "g":
                            grn += 1
                out.append(
                    "sky" if sky / n > 0.55 else "interior" if grn / n > 0.12 else "cave"
                )
        return out

    def biome_at(self, cx: int, cy: int) -> str:
        return self.biomes[((cy * CELL) // SCREEN_H) * self.sx_n + ((cx * CELL) // SCREEN_W)]


def report(world: World) -> None:
    print("=" * 78)
    print("АУДИТ ПРОХОДИМОСТИ: s2_collision.json против визуала мира")
    print("=" * 78)
    print(
        f"сетка {world.cw}x{world.ch} ячеек, биомы {dict(Counter(world.biomes))}"
    )
    print()

    checks = (("грунт (speckled)", is_speckled_earth), ("красный кирпич", is_red_brick))
    worst: Counter = Counter()
    for label, pred in checks:
        total: Counter = Counter()
        holes: Counter = Counter()
        for cy in range(world.ch):
            for cx in range(world.cw):
                if not pred(world.counts[cy][cx]):
                    continue
                b = world.biome_at(cx, cy)
                total[b] += 1
                if not world.solid[cy][cx]:
                    holes[b] += 1
                    if pred is is_speckled_earth:
                        worst[(cx * CELL // SCREEN_W, cy * CELL // SCREEN_H, b)] += 1
        t, hn = sum(total.values()), sum(holes.values())
        print(f"[{label}] всего {t}, БЕЗ коллизии {hn} ({100 * hn / max(t, 1):.1f}%)")
        for b in ("cave", "interior", "sky"):
            if total[b]:
                print(
                    "    %-9s всего %7d, дыр %7d (%.1f%%)"
                    % (b, total[b], holes[b], 100 * holes[b] / total[b])
                )
        print()

    print("-" * 78)
    print("ЭКРАНЫ С НАИБОЛЬШИМ ЧИСЛОМ ПРОВАЛЬНЫХ ЯЧЕЕК ГРУНТА")
    print("-" * 78)
    scale = world.data["scale"]
    for (sx, sy, b), n in worst.most_common(10):
        print(
            f"  экран ({sx:2d},{sy:2d}) биом {b:9s} дыр {n:5d}"
            f"   мир ~({sx * SCREEN_W * scale},{sy * SCREEN_H * scale})"
        )
    print()

    simulate_fix(world)


def components(grid: list[list[int]], cw: int, ch: int) -> list[int]:
    seen = [[0] * cw for _ in range(ch)]
    sizes = []
    for sy in range(ch):
        for sx in range(cw):
            if grid[sy][sx] or seen[sy][sx]:
                continue
            q = deque([(sx, sy)])
            seen[sy][sx] = 1
            n = 0
            while q:
                x, y = q.popleft()
                n += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < cw and 0 <= ny < ch and not grid[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = 1
                        q.append((nx, ny))
            sizes.append(n)
    return sorted(sizes, reverse=True)


def simulate_fix(world: World) -> None:
    """Что даст добавление speckled_earth в ветку interior."""
    fixed = [row[:] for row in world.solid]
    added = 0
    for cy in range(world.ch):
        for cx in range(world.cw):
            if fixed[cy][cx]:
                continue
            if world.biome_at(cx, cy) == "interior" and is_speckled_earth(world.counts[cy][cx]):
                fixed[cy][cx] = 1
                added += 1
    blocked = sum(
        1
        for cy in range(world.ch)
        for cx in range(world.cw)
        if world.ladder[cy][cx] and fixed[cy][cx] and not world.solid[cy][cx]
    )
    print("-" * 78)
    print("ЕСЛИ ДОБАВИТЬ speckled_earth В ВЕТКУ interior")
    print("-" * 78)
    print(f"  станет солидом ячеек            : {added}")
    print(f"  из них попадёт на лестницы      : {blocked}")
    for label, g in (("сейчас", world.solid), ("после ", fixed)):
        s = components(g, world.cw, world.ch)
        tot = sum(s)
        print(
            f"  {label}: свободных {tot}, связных областей {len(s)},"
            f" крупнейшая {s[0]} ({100 * s[0] / tot:.1f}%), областей >1000: "
            f"{sum(1 for n in s if n > 1000)}"
        )
    print()
    print("  Разбиение на несколько крупных областей ожидаемо: непроницаемый грунт")
    print("  разделяет то, что сейчас слито в одну сплошную пустоту. Области стоит")
    print("  просмотреть глазами — часть из них может оказаться отрезанными комнатами.")


def dump_screen(world: World, sx: int, sy: int, out_path: str | None) -> None:
    x0, y0 = sx * SCREEN_W, sy * SCREEN_H
    print(f"ЭКРАН ({sx},{sy}) биом {world.biome_at(x0 // CELL, y0 // CELL)}")
    print("  СЛЕВА вид: ':' грунт  'L' зелёные обои  '#' кирпич  '.' пусто  'b' синее")
    print("  СПРАВА коллизия: '#' солид")
    for cy in range(y0 // CELL, (y0 + SCREEN_H) // CELL):
        look = ""
        coll = ""
        for cx in range(x0 // CELL, (x0 + SCREEN_W) // CELL):
            c = world.counts[cy][cx]
            if is_speckled_earth(c):
                look += ":"
            elif is_red_brick(c):
                look += "#"
            elif c["g"] >= 12:
                look += "L"
            elif c["b"] >= 24:
                look += "b"
            elif c["k"] >= 56:
                look += "."
            else:
                look += "?"
            coll += "#" if world.solid[cy][cx] else "."
        print("  " + look + "   " + coll)

    if not out_path:
        return
    base = world.im.crop((x0, y0, x0 + SCREEN_W, y0 + SCREEN_H)).convert("RGBA")
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for cy in range(y0 // CELL, (y0 + SCREEN_H) // CELL):
        for cx in range(x0 // CELL, (x0 + SCREEN_W) // CELL):
            lx, ly = cx * CELL - x0, cy * CELL - y0
            if world.solid[cy][cx]:
                d.rectangle((lx, ly, lx + CELL - 1, ly + CELL - 1), fill=(60, 255, 60, 70))
            elif is_speckled_earth(world.counts[cy][cx]):
                d.rectangle((lx, ly, lx + CELL - 1, ly + CELL - 1), fill=(255, 30, 30, 150))
    img = Image.alpha_composite(base, ov).resize((SCREEN_W * 4, SCREEN_H * 4), Image.NEAREST)
    img.convert("RGB").save(out_path)
    print(f"  overlay -> {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--screen", nargs=2, type=int, metavar=("SX", "SY"))
    ap.add_argument("--png", help="сохранить наложение коллизии для --screen")
    args = ap.parse_args()

    if not DATA.exists():
        raise SystemExit("нет assets/world/s2_collision.json — сначала запусти build_s2_world.py")
    if not WORLD.exists() and not (TILES.exists() and ATLAS.exists()):
        raise SystemExit("нет мозаики и нет тайлсета — сначала запусти build_s2_world.py")

    world = World()
    if args.screen:
        dump_screen(world, args.screen[0], args.screen[1], args.png)
    else:
        report(world)


if __name__ == "__main__":
    main()
