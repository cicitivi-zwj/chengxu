# -*- coding: utf-8 -*-
"""生成 MSDL 图标（纯标准库：像素绘制 + PNG 编码 + ICO 封装）"""
import os
import struct
import zlib

BLUE_TOP = (34, 113, 235)
BLUE_BOT = (18, 74, 168)
WHITE = (255, 255, 255)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def render(size):
    """返回 RGBA bytearray，size x size"""
    px = bytearray(size * size * 4)
    r = size * 0.22                 # 圆角半径
    for y in range(size):
        for x in range(size):
            # 圆角矩形遮罩
            cx = min(max(x + 0.5, r), size - r)
            cy = min(max(y + 0.5, r), size - r)
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            if dx * dx + dy * dy > r * r:
                continue
            col = lerp(BLUE_TOP, BLUE_BOT, y / max(1, size - 1))
            i = (y * size + x) * 4
            px[i:i + 4] = bytes((col[0], col[1], col[2], 255))
    return px


def rounded_mask(size, r):
    m = [[False] * size for _ in range(size)]
    for y in range(size):
        for x in range(size):
            cx = min(max(x + 0.5, r), size - r)
            cy = min(max(y + 0.5, r), size - r)
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            m[y][x] = dx * dx + dy * dy <= r * r
    return m


def draw_glyph(px, size):
    """白色下行箭头 + 托盘"""
    m = rounded_mask(size, size * 0.22)
    s = size / 100.0

    def put(x, y, a=255):
        if 0 <= x < size and 0 <= y < size and m[int(y)][int(x)]:
            i = (int(y) * size + int(x)) * 4
            old = px[i:i + 3]
            t = a / 255.0
            px[i] = int(old[0] * (1 - t) + WHITE[0] * t)
            px[i + 1] = int(old[1] * (1 - t) + WHITE[1] * t)
            px[i + 2] = int(old[2] * (1 - t) + WHITE[2] * t)
            px[i + 3] = 255

    # 箭头竖杆：x 43..57, y 18..52
    for y in range(int(18 * s), int(52 * s)):
        for x in range(int(43 * s), int(57 * s)):
            put(x, y)
    # 箭头三角：从 (30,50) 到 (70,50) 收到底部 (50,70)
    y0, y1 = 50 * s, 70 * s
    for y in range(int(y0), int(y1)):
        t = (y - y0) / max(1.0, (y1 - y0))
        half = (20 * s) * (1 - t)
        for x in range(int(50 * s - half), int(50 * s + half)):
            put(x, y)
    # 托盘：横条 + 两侧短竖
    for y in range(int(74 * s), int(81 * s)):
        for x in range(int(22 * s), int(78 * s)):
            put(x, y)
    for x in range(int(24 * s), int(31 * s)):
        for y in range(int(64 * s), int(74 * s)):
            put(x, y)
    for x in range(int(69 * s), int(76 * s)):
        for y in range(int(64 * s), int(74 * s)):
            put(x, y)


def png_bytes(px, size):
    raw = bytearray()
    stride = size * 4
    for y in range(size):
        raw.append(0)                      # filter type 0
        raw += px[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def make_ico(path, sizes=(256, 128, 64, 48, 32, 16)):
    entries = []
    for s in sizes:
        px = render(s)
        draw_glyph(px, s)
        entries.append((s, png_bytes(px, s)))

    n = len(entries)
    header = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16 * n
    dir_entries, blobs = b"", b""
    for s, data in entries:
        w = 0 if s >= 256 else s
        h = 0 if s >= 256 else s
        dir_entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    with open(path, "wb") as f:
        f.write(header + dir_entries + blobs)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "msdl.ico")
    make_ico(out)
    print("icon ->", out, os.path.getsize(out), "bytes")
