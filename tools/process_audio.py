#!/usr/bin/env python3
"""Rebuild game WAV files from CC0 downloads in assets/audio/_source/.

Effects: 22050 Hz, 16-bit mono, silence trimmed, peaks level-matched.
Music: 44100 Hz, 16-bit stereo. theme_fast is the same track at 1.4x speed.
Loops are crossfaded so the join does not click.

Requires numpy and miniaudio (Vorbis/MP3/FLAC/WAV decode). No ffmpeg.
    pip install numpy miniaudio
    python tools/process_audio.py

Raw downloads stay in assets/audio/_source/ and are gitignored.
The script is deterministic: a second run writes identical bytes.
"""

from __future__ import annotations

import math
import shutil
import urllib.request
import wave
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "audio" / "_source"
ZIPS = SOURCE / "zips"
LOOSE = SOURCE / "loose"
UNZ = SOURCE / "unz"
SFX_OUT = ROOT / "assets" / "audio" / "sfx"
MUSIC_OUT = ROOT / "assets" / "audio" / "music"

SFX_RATE = 22050
MUSIC_RATE = 44100
SPEED = 1.4
MUSIC_PEAK_DB = -4.0
LOOP_FADE_SEC = 0.12

# zip name -> download URL. Pages were checked for CC0 before these URLs
# were written down. See assets/CREDITS.md.
PACKS: dict[str, str] = {
    "kenney_impact-sounds.zip": (
        "https://kenney.nl/media/pages/assets/impact-sounds/"
        "87b4ddecda-1677589768/kenney_impact-sounds.zip"
    ),
    "kenney_interface-sounds.zip": (
        "https://kenney.nl/media/pages/assets/interface-sounds/"
        "fa43c1dd4d-1677589452/kenney_interface-sounds.zip"
    ),
    "kenney_rpg-audio.zip": (
        "https://kenney.nl/media/pages/assets/rpg-audio/"
        "8e99002d76-1677590336/kenney_rpg-audio.zip"
    ),
    "swishes.zip": "https://opengameart.org/sites/default/files/swishes.zip",
    "100-CC0-SFX_0.zip": (
        "https://opengameart.org/sites/default/files/100-CC0-SFX_0.zip"
    ),
    "yd-Sounds.zip": "https://opengameart.org/sites/default/files/yd-Sounds.zip",
    "sfx_loops.zip": "https://opengameart.org/sites/default/files/sfx_loops.zip",
}

LOOSE_FILES: dict[str, str] = {
    "espionage.ogg": "https://opengameart.org/sites/default/files/espionage.ogg",
}

