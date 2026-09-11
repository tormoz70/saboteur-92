#!/usr/bin/env python3
"""Retired colour-fingerprint ladder tests — rungs come from the marker table."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from opcode_catalog import LADDER_START, MARKERS, type_id_ladder


def test_ladder_markers_are_climb_modules() -> None:
    for op in (0o10, 0o16, 0o36, 0o41):
        m = MARKERS[op]
        assert m.collision == "climb", op
        assert m.consume == "ladder"
        assert m.ladder_tile == LADDER_START[op]
        assert type_id_ladder(op).startswith("ladder_")


def main() -> None:
    test_ladder_markers_are_climb_modules()
    print("test_ladder_classify: ok")


if __name__ == "__main__":
    main()
