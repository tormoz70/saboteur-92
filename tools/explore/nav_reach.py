#!/usr/bin/env python3
"""Reachability over nav_graph.json and a coverage map.

    python tools/explore/nav_reach.py [visited.json] [out.png]

Without visited.json it draws the graph's own reach from the start node
(green reachable, red not). With the explorer's report it draws what Nina
actually walked (green visited, yellow reachable in the graph but missed,
red unreachable).
"""
from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / ".mcp" / "explore" / "nav_graph.json"
MAP = ROOT / "assets" / "world" / "saboteur2_world2.png"


def reach(data: dict) -> set[int]:
    adj: dict[int, list[int]] = {}
    for a, b, _t, _x in data["edges"]:
        adj.setdefault(a, []).append(b)
    seen = {data["start"]}
    q = deque(seen)
    while q:
        a = q.popleft()
        for b in adj.get(a, []):
            if b not in seen:
                seen.add(b)
                q.append(b)
    return seen


def main() -> None:
    data = json.loads(GRAPH.read_text(encoding="utf-8"))
    nodes = data["nodes"]
    got = reach(data)
    visited: set[int] | None = None
    if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
        rep = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        visited = set(rep.get("visited", []))
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / ".mcp" / "explore" / "coverage.png"
    print(f"nodes {len(nodes)} graph-reachable {len(got)} ({100 * len(got) / len(nodes):.1f}%)")
    if visited is not None:
        print(f"visited {len(visited)} ({100 * len(visited) / max(len(got), 1):.1f}% of reachable)")
    img = Image.open(MAP).convert("RGB").point(lambda v: v // 3)
    d = ImageDraw.Draw(img)
    for i, (x, f, _crouch, _seg) in enumerate(nodes):
        if visited is not None:
            c = (0, 255, 0) if i in visited else (255, 220, 0) if i in got else (255, 0, 0)
        else:
            c = (0, 255, 0) if i in got else (255, 0, 0)
        d.rectangle([x - 6, f - 10, x + 6, f], fill=c)
    img = img.resize((img.width // 4, img.height // 4), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(out)


if __name__ == "__main__":
    main()
