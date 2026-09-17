"""Generate the CodexQuotaMonitor ICO from the runtime tray-icon geometry."""

from __future__ import annotations

import binascii
import math
import struct
import zlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "assets" / "CodexQuotaMonitor.ico"


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _png(size: int) -> bytes:
    pixels = bytearray(size * size * 4)
    center = (size - 1) / 2.0
    outer_radius = size * 0.47
    inner_radius = size * 0.34
    green = (71, 188, 148)
    inner = (39, 51, 64)
    white = (244, 246, 248)

    def set_pixel(x: int, y: int, rgba: tuple[int, int, int, int]) -> None:
        offset = (y * size + x) * 4
        pixels[offset : offset + 4] = bytes(rgba)

    for y in range(size):
        for x in range(size):
            distance = math.hypot(x - center, y - center)
            if distance > outer_radius + 1.0:
                continue
            if distance > outer_radius - 1.0:
                alpha = int(max(0.0, min(1.0, outer_radius + 1.0 - distance)) * 255)
                set_pixel(x, y, (*green, alpha))
            elif distance >= inner_radius:
                set_pixel(x, y, (*green, 255))
            else:
                set_pixel(x, y, (*inner, 255))

    scale = max(1, size // 16)
    glyph = ("1111", "1000", "1000", "1000", "1111")
    glyph_width = len(glyph[0]) * scale
    glyph_height = len(glyph) * scale
    glyph_x = (size - glyph_width) // 2
    glyph_y = (size - glyph_height) // 2
    for row, pattern in enumerate(glyph):
        for column, value in enumerate(pattern):
            if value != "1":
                continue
            for yy in range(scale):
                for xx in range(scale):
                    set_pixel(
                        glyph_x + column * scale + xx,
                        glyph_y + row * scale + yy,
                        (*white, 255),
                    )

    raw = b"".join(b"\x00" + bytes(pixels[row * size * 4 : (row + 1) * size * 4]) for row in range(size))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")


def build_icon_bytes() -> bytes:
    """Return the ICO payload for the current geometry without touching the filesystem."""

    images = [(size, _png(size)) for size in (16, 32, 48, 256)]
    directory = struct.pack("<HHH", 0, 1, len(images))
    entries = bytearray()
    payload = bytearray()
    offset = 6 + 16 * len(images)
    for size, image in images:
        dimension = 0 if size >= 256 else size
        entries.extend(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(image), offset))
        payload.extend(image)
        offset += len(image)
    return bytes(directory + entries + payload)


def write_if_changed(data: bytes) -> bool:
    """Write the ICO only when its content differs; return True when a write happened."""

    if OUTPUT.is_file():
        try:
            if OUTPUT.read_bytes() == data:
                return False
        except OSError:
            pass
    OUTPUT.write_bytes(data)
    return True


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    data = build_icon_bytes()
    if write_if_changed(data):
        print(f"Generated {OUTPUT}")
    else:
        print(f"Unchanged {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