# peak_db: hits near -3. Steps and landings stay soft: Nina is a ninja.
# max_ms: hard cap after the silence trim (0 = no cap).
SFX: list[dict] = [
    {
        "name": "step",
        "pack": "kenney_impact-sounds.zip",
        "member": "Audio/footstep_concrete_004.ogg",
        "peak_db": -20.0,
        "max_ms": 140,
        "trim_db": -80.0,
    },
    {
        "name": "punch",
        "pack": "kenney_impact-sounds.zip",
        "member": "Audio/impactSoft_medium_002.ogg",
        "peak_db": -8.0,
        "max_ms": 140,
        "trim_db": -40.0,
    },
    {
        "name": "hit",
        "pack": "kenney_impact-sounds.zip",
        "member": "Audio/impactSoft_heavy_001.ogg",
        "peak_db": -3.0,
        "max_ms": 320,
        "trim_db": -40.0,
    },
    {
        "name": "somersault",
        "pack": "swishes.zip",
        "member": "swishes/swish-4.wav",
        "peak_db": -6.0,
        "max_ms": 180,
        "trim_db": -38.0,
    },
    {
        "name": "land",
        "pack": "kenney_impact-sounds.zip",
        "member": "Audio/footstep_grass_002.ogg",
        "peak_db": -18.0,
        "max_ms": 800,
        "trim_db": -80.0,
    },
    {
        "name": "ladder",
        "pack": "kenney_impact-sounds.zip",
        "member": "Audio/footstep_carpet_004.ogg",
        "peak_db": -20.0,
        "max_ms": 80,
        "trim_db": -36.0,
    },
    {
        "name": "lift_start",
        "pack": "100-CC0-SFX_0.zip",
        "member": "machine_01.ogg",
        "peak_db": -6.0,
        "max_ms": 520,
        "trim_db": -42.0,
    },
    {
        "name": "lift_stop",
        "pack": "kenney_rpg-audio.zip",
        "member": "Audio/metalLatch.ogg",
        "peak_db": -6.0,
        "max_ms": 180,
        "trim_db": -40.0,
    },
    {
        "name": "pickup",
        "pack": "kenney_interface-sounds.zip",
        "member": "Audio/confirmation_001.ogg",
        "peak_db": -6.0,
        "max_ms": 340,
        "trim_db": -42.0,
    },
    {
        "name": "alarm",
        "pack": "sfx_loops.zip",
        "member": "alarm_03.ogg",
        "peak_db": -12.0,
        "max_ms": 1200,
        "trim_db": -40.0,
        "lowpass_hz": 1800.0,
        "fade_in_ms": 140.0,
        "fade_out_ms": 180.0,
    },
    {
        "name": "spotted",
        "pack": "kenney_impact-sounds.zip",
        "member": "Audio/impactBell_heavy_004.ogg",
        "peak_db": -6.0,
        "max_ms": 280,
        "trim_db": -40.0,
    },
    {
        "name": "fuse_tick",
        "pack": "kenney_interface-sounds.zip",
        "member": "Audio/tick_002.ogg",
        "peak_db": -12.0,
        "max_ms": 70,
        "trim_db": -36.0,
    },
    {
        "name": "death",
        "pack": "100-CC0-SFX_0.zip",
        "member": "slam_01.ogg",
        "peak_db": -3.0,
        "max_ms": 420,
        "trim_db": -40.0,
    },
    {
        "name": "win",
        "pack": "kenney_interface-sounds.zip",
        "member": "Audio/confirmation_004.ogg",
        "peak_db": -3.0,
        "max_ms": 560,
        "trim_db": -42.0,
    },
    {
        "name": "rope_mount",
        "pack": "kenney_rpg-audio.zip",
        "member": "Audio/cloth2.ogg",
        "peak_db": -8.0,
        "max_ms": 280,
        "trim_db": -46.0,
    },
    {
        "name": "rope_fall",
        "pack": "swishes.zip",
        "member": "swishes/swish-9.wav",
        "peak_db": -6.0,
        "max_ms": 220,
        "trim_db": -38.0,
    },
]


def _download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1000:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "saboteur-92-audio/1.0"})
    print(f"download {dest.name}")
    with urllib.request.urlopen(req, timeout=180) as response, dest.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _ensure_sources() -> None:
    # Godot imports every file under the project. An empty .gdignore keeps
    # the raw downloads out of the resource scan.
    SOURCE.mkdir(parents=True, exist_ok=True)
    ignore = SOURCE / ".gdignore"
    if not ignore.exists():
        ignore.write_bytes(b"")
    for name, url in PACKS.items():
        _download(url, ZIPS / name)
    for name, url in LOOSE_FILES.items():
        _download(url, LOOSE / name)


def _source_path(spec: dict) -> Path:
    loose = spec.get("loose")
    if loose:
        return LOOSE / loose
    pack = spec["pack"]
    member = spec["member"]
    dest = UNZ / pack.replace(".zip", "") / member
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIPS / pack) as archive:
        archive.extract(member, UNZ / pack.replace(".zip", ""))
    return dest


def decode(path: Path) -> tuple[np.ndarray, int]:
    import miniaudio

    decoded = miniaudio.decode_file(
        str(path),
        output_format=miniaudio.SampleFormat.FLOAT32,
        dither=miniaudio.DitherMode.NONE,
    )
    frames = np.array(decoded.samples, dtype=np.float64, copy=True)
    frames = frames.reshape(-1, decoded.nchannels)
    return frames, int(decoded.sample_rate)


