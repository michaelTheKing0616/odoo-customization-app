"""Distinctive PNG app icons for Apps Store zips and live-metadata home tiles.

Odoo 19 treats Font Awesome ``fa-book,#hex`` as a file path and aborts menu create.
Live Apply therefore cannot use FA ``web_icon``. Installable modules use
``static/description/icon.png`` (the only icon Apps Store reads). This module
paints a 64×64 PNG from the app name so we stop shipping a 1×1 placeholder.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from typing import Any

ICON_SIZE = 64

# 5×7 bitmap font (MSB left). Covers A–Z, 0–9, and a few punctuation marks.
_FONT_5X7: dict[str, tuple[int, ...]] = {
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x01, 0x01, 0x01, 0x01, 0x11, 0x11, 0x0E),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F),
    "3": (0x1E, 0x01, 0x01, 0x0E, 0x01, 0x01, 0x1E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
}


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def encode_png_rgba(width: int, height: int, pixels: bytes) -> bytes:
    """``pixels`` is ``width * height * 4`` RGBA bytes."""
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * stride : (y + 1) * stride])
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def _hue_rgb(seed: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    hue = digest[0] / 255.0
    sat = 0.45 + (digest[1] / 255.0) * 0.25
    val = 0.42 + (digest[2] / 255.0) * 0.18
    return _hsv_to_rgb(hue, sat, val)


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    i = int(h * 6.0) % 6
    f = h * 6.0 - int(h * 6.0)
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    table = (
        (v, t, p),
        (q, v, p),
        (p, v, t),
        (p, q, v),
        (t, p, v),
        (v, p, q),
    )
    r, g, b = table[i]
    return int(r * 255), int(g * 255), int(b * 255)


def _initials(name: str) -> str:
    tokens = [t for t in "".join(ch if ch.isalnum() else " " for ch in (name or "")).split() if t]
    if not tokens:
        return "AP"
    if len(tokens) == 1:
        word = tokens[0].upper()
        return (word[:2] if len(word) >= 2 else (word + "X")[:2])
    return (tokens[0][0] + tokens[1][0]).upper()


def _blit_glyph(buf: bytearray, ch: str, origin_x: int, origin_y: int, rgb: tuple[int, int, int]) -> None:
    rows = _FONT_5X7.get(ch.upper())
    if not rows:
        return
    scale = 4
    r, g, b = rgb
    for gy, bits in enumerate(rows):
        for gx in range(5):
            if not (bits & (1 << (4 - gx))):
                continue
            for dy in range(scale):
                for dx in range(scale):
                    x = origin_x + gx * scale + dx
                    y = origin_y + gy * scale + dy
                    if 0 <= x < ICON_SIZE and 0 <= y < ICON_SIZE:
                        i = (y * ICON_SIZE + x) * 4
                        buf[i : i + 4] = bytes((r, g, b, 255))


def render_app_icon_png(name: str, *, seed: str | None = None) -> bytes:
    """Paint a 64×64 rounded-square icon with two initials. Deterministic per name."""
    label = (name or "App").strip() or "App"
    bg = _hue_rgb(seed or label.lower())
    fg = (250, 250, 248)
    pixels = bytearray(ICON_SIZE * ICON_SIZE * 4)
    radius = 10
    for y in range(ICON_SIZE):
        for x in range(ICON_SIZE):
            inset_x = min(x, ICON_SIZE - 1 - x)
            inset_y = min(y, ICON_SIZE - 1 - y)
            corner = inset_x < radius and inset_y < radius
            if corner:
                dx = radius - inset_x
                dy = radius - inset_y
                if dx * dx + dy * dy > radius * radius:
                    continue
            i = (y * ICON_SIZE + x) * 4
            pixels[i : i + 4] = bytes((bg[0], bg[1], bg[2], 255))
    letters = _initials(label)
    # Two glyphs: 5 cols * 4 scale = 20px each, plus 4px gap.
    total_w = 20 + 4 + 20
    start_x = (ICON_SIZE - total_w) // 2
    start_y = (ICON_SIZE - 7 * 4) // 2
    _blit_glyph(pixels, letters[0], start_x, start_y, fg)
    _blit_glyph(pixels, letters[1], start_x + 24, start_y, fg)
    return encode_png_rgba(ICON_SIZE, ICON_SIZE, bytes(pixels))


def stamp_menu_icon_png(client: Any, menu_id: int, name: str) -> str | None:
    """Best-effort write of ``web_icon_data`` after a live-metadata menu create.

    Odoo 19 computes ``web_icon_data`` from ``web_icon`` (a module file path). Writing
    the binary may persist when the field is stored; if the write is ignored, the
    home tile stays the sanitized ``base`` icon. Apps Store uniqueness still comes
    from the module zip ``icon.png``.
    """
    import base64

    png = render_app_icon_png(name)
    payload = base64.b64encode(png).decode("ascii")
    try:
        client.execute_kw(
            "ir.ui.menu",
            "write",
            [[int(menu_id)], {"web_icon_data": payload}],
        )
        return "web_icon_data"
    except Exception:  # noqa: BLE001
        return None


__all__ = [
    "ICON_SIZE",
    "encode_png_rgba",
    "render_app_icon_png",
    "stamp_menu_icon_png",
]
