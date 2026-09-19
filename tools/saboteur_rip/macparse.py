"""Parse MACRO-11 .BYTE/.WORD octal dumps from SABOT2-DISASM."""
from __future__ import annotations

import re
from pathlib import Path

LABEL_RE = re.compile(r"^([A-Z][0-9A-Z]*):", re.I)
BYTE_RE = re.compile(r"\.BYTE\s+(.+)$", re.I)
WORD_RE = re.compile(r"\.WORD\s+(.+)$", re.I)


def parse_octal_tokens(part: str) -> list[int]:
    out: list[int] = []
    for tok in part.split(","):
        tok = tok.strip()
        if not tok or tok.startswith(";"):
            break
        tok = tok.split(";")[0].strip().rstrip(",")
        if not tok:
            continue
        if tok[:1] in "<\"'":
            continue
        try:
            out.append(int(tok, 8))
        except ValueError:
            continue
    return out


def parse_mac_bytes(path: Path) -> dict[str, list[int]]:
    blocks: dict[str, list[int]] = {}
    current: str | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        m = LABEL_RE.match(line)
        if m:
            current = m.group(1)
            blocks.setdefault(current, [])
            rest = line[m.end() :].strip()
            if ".BYTE" in rest.upper():
                blocks[current].extend(parse_octal_tokens(rest.split(".BYTE", 1)[-1]))
            elif ".WORD" in rest.upper():
                for w in parse_octal_tokens(rest.split(".WORD", 1)[-1]):
                    blocks[current].extend([w & 0xFF, (w >> 8) & 0xFF])
            continue
        if current is None:
            continue
        bm = BYTE_RE.search(line)
        if bm:
            blocks[current].extend(parse_octal_tokens(bm.group(1)))
            continue
        wm = WORD_RE.search(line)
        if wm:
            for w in parse_octal_tokens(wm.group(1)):
                blocks[current].extend([w & 0xFF, (w >> 8) & 0xFF])
    return blocks


def parse_word_table(path: Path, label: str) -> list[int]:
    words: list[int] = []
    grab = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith(label + ":"):
            grab = True
            rest = line.split(":", 1)[1].strip()
            if ".WORD" in rest.upper():
                words.extend(parse_octal_tokens(rest.split(".WORD", 1)[-1]))
            continue
        if not grab:
            continue
        if ".WORD" in line.upper():
            words.extend(parse_octal_tokens(line.split(".WORD", 1)[-1]))
        elif LABEL_RE.match(line):
            break
    return words
