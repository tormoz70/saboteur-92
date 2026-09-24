"""Fan-map generators write under draft/ so they cannot replace the live art.

assets/tilesets is hand-edited. build_world_atlas.py, build_tilesets.py and
slice_world_tiles.py drop atlases, TileSets and their JSON into draft/.
Pass --overwrite to write the checked-in paths instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

OVERWRITE_FLAG = "--overwrite"


def draft_root(root: Path) -> Path:
    return root / "draft"


def prepare_draft(root: Path) -> Path:
    folder = draft_root(root)
    folder.mkdir(parents=True, exist_ok=True)
    ignore = folder / ".gdignore"
    if not ignore.exists():
        ignore.write_text(
            "Generator scratch. Godot must not import these files.\n",
            encoding="utf-8",
        )
    return folder


def writing_live(argv: list[str] | None = None) -> bool:
    args = sys.argv if argv is None else argv
    return OVERWRITE_FLAG in args
