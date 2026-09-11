#!/usr/bin/env python3
"""Retired colour-fingerprint floor tests — collision comes from the marker table."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from opcode_catalog import MARKERS, fill_collision


def test_fill_collision_from_geometry() -> None:
    assert fill_collision(8, 1) == "floor"
    assert fill_collision(1, 4) == "solid"
    assert MARKERS[0o00].collision == "floor"
    assert MARKERS[0o06].collision == "solid"
    assert MARKERS[0o11].collision == "solid"


def main() -> None:
    test_fill_collision_from_geometry()
    print("test_floor_classify: OK")


if __name__ == "__main__":
    main()
