#!/usr/bin/env python3
"""Generate ZX-beeper-style SFX and music for Saboteur 92.

WAV: 22050 Hz, 16-bit PCM, mono. Deterministic — same bytes every run.
Stdlib only (wave, struct, math, pathlib). No random, no timestamps.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_SFX = ROOT / "assets" / "audio" / "sfx"
OUT_MUSIC = ROOT / "assets" / "audio" / "music"

RATE = 22050
AMP = 12000  # leave headroom under int16 max


def _clamp(v: float) -> int:
    iv = int(round(v))
    if iv > 32767:
        return 32767
    if iv < -32768:
        return -32768
    return iv


def _write_wav(path: Path, samples: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(b"".join(struct.pack("<h", s) for s in samples))


def _square(freq: float, t: float, duty: float = 0.5) -> float:
    phase = (t * freq) % 1.0
    return 1.0 if phase < duty else -1.0


def _noise(t: float, seed: int = 1) -> float:
    # Deterministic hash noise (not PRNG state).
    x = int(t * RATE) ^ (seed * 2654435761)
    x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13
    return 1.0 if (x & 1) else -1.0


def _env_lin(i: int, n: int, attack: float = 0.01, release: float = 0.15) -> float:
    if n <= 1:
        return 0.0
    t = i / (n - 1)
    a = min(1.0, t / attack) if attack > 0 else 1.0
    r = min(1.0, (1.0 - t) / release) if release > 0 else 1.0
    return a * r


def tone(
    freq: float,
    ms: float,
    *,
    amp: float = 1.0,
    duty: float = 0.5,
    attack: float = 0.02,
    release: float = 0.2,
) -> list[int]:
    n = max(1, int(RATE * ms / 1000.0))
    out: list[int] = []
    for i in range(n):
        t = i / RATE
        e = _env_lin(i, n, attack, release)
        out.append(_clamp(AMP * amp * e * _square(freq, t, duty)))
    return out


def sweep(
    f0: float,
    f1: float,
    ms: float,
    *,
    amp: float = 1.0,
    duty: float = 0.5,
    attack: float = 0.02,
    release: float = 0.15,
) -> list[int]:
    n = max(1, int(RATE * ms / 1000.0))
    out: list[int] = []
    for i in range(n):
        u = i / (n - 1) if n > 1 else 0.0
        freq = f0 + (f1 - f0) * u
        t = i / RATE
        e = _env_lin(i, n, attack, release)
        out.append(_clamp(AMP * amp * e * _square(freq, t, duty)))
    return out


def noise_burst(
    ms: float,
    *,
    amp: float = 0.7,
    seed: int = 1,
    attack: float = 0.01,
    release: float = 0.35,
) -> list[int]:
    n = max(1, int(RATE * ms / 1000.0))
    out: list[int] = []
    for i in range(n):
        t = i / RATE
        e = _env_lin(i, n, attack, release)
        out.append(_clamp(AMP * amp * e * _noise(t, seed)))
    return out


def silence(ms: float) -> list[int]:
    return [0] * max(1, int(RATE * ms / 1000.0))


def concat(*parts: list[int]) -> list[int]:
    out: list[int] = []
    for p in parts:
        out.extend(p)
    return out


def mix(*layers: list[int], amp: float = 1.0) -> list[int]:
    n = max((len(L) for L in layers), default=0)
    out = [0] * n
    for layer in layers:
        for i, s in enumerate(layer):
            out[i] += s
    return [_clamp(v * amp) for v in out]


# --- SFX recipes (ZX beeper: square, short sweeps, noise) -------------------


def sfx_step() -> list[int]:
    return tone(180, 35, amp=0.45, duty=0.4, attack=0.05, release=0.55)


def sfx_punch() -> list[int]:
    return concat(
        sweep(220, 90, 45, amp=0.85, duty=0.5, attack=0.02, release=0.4),
        noise_burst(25, amp=0.35, seed=3, release=0.6),
    )


def sfx_hit() -> list[int]:
    return concat(
        noise_burst(40, amp=0.8, seed=7, attack=0.01, release=0.45),
        sweep(400, 120, 50, amp=0.55, duty=0.35, release=0.5),
    )


def sfx_somersault() -> list[int]:
    return concat(
        sweep(300, 700, 90, amp=0.55, duty=0.45, attack=0.05, release=0.2),
        sweep(700, 350, 80, amp=0.45, duty=0.45, attack=0.05, release=0.35),
    )


def sfx_land() -> list[int]:
    return concat(
        tone(120, 30, amp=0.6, duty=0.5, attack=0.02, release=0.5),
        noise_burst(20, amp=0.25, seed=11, release=0.7),
    )


def sfx_ladder() -> list[int]:
    return tone(260, 40, amp=0.4, duty=0.3, attack=0.08, release=0.5)


def sfx_lift_start() -> list[int]:
    return concat(
        sweep(80, 160, 120, amp=0.5, duty=0.5, attack=0.1, release=0.25),
        tone(160, 60, amp=0.35, duty=0.5, attack=0.05, release=0.4),
    )


def sfx_lift_stop() -> list[int]:
    return concat(
        tone(160, 40, amp=0.4, duty=0.5, attack=0.05, release=0.3),
        sweep(160, 70, 80, amp=0.35, duty=0.5, release=0.45),
    )


def sfx_pickup() -> list[int]:
    return concat(
        tone(523, 60, amp=0.55, duty=0.5, attack=0.05, release=0.25),
        tone(784, 90, amp=0.55, duty=0.5, attack=0.05, release=0.4),
    )


def sfx_alarm() -> list[int]:
    # Two alternating beeps, classic Spectrum alert.
    beep = tone(880, 90, amp=0.7, duty=0.5, attack=0.02, release=0.15)
    gap = silence(40)
    low = tone(660, 90, amp=0.7, duty=0.5, attack=0.02, release=0.15)
    return concat(beep, gap, low, gap, beep, gap, low)


def sfx_spotted() -> list[int]:
    # A guard notices Nina: short rising "hey!" chirp, quieter than the alarm.
    return concat(
        tone(587, 45, amp=0.55, duty=0.5, attack=0.02, release=0.2),
        silence(20),
        sweep(700, 1180, 70, amp=0.55, duty=0.5, attack=0.02, release=0.35),
    )


def sfx_fuse_tick() -> list[int]:
    return tone(1000, 28, amp=0.4, duty=0.25, attack=0.05, release=0.55)


def sfx_death() -> list[int]:
    return concat(
        sweep(400, 80, 280, amp=0.7, duty=0.5, attack=0.02, release=0.35),
        noise_burst(120, amp=0.4, seed=17, release=0.5),
    )


def sfx_win() -> list[int]:
    notes = [392, 494, 587, 784, 988]
    parts: list[list[int]] = []
    for i, f in enumerate(notes):
        parts.append(tone(f, 90 if i < len(notes) - 1 else 180, amp=0.55, duty=0.5, release=0.3))
        if i < len(notes) - 1:
            parts.append(silence(15))
    return concat(*parts)


def sfx_rope_mount() -> list[int]:
    return concat(
        tone(340, 35, amp=0.4, duty=0.4, attack=0.05, release=0.4),
        sweep(340, 480, 55, amp=0.35, duty=0.4, release=0.4),
    )


def sfx_rope_fall() -> list[int]:
    return concat(
        noise_burst(30, amp=0.45, seed=23, release=0.4),
        sweep(500, 140, 160, amp=0.55, duty=0.45, attack=0.02, release=0.35),
    )


# --- Music: short looping beeper motif --------------------------------------

# Melody in Hz; durations in ms. Phrase designed to loop cleanly.
_THEME_NOTES: list[tuple[float, float]] = [
    (262, 140),
    (0, 40),
    (330, 140),
    (0, 40),
    (392, 140),
    (0, 40),
    (523, 200),
    (0, 80),
    (392, 140),
    (0, 40),
    (330, 140),
    (0, 40),
    (294, 140),
    (0, 40),
    (262, 280),
    (0, 120),
    (196, 140),
    (0, 40),
    (262, 140),
    (0, 40),
    (330, 140),
    (0, 40),
    (392, 280),
    (0, 120),
]


def _melody(notes: list[tuple[float, float]], *, speed: float = 1.0, amp: float = 0.35) -> list[int]:
    parts: list[list[int]] = []
    for freq, ms in notes:
        dur = ms / speed
        if freq <= 0:
            parts.append(silence(dur))
        else:
            parts.append(
                tone(freq, dur, amp=amp, duty=0.5, attack=0.04, release=0.2)
            )
    return concat(*parts)


def music_theme() -> list[int]:
    return _melody(_THEME_NOTES, speed=1.0, amp=0.32)


def music_theme_fast() -> list[int]:
    # Fuse countdown: same motif, ~1.45× tempo.
    return _melody(_THEME_NOTES, speed=1.45, amp=0.34)


SFX: dict[str, callable] = {
    "step": sfx_step,
    "punch": sfx_punch,
    "hit": sfx_hit,
    "somersault": sfx_somersault,
    "land": sfx_land,
    "ladder": sfx_ladder,
    "lift_start": sfx_lift_start,
    "lift_stop": sfx_lift_stop,
    "pickup": sfx_pickup,
    "alarm": sfx_alarm,
    "spotted": sfx_spotted,
    "fuse_tick": sfx_fuse_tick,
    "death": sfx_death,
    "win": sfx_win,
    "rope_mount": sfx_rope_mount,
    "rope_fall": sfx_rope_fall,
}

MUSIC: dict[str, callable] = {
    "theme": music_theme,
    "theme_fast": music_theme_fast,
}


def generate_all() -> list[Path]:
    written: list[Path] = []
    for name, fn in SFX.items():
        path = OUT_SFX / f"{name}.wav"
        _write_wav(path, fn())
        written.append(path)
    for name, fn in MUSIC.items():
        path = OUT_MUSIC / f"{name}.wav"
        _write_wav(path, fn())
        written.append(path)
    return written


def main() -> None:
    paths = generate_all()
    for p in paths:
        print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size} bytes)")
    print(f"ok: {len(paths)} files")


if __name__ == "__main__":
    main()
