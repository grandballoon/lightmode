#!/usr/bin/env python3
"""Regenerate the raster favicons from the wobbly-circle geometry in favicon.svg.

favicon.svg is the source of truth for the shape: it is the site header's
background blob, CSS border-radius 44% 56% 49% 51% / 55% 42% 58% 45%. Each
corner of that shape is a quarter ellipse, which is all the rasterizer below
needs. Run from the repo root; no third-party dependencies.
"""

import struct
import zlib

BRAND = (0xFA, 0xCA, 0x47)  # oklch(0.86 0.152 88), the site's yellow
INK = (0x16, 0x15, 0x0F)    # the site's background

# (center_x, center_y, rx, ry, x_is_less_than_center, y_is_less_than_center)
CORNERS = [
    (44, 55, 44, 55, True, True),    # top-left
    (44, 42, 56, 42, False, True),   # top-right
    (51, 42, 49, 58, False, False),  # bottom-right
    (51, 55, 51, 45, True, False),   # bottom-left
]


def inside(x, y):
    """Is (x, y) inside the blob? Coordinates run 0..100, as in the SVG."""
    for cx, cy, rx, ry, x_less, y_less in CORNERS:
        in_x = x < cx if x_less else x > cx
        in_y = y < cy if y_less else y > cy
        if in_x and in_y:
            return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0
    # The corner regions are disjoint and cover every edge, so anything left
    # over is the interior.
    return True


def render(size, inset, background):
    """RGBA rows. inset is the margin per side, as a fraction of the canvas.

    background=None leaves the surround transparent; otherwise the blob is
    composited onto that opaque color.
    """
    samples = 4  # supersample factor, for antialiased edges
    span = size * (1 - 2 * inset)
    origin = size * inset
    rows = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            hits = 0
            for sy in range(samples):
                y = (py + (sy + 0.5) / samples - origin) / span * 100
                for sx in range(samples):
                    x = (px + (sx + 0.5) / samples - origin) / span * 100
                    if 0 <= x <= 100 and 0 <= y <= 100 and inside(x, y):
                        hits += 1
            coverage = hits / (samples * samples)
            if background is None:
                row += bytes(BRAND) + bytes([round(coverage * 255)])
            else:
                row += bytes(round(b + (f - b) * coverage)
                             for f, b in zip(BRAND, background)) + b"\xff"
        rows.append(bytes(row))
    return rows


def encode_png(size, rows):
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    pixels = b"".join(b"\x00" + row for row in rows)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(pixels, 9))
            + chunk(b"IEND", b""))


def encode_ico(images):
    """images: [(size, png_bytes)]. ICO files may embed PNGs directly."""
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0,
                               1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return struct.pack("<HHH", 0, 1, len(images)) + entries + blobs


def main():
    # Tab icons stay transparent so the blob reads on light and dark chrome.
    ico_sizes = [16, 32, 48]
    images = [(s, encode_png(s, render(s, 0.05, None))) for s in ico_sizes]
    with open("favicon.ico", "wb") as f:
        f.write(encode_ico(images))

    # iOS home screens ignore transparency, so paint the site's ground behind.
    with open("apple-touch-icon.png", "wb") as f:
        f.write(encode_png(180, render(180, 0.16, INK)))

    print("wrote favicon.ico (%s) and apple-touch-icon.png"
          % ", ".join(f"{s}x{s}" for s in ico_sizes))


if __name__ == "__main__":
    main()