def _lowpass(frames: np.ndarray, cutoff: float, sample_rate: int, taps: int = 63) -> np.ndarray:
    if taps % 2 == 0:
        taps += 1
    offsets = np.arange(taps, dtype=np.float64) - (taps // 2)
    kernel = np.sinc(2.0 * cutoff / sample_rate * offsets) * np.hamming(taps)
    kernel /= np.sum(kernel)
    if frames.ndim == 1:
        return np.convolve(frames, kernel, mode="same")
    columns = [np.convolve(frames[:, channel], kernel, mode="same") for channel in range(frames.shape[1])]
    return np.stack(columns, axis=1)


def resample(frames: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return frames
    filtered = frames
    if dst_rate < src_rate:
        filtered = _lowpass(frames, cutoff=0.45 * dst_rate, sample_rate=src_rate)
    count = max(1, int(round(filtered.shape[0] * dst_rate / src_rate)))
    src_index = np.arange(filtered.shape[0], dtype=np.float64)
    dst_index = np.linspace(0.0, filtered.shape[0] - 1, count)
    if filtered.ndim == 1:
        return np.interp(dst_index, src_index, filtered)
    columns = [
        np.interp(dst_index, src_index, filtered[:, channel]) for channel in range(filtered.shape[1])
    ]
    return np.stack(columns, axis=1)


def _fade(frames: np.ndarray, start: int, stop: int, ramp: np.ndarray) -> None:
    if ramp.size < 2:
        return
    if frames.ndim == 1:
        frames[start:stop] *= ramp
    else:
        frames[start:stop] *= ramp[:, None]


def trim_silence(frames: np.ndarray, sample_rate: int, thresh_db: float, pad_ms: float = 3.0) -> np.ndarray:
    level = frames if frames.ndim == 1 else np.max(np.abs(frames), axis=1)
    threshold = 10.0 ** (thresh_db / 20.0)
    hits = np.flatnonzero(np.abs(level) >= threshold)
    if hits.size == 0:
        return frames[:1]
    pad = int(round(pad_ms * sample_rate / 1000.0))
    start = max(0, int(hits[0]) - pad)
    stop = min(frames.shape[0], int(hits[-1]) + pad + 1)
    return frames[start:stop]


def cap_duration(frames: np.ndarray, sample_rate: int, max_ms: int, fade_ms: float = 12.0) -> np.ndarray:
    if max_ms <= 0:
        return frames
    limit = int(round(max_ms * sample_rate / 1000.0))
    if frames.shape[0] <= limit:
        return frames
    clipped = frames[:limit].copy()
    fade = min(int(round(fade_ms * sample_rate / 1000.0)), max(2, limit // 4))
    _fade(clipped, limit - fade, limit, np.linspace(1.0, 0.0, fade))
    return clipped


def edge_fades(frames: np.ndarray, sample_rate: int, fade_in_ms: float = 0.8, fade_out_ms: float = 5.0) -> np.ndarray:
    faded = frames.copy()
    count = faded.shape[0]
    fade_in = min(int(round(fade_in_ms * sample_rate / 1000.0)), max(2, count // 5))
    fade_out = min(int(round(fade_out_ms * sample_rate / 1000.0)), max(2, count // 5))
    _fade(faded, 0, fade_in, np.linspace(0.0, 1.0, fade_in))
    _fade(faded, count - fade_out, count, np.linspace(1.0, 0.0, fade_out))
    return faded


def remove_dc(frames: np.ndarray) -> np.ndarray:
    if frames.ndim == 1:
        return frames - np.mean(frames)
    return frames - np.mean(frames, axis=0, keepdims=True)


def normalize_peak(frames: np.ndarray, peak_db: float) -> np.ndarray:
    target = 10.0 ** (peak_db / 20.0)
    peak = float(np.max(np.abs(frames)))
    if peak < 1e-8:
        return frames
    return frames * (target / peak)


def time_compress(frames: np.ndarray, factor: float) -> np.ndarray:
    count = max(1, int(round(frames.shape[0] / factor)))
    src_index = np.arange(frames.shape[0], dtype=np.float64)
    dst_index = np.linspace(0.0, frames.shape[0] - 1, count)
    columns = [
        np.interp(dst_index, src_index, frames[:, channel]) for channel in range(frames.shape[1])
    ]
    return np.stack(columns, axis=1)


def loop_crossfade(frames: np.ndarray, fade_samples: int) -> np.ndarray:
    """Overlap the tail onto the head so the buffer wraps on adjacent samples."""
    if fade_samples < 8 or fade_samples * 2 >= frames.shape[0]:
        return frames
    angle = np.linspace(0.0, math.pi / 2.0, fade_samples)
    fade_in = np.sin(angle)
    fade_out = np.cos(angle)
    blended = frames[:fade_samples] * fade_in[:, None] + frames[-fade_samples:] * fade_out[:, None]
    return np.concatenate([blended, frames[fade_samples:-fade_samples]], axis=0)


def to_pcm(frames: np.ndarray) -> np.ndarray:
    scaled = np.rint(frames * 32767.0)
    return np.clip(scaled, -32768, 32767).astype("<i2")


def write_wav(path: Path, frames: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = to_pcm(frames)
    channels = 1 if pcm.ndim == 1 else pcm.shape[1]
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def describe(path: Path) -> str:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
        channels = handle.getnchannels()
        raw = handle.readframes(frames)
    pcm = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    peak = float(np.max(np.abs(pcm))) / 32767.0
    peak_db = 20.0 * math.log10(peak + 1e-12)
    duration_ms = frames / rate * 1000.0
    return f"{duration_ms:7.0f} ms  peak {peak_db:6.1f} dB  {rate} Hz {channels} ch"


def process_sfx(spec: dict) -> Path:
    source = _source_path(spec)
    frames, rate = decode(source)
    mono = frames.mean(axis=1) if frames.shape[1] > 1 else frames[:, 0]
    mono = resample(mono, rate, SFX_RATE)
    mono = trim_silence(mono, SFX_RATE, spec["trim_db"])
    mono = cap_duration(mono, SFX_RATE, spec["max_ms"])
    cutoff = float(spec.get("lowpass_hz", 0.0))
    if cutoff > 0.0:
        mono = _lowpass(mono, cutoff, SFX_RATE, taps=255)
    mono = edge_fades(
        mono,
        SFX_RATE,
        fade_in_ms=float(spec.get("fade_in_ms", 0.8)),
        fade_out_ms=float(spec.get("fade_out_ms", 5.0)),
    )
    mono = remove_dc(mono)
    mono = normalize_peak(mono, spec["peak_db"])
    dest = SFX_OUT / f"{spec['name']}.wav"
    write_wav(dest, mono, SFX_RATE)
    return dest


def _prepare_music(frames: np.ndarray, rate: int, speed: float) -> np.ndarray:
    stereo = frames if frames.shape[1] == 2 else np.repeat(frames[:, :1], 2, axis=1)
    stereo = resample(stereo, rate, MUSIC_RATE)
    if speed != 1.0:
        stereo = time_compress(stereo, speed)
    stereo = remove_dc(stereo)
    fade = int(round(LOOP_FADE_SEC * MUSIC_RATE))
    stereo = loop_crossfade(stereo, fade)
    return normalize_peak(stereo, MUSIC_PEAK_DB)


def _seam_step(frames: np.ndarray) -> tuple[float, float]:
    mono = frames.mean(axis=1)
    jump = abs(float(mono[0] - mono[-1]))
    window = mono[: min(mono.size, MUSIC_RATE)]
    typical = float(np.median(np.abs(np.diff(window))))
    return jump, typical


def process_music() -> list[Path]:
    frames, rate = decode(LOOSE / "espionage.ogg")
    written: list[Path] = []
    for name, speed in (("theme", 1.0), ("theme_fast", SPEED)):
        prepared = _prepare_music(frames, rate, speed)
        jump, typical = _seam_step(prepared)
        dest = MUSIC_OUT / f"{name}.wav"
        write_wav(dest, prepared, MUSIC_RATE)
        written.append(dest)
        print(f"  loop seam {name}: boundary {jump:.6f}  median step {typical:.6f}")
    return written


def main() -> None:
    _ensure_sources()
    written: list[Path] = []
    for spec in SFX:
        written.append(process_sfx(spec))
    written.extend(process_music())
    for path in written:
        print(f"{path.relative_to(ROOT).as_posix():32} {describe(path)}")
    print(f"ok: {len(written)} files")


if __name__ == "__main__":
    main()
