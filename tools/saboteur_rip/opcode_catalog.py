"""Room-marker catalog from S2CORE.MAC jump table K13426.

Layers (authoring, not physics):
  0 sky, 1 earth, 2 structure, 3 interior, 4 artifacts,
  5 machines, 6 actors, 7 fg

Collision is a property of the marker / fill geometry, never a colour count.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SKY, EARTH, STRUCTURE, INTERIOR, ARTIFACTS, MACHINES, ACTORS, FG = range(8)

LAYER_NAMES = {
    SKY: "sky",
    EARTH: "earth",
    STRUCTURE: "structure",
    INTERIOR: "interior",
    ARTIFACTS: "artifacts",
    MACHINES: "machines",
    ACTORS: "actors",
    FG: "fg",
}

LAYER_Z = {
    SKY: -30,
    EARTH: -20,
    STRUCTURE: -10,
    INTERIOR: 0,
    ARTIFACTS: 7,
    MACHINES: 6,
    ACTORS: 8,
    FG: 12,
}

SKIP_TILE = 0o377
ROOM_COLS = 32
ROOM_ROWS = 18
CELL = 8
SCREEN_W = 256
SCREEN_H = 192  # Spectrum frame with HUD (mosaic / camera)
PLAYFIELD_H = ROOM_ROWS * CELL  # 144 — room stack stride, not SCREEN_H
MAP_W = 32
MAP_ROWS = 31  # MAP at K70632; RMDN 1..31
WORLD_ROWS = 1 + MAP_ROWS  # RMDN 0 is virtual sky (always room 0)
# Engine start: RMAC=17, RMDN=0 (S2CORE K36215 / K36214).
START_RMAC = 17
START_RMDN = 0
# Flip-screen templates stamp these on every outdoor room; the continuous
# world keeps a single instance.
WORLD_UNIQUE_TYPES = frozenset({"moon"})
WALLPAPER_TYPE = "wallpaper_green"
# Behind structure/floors, in front of sky. Interior node, absolute z.
WALLPAPER_Z = -15
# BCHRS 023: indoor brick paper (same glyph as 000; 000 is also a sky skip).
WALLPAPER_TILE = 0o023
INDOOR_TYPE_PREFIXES = (
    "furniture",
    "desk",
    "bookcase",
    "cabinet",
    "door",
    "shelf",
)
OUTDOOR_TYPE_PREFIXES = ("tree_", "rocket")

# Relocation used by ADD #K43310, dest  then index vs L25424 (S2CORE).
K43310 = 0o43310
L25424 = 0o125424

# Paper / empty character indices used as sky or hole in ROM templates.
SKY_TILES = frozenset({0, 1, 0o10})
EMPTY_TILES = frozenset({SKIP_TILE}) | SKY_TILES

# Ladder pair start tiles from S2CORE handlers.
LADDER_START = {
    0o10: 0o005,  # white
    0o16: 0o011,  # wide white
    0o36: 0o045,  # black
    0o41: 0o054,  # black on green
}


@dataclass
class Prefab:
    """Fixed tile stamp (copy-block marker). dest=None means dest comes from the stream."""

    w: int
    h: int
    tiles: tuple[int, ...]
    dest: int | None = None
    layer: int = INTERIOR
    collision: str = "none"
    name: str = ""


@dataclass
class Marker:
    name: str
    layer: int
    collision: str
    mode: str  # fill, ladder, stile, prefab, triangle, skip, joint
    consume: str
    ladder_tile: int = 0
    triangle_stride: int = 32
    prefab: Prefab | None = None


def dest_to_cell(dest: int) -> tuple[int, int]:
    """16-bit room dest → (col, row) in the 32×18 back tile screen."""
    addr = (K43310 + dest) & 0xFFFF
    idx = (addr - L25424) & 0xFFFF
    if idx >= ROOM_COLS * ROOM_ROWS * 4:
        if dest < ROOM_COLS * ROOM_ROWS:
            idx = dest
        else:
            idx %= ROOM_COLS * ROOM_ROWS
    else:
        idx %= ROOM_COLS * ROOM_ROWS
    return idx % ROOM_COLS, idx // ROOM_COLS


def fill_collision(w: int, h: int) -> str:
    if h <= 1:
        return "floor"
    return "solid"


def tile_is_sky(tile: int) -> bool:
    return tile in EMPTY_TILES


def type_id_chr(tile: int) -> str:
    return f"chr_{tile:03o}"


def type_id_ladder(op: int) -> str:
    return {
        0o10: "ladder_white",
        0o16: "ladder_wide",
        0o36: "ladder_black",
        0o41: "ladder_green",
    }.get(op, f"ladder_{op:03o}")


def type_id_stile(n: int) -> str:
    return f"stile_{n:02d}"


def type_id_prefab(op: int) -> str:
    m = MARKERS.get(op)
    if m and m.prefab and m.prefab.name:
        return m.prefab.name
    return f"prefab_{op:03o}"


# Tile templates from S217E6.MAC / S21E80.MAC / S2CORE inline .BYTE
_T = {
    "leaves": (
        0o013, 0o014, 0o015, 0o015, 0o016,
        0o017, 0o020, 0o020, 0o020, 0o021,
        0o017, 0o020, 0o020, 0o020, 0o025,
        0o022, 0o023, 0o024, 0o025, SKIP_TILE,
    ),
    "wing_lb": (0o370, 0o370, 0o370, 0o321, 0o321, 0),
    "wing_rb": (0o370, 0o370, 0o320, 0o370, 0, 0o320),
    "wing_lt": (0, 0o366, 0o366, 0o370, 0o370, 0o370, 0o370, 0o370, 0o370, 0o370, 0o321, 0),
    "wing_rt": (0o365, 0, 0o370, 0o365, 0o370, 0o370, 0o370, 0o370, 0o370, 0o370, 0, 0o320),
    "obj_030": (0, 0, 0o316, 0, 0o316, 0o317, 0o316, 0o317, 0o317),
    "obj_031": (0o315, 0, 0, 0o317, 0o315, 0, 0o317, 0o317, 0o315),
    "obj_034": (1, 0o037, 0o040, 0o036, 0o036, 0o041, 0o036, 0o036, 0o036, 0o036, 1, 0o042, 0o043, 0o044, 0o044),
    "obj_040": (0o047, 0o050, 0o051, 0o036, 0o052, 0o053),
    "obj_035": (0o026, 0o027, 0o030, 0o031, 0o032, 0o033, 0o034, 0o035, 0o036),
    "obj_037": (0o037, 0o037, 0o037, 0o037),
    "moon": (0o032, 0o033, 0o034, 0o035),
    "shelf_8x4": (
        2, 3, 3, 3, 3, 3, 3, 4,
        5, 6, 6, 6, 6, 6, 6, 7,
        5, 6, 6, 6, 6, 6, 6, 7,
        0o10, 0o11, 0o11, 0o11, 0o11, 0o11, 0o11, 0o12,
    ),
    "door_4x4": (
        0o211, 0o212, 0o212, 0o213,
        SKIP_TILE, SKIP_TILE, 0o041, SKIP_TILE,
        SKIP_TILE, SKIP_TILE, 0o041, SKIP_TILE,
        SKIP_TILE, SKIP_TILE, 0o041, SKIP_TILE,
    ),
    "pipe_5x1": (0o322, 0o322, 0o323, 0o323, 0o325),
}


def _pf(name: str, w: int, h: int, key: str, dest: int | None, layer: int, collision: str = "none") -> Prefab:
    tiles = _T[key]
    assert len(tiles) == w * h, (name, len(tiles), w * h)
    return Prefab(w=w, h=h, tiles=tiles, dest=dest, layer=layer, collision=collision, name=name)


def _m(
    name: str,
    layer: int,
    collision: str,
    mode: str,
    consume: str,
    **kw,
) -> Marker:
    return Marker(name=name, layer=layer, collision=collision, mode=mode, consume=consume, **kw)


# Jump table $00–$67 (104 entries). Prefab tile lists for copy-blocks that live
# in other MAC files are filled in by room_bytecode.load_templates().
MARKERS: dict[int, Marker] = {
    0o00: _m("fill_h", STRUCTURE, "floor", "fill", "fill_h"),
    0o01: _m("fill_v", STRUCTURE, "solid", "fill", "fill_v"),
    0o02: _m("fill_rect", STRUCTURE, "solid", "fill", "fill_rect"),
    0o03: _m("fill_room", SKY, "none", "fill", "fill_room"),
    0o04: _m("fill_one", STRUCTURE, "floor", "fill", "fill_one"),
    0o05: _m("rocket_upper", STRUCTURE, "solid", "prefab", "fixed", prefab=Prefab(3, 4, (), 0o62334, STRUCTURE, "solid", "rocket_upper")),
    0o06: _m("fill_diag_rd", EARTH, "solid", "fill", "diag_rd"),
    0o07: _m("fill_diag_ld", EARTH, "solid", "fill", "diag_ld"),
    0o10: _m("ladder_white", INTERIOR, "climb", "ladder", "ladder", ladder_tile=0o005),
    0o11: _m("supertile", EARTH, "solid", "stile", "stile"),
    0o12: _m("tri_down_right", EARTH, "solid", "triangle", "triangle", triangle_stride=32),
    0o13: _m("tri_up_right", EARTH, "solid", "triangle", "triangle", triangle_stride=-32),
    0o14: _m("tri_right_up", EARTH, "solid", "triangle", "triangle", triangle_stride=-31),
    0o15: _m("tri_right_down", EARTH, "solid", "triangle", "triangle", triangle_stride=33),
    0o16: _m("ladder_wide", INTERIOR, "climb", "ladder", "ladder", ladder_tile=0o011),
    0o17: _m("ladder_joint", INTERIOR, "climb", "joint", "joint"),
    0o20: _m("cabinet", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(8, 5, (), 0o62546, FG, "none", "cabinet")),
    0o21: _m("lift_platform", MACHINES, "machine", "prefab", "dest", prefab=Prefab(6, 1, (), None, MACHINES, "machine", "lift_platform")),
    0o22: _m("tree_leaves", SKY, "none", "prefab", "fixed", prefab=_pf("tree_leaves", 5, 4, "leaves", 0o63477, SKY)),
    0o23: _m("moon", SKY, "none", "prefab", "fixed", prefab=_pf("moon", 2, 2, "moon", 0o62245, SKY)),
    0o24: _m("rocket_wing_lt", STRUCTURE, "solid", "prefab", "dest", prefab=_pf("rocket_wing_lt", 2, 6, "wing_lt", None, STRUCTURE, "solid")),
    0o25: _m("rocket_wing_rt", STRUCTURE, "solid", "prefab", "dest", prefab=_pf("rocket_wing_rt", 2, 6, "wing_rt", None, STRUCTURE, "solid")),
    0o26: _m("rocket_wing_lb", STRUCTURE, "solid", "prefab", "fixed", prefab=_pf("rocket_wing_lb", 2, 3, "wing_lb", 0o62570, STRUCTURE, "solid")),
    0o27: _m("rocket_wing_rb", STRUCTURE, "solid", "prefab", "fixed", prefab=_pf("rocket_wing_rb", 2, 3, "wing_rb", 0o62600, STRUCTURE, "solid")),
    0o30: _m("rock_030", EARTH, "solid", "prefab", "fixed", prefab=_pf("rock_030", 3, 3, "obj_030", 0o62731, EARTH, "solid")),
    0o31: _m("rock_031", EARTH, "solid", "prefab", "fixed", prefab=_pf("rock_031", 3, 3, "obj_031", 0o62737, EARTH, "solid")),
    0o32: _m("flag_nop", SKY, "none", "skip", "none"),
    0o33: _m("flag_draw", SKY, "none", "skip", "none"),
    0o34: _m("tree_left", SKY, "none", "prefab", "dest", prefab=_pf("tree_left", 5, 3, "obj_034", None, SKY)),
    0o35: _m("panel_035", INTERIOR, "none", "prefab", "fixed", prefab=_pf("panel_035", 3, 3, "obj_035", 0o64040, INTERIOR)),
    0o36: _m("ladder_black", INTERIOR, "climb", "ladder", "ladder", ladder_tile=0o045),
    0o37: _m("block_037", STRUCTURE, "solid", "prefab", "fixed", prefab=_pf("block_037", 2, 2, "obj_037", 0o64235, STRUCTURE, "solid")),
    0o40: _m("tree_right", SKY, "none", "prefab", "dest", prefab=_pf("tree_right", 3, 2, "obj_040", None, SKY)),
    0o41: _m("ladder_green", INTERIOR, "climb", "ladder", "ladder", ladder_tile=0o054),
    0o42: _m("sign_1", FG, "none", "skip", "none"),
    0o43: _m("sign_2", FG, "none", "skip", "none"),
    0o44: _m("sign_3", FG, "none", "skip", "none"),
    0o45: _m("furniture_045", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(11, 7, (), 0o63666, INTERIOR, "none", "furniture_045")),
    0o46: _m("furniture_046", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 4, (), 0o64044, INTERIOR, "none", "furniture_046")),
    0o47: _m("furniture_047", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(5, 8, (), 0o62540, INTERIOR, "none", "furniture_047")),
    0o50: _m("bookcase_050", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(7, 9, (), 0o62471, INTERIOR, "none", "bookcase")),
    0o51: _m("bookcase_051", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(7, 9, (), 0o62456, INTERIOR, "none", "bookcase")),
    0o52: _m("crate_pair", FG, "none", "prefab", "fixed", prefab=Prefab(2, 3, (), 0o62665, FG, "none", "crate_pair")),
    0o53: _m("crate_row", FG, "none", "prefab", "fixed", prefab=Prefab(5, 3, (), 0o62740, FG, "none", "crate_row")),
    0o54: _m("deco_054", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(2, 3, (), 0o62735, INTERIOR, "none", "deco_054")),
    0o55: _m("deco_055", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(2, 3, (), 0o62732, INTERIOR, "none", "deco_055")),
    0o56: _m("level_sign", FG, "none", "skip", "none"),
    0o57: _m("cabinet_057", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(8, 5, (), 0o62517, FG, "none", "cabinet")),
    0o60: _m("deco_060", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(2, 3, (), 0o64020, INTERIOR, "none", "deco_060")),
    0o61: _m("deco_061", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(2, 3, (), 0o64026, INTERIOR, "none", "deco_061")),
    0o62: _m("deco_062", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(3, 2, (), 0o62342, INTERIOR, "none", "deco_062")),
    0o63: _m("furniture_063", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62625, INTERIOR, "none", "desk")),
    0o64: _m("furniture_064", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62640, INTERIOR, "none", "desk")),
    0o65: _m("furniture_065", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(8, 5, (), 0o62532, INTERIOR, "none", "furniture_065")),
    0o66: _m("furniture_066", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(8, 5, (), 0o62516, INTERIOR, "none", "furniture_066")),
    0o67: _m("furniture_067", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(8, 5, (), 0o62500, INTERIOR, "none", "furniture_067")),
    0o70: _m("furniture_070", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(11, 7, (), 0o63617, INTERIOR, "none", "furniture_070")),
    0o71: _m("furniture_071", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(11, 7, (), 0o63636, INTERIOR, "none", "furniture_071")),
    0o72: _m("furniture_072", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62515, INTERIOR, "none", "desk")),
    0o73: _m("furniture_073", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62532, INTERIOR, "none", "desk")),
    0o74: _m("cabinet_074", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(8, 5, (), 0o62364, FG, "none", "cabinet")),
    0o75: _m("furniture_075", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62542, INTERIOR, "none", "desk")),
    0o76: _m("furniture_076", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(8, 5, (), 0o62401, INTERIOR, "none", "furniture_076")),
    0o77: _m("bookcase_077", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(7, 9, (), 0o62503, INTERIOR, "none", "bookcase")),
    0o100: _m("furniture_100", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(10, 7, (), 0o63637, INTERIOR, "none", "furniture_100")),
    0o101: _m("furniture_101", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(5, 10, (), 0o63461, INTERIOR, "none", "furniture_101")),
    0o102: _m("furniture_102", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(5, 10, (), 0o63506, INTERIOR, "none", "furniture_102")),
    0o103: _m("furniture_103", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(5, 10, (), 0o63475, INTERIOR, "none", "furniture_103")),
    0o104: _m("tri_special", EARTH, "solid", "triangle", "triangle", triangle_stride=33),
    0o105: _m("fill_diag_fixed", EARTH, "solid", "fill", "none"),
    0o106: _m("furniture_106", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(11, 5, (), 0o63730, INTERIOR, "none", "furniture_106")),
    0o107: _m("flag_107", SKY, "none", "skip", "none"),
    0o110: _m("flag_110", SKY, "none", "skip", "none"),
    0o111: _m("pipe_111", STRUCTURE, "solid", "prefab", "fixed", prefab=_pf("pipe_111", 5, 1, "pipe_5x1", 0o63057, STRUCTURE, "floor")),
    0o112: _m("door_112", INTERIOR, "none", "prefab", "fixed", prefab=_pf("door_112", 4, 4, "door_4x4", 0o63760, INTERIOR)),
    0o113: _m("pipe_113", STRUCTURE, "solid", "prefab", "fixed", prefab=_pf("pipe_113", 5, 1, "pipe_5x1", 0o63034, STRUCTURE, "floor")),
    0o114: _m("door_114", INTERIOR, "none", "prefab", "fixed", prefab=_pf("door_114", 4, 4, "door_4x4", 0o63735, INTERIOR)),
    0o115: _m("furniture_115", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(11, 7, (), 0o63615, INTERIOR, "none", "furniture_115")),
    0o116: _m("shelf_116", INTERIOR, "none", "prefab", "fixed", prefab=_pf("shelf_116", 8, 4, "shelf_8x4", 0o63765, INTERIOR)),
    0o117: _m("furniture_117", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(11, 7, (), 0o63633, INTERIOR, "none", "furniture_117")),
    0o120: _m("furniture_120", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(10, 7, (), 0o63255, INTERIOR, "none", "furniture_120")),
    0o121: _m("furniture_121", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(11, 7, (), 0o63655, INTERIOR, "none", "furniture_121")),
    0o122: _m("furniture_122", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(10, 7, (), 0o63263, INTERIOR, "none", "furniture_122")),
    0o123: _m("furniture_123", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(8, 4, (), 0o64026, INTERIOR, "none", "furniture_123")),
    0o124: _m("furniture_124", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62654, INTERIOR, "none", "desk")),
    0o125: _m("furniture_125", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62663, INTERIOR, "none", "desk")),
    0o126: _m("furniture_126", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62675, INTERIOR, "none", "desk")),
    0o127: _m("furniture_127", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62705, INTERIOR, "none", "desk")),
    0o130: _m("furniture_130", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62723, INTERIOR, "none", "desk")),
    0o131: _m("furniture_131", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62733, INTERIOR, "none", "desk")),
    0o132: _m("furniture_132", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62743, INTERIOR, "none", "desk")),
    0o133: _m("furniture_133", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62616, INTERIOR, "none", "desk")),
    0o134: _m("furniture_134", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62631, INTERIOR, "none", "desk")),
    0o135: _m("furniture_135", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62555, INTERIOR, "none", "desk")),
    0o136: _m("furniture_136", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62573, INTERIOR, "none", "desk")),
    0o137: _m("furniture_137", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62602, INTERIOR, "none", "desk")),
    0o140: _m("furniture_140", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(6, 5, (), 0o62564, INTERIOR, "none", "desk")),
    0o141: _m("furniture_141", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(11, 7, (), 0o63023, INTERIOR, "none", "furniture_141")),
    0o142: _m("window_frame", STRUCTURE, "none", "prefab", "fixed", prefab=Prefab(9, 6, (), 0o62164, STRUCTURE, "none", "window")),
    0o143: _m("window_wide", STRUCTURE, "none", "prefab", "fixed", prefab=Prefab(9, 6, (), 0o62177, STRUCTURE, "none", "window_wide")),
    0o144: _m("window_144", STRUCTURE, "none", "prefab", "fixed", prefab=Prefab(9, 6, (), 0o62157, STRUCTURE, "none", "window")),
    0o145: _m("window_145", STRUCTURE, "none", "prefab", "fixed", prefab=Prefab(9, 6, (), 0o62175, STRUCTURE, "none", "window")),
    0o146: _m("window_146", STRUCTURE, "none", "prefab", "fixed", prefab=Prefab(6, 6, (), 0o62260, STRUCTURE, "none", "window")),
    0o147: _m("deco_147", INTERIOR, "none", "prefab", "fixed", prefab=Prefab(2, 3, (), 0o62726, INTERIOR, "none", "deco_147")),
}

# Labels whose bytes are loaded into Prefab.tiles at startup.
TEMPLATE_LABELS: dict[str, tuple[int, ...]] = {
    "K13746": (0o60, 0o61),
    "K13754": (0o101, 0o102, 0o103),
    "K14036": (0o20, 0o57, 0o74),
    "K14106": (0o47,),
    "K14156": (0o50, 0o51, 0o77),
    "K14255": (0o53,),
    "K14274": (0o52, 0o54, 0o55, 0o147),
    "K14302": (0o62,),
    "K14310": (0o63, 0o64, 0o72, 0o73, 0o75, 0o124, 0o125, 0o126, 0o127, 0o130, 0o131, 0o132, 0o133, 0o134, 0o135, 0o136, 0o137, 0o140),
    "K14346": (0o142, 0o143, 0o144, 0o145),
    "K14434": (0o146,),
    "K17362": (0o46,),
    "K17412": (0o45, 0o70, 0o71, 0o115, 0o117, 0o121, 0o141),
    "K17527": (0o100, 0o120, 0o122),
    "K16702": (0o116, 0o123),
    "K17204": (0o106,),
}


def apply_template_bytes(op: int, tiles: list[int]) -> None:
    m = MARKERS.get(op)
    if m is None or m.prefab is None:
        return
    pf = m.prefab
    need = pf.w * pf.h
    data = tuple(tiles[:need])
    if len(data) < need:
        data = data + (SKIP_TILE,) * (need - len(data))
    m.prefab = Prefab(pf.w, pf.h, data, pf.dest, pf.layer, pf.collision, pf.name)
