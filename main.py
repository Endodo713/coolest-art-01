#!/usr/bin/env python3
"""Sky Leviathan — coolest-art-01 entry.

A colossal bioluminescent jellyfish drifts above a dark sea at night, lit from
within, its tentacles trailing toward a tiny boat with one warm lantern far
below. One huge calm shape that reads even at 300 px across: deep indigo sky,
a cyan-to-violet glowing bell, and a single warm dot of human scale.

Drawn pixel by pixel with the Python 3.13 standard library only (no PIL, no
network): a small software rasteriser plus a hand-rolled PNG encoder. The
program writes $MAKEFUN_OUTPUT_DIR/entry.png (default /output): a 1024x1024
PNG. It is deterministic — a fixed seed, no clock — so two runs write
identical bytes.
"""

import math
import os
import random
import struct
import zlib

W = 1024
H = 1024
HORIZON = 742  # y where the sea meets the sky

# Palette.
SKY_TOP = (7, 11, 36)
SKY_MID = (13, 24, 58)
SKY_HOR = (22, 50, 79)
SEA_TOP = (14, 36, 58)
SEA_BOT = (5, 14, 28)
CYAN = (55, 224, 255)
MAGENTA = (255, 92, 225)
VIOLET = (150, 110, 255)
RIM = (210, 245, 255)
DARK = (4, 7, 14)
LANTERN = (255, 170, 60)

# The pixel buffer: RGB, row-major.
BUF = bytearray(W * H * 3)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def mix(a, b, t):
    return a + (b - a) * t


def mix3(c1, c2, t):
    return (mix(c1[0], c2[0], t), mix(c1[1], c2[1], t), mix(c1[2], c2[2], t))


def blend(x, y, r, g, b, a):
    """Alpha-blend one pixel. a is 0..1."""
    if a <= 0.0 or x < 0 or y < 0 or x >= W or y >= H:
        return
    i = (y * W + x) * 3
    if a >= 1.0:
        BUF[i] = int(r)
        BUF[i + 1] = int(g)
        BUF[i + 2] = int(b)
        return
    ia = 1.0 - a
    BUF[i] = int(r * a + BUF[i] * ia)
    BUF[i + 1] = int(g * a + BUF[i + 1] * ia)
    BUF[i + 2] = int(b * a + BUF[i + 2] * ia)


def add(x, y, r, g, b, a):
    """Additive glow: brightens the pixel toward the colour."""
    if a <= 0.0 or x < 0 or y < 0 or x >= W or y >= H:
        return
    i = (y * W + x) * 3
    BUF[i] = min(255, int(BUF[i] + r * a))
    BUF[i + 1] = min(255, int(BUF[i + 1] + g * a))
    BUF[i + 2] = min(255, int(BUF[i + 2] + b * a))


def row_fill(y, col):
    """Fill a whole row with one colour (base layer, no blending)."""
    row = bytes((int(col[0]), int(col[1]), int(col[2]))) * W
    BUF[y * W * 3:(y + 1) * W * 3] = row


def vgrad(y0, y1, c_top, c_bot):
    """Vertical gradient over rows y0..y1 (inclusive)."""
    n = max(1, y1 - y0)
    for y in range(y0, y1 + 1):
        t = (y - y0) / n
        row_fill(y, mix3(c_top, c_bot, t))


def disc(cx, cy, rad, col, alpha=1.0, feather=1.3, additive=False):
    """Filled disc with a soft (anti-aliased) edge."""
    if rad <= 0:
        return
    r, g, b = col
    x0 = max(0, int(cx - rad - feather - 1))
    x1 = min(W - 1, int(cx + rad + feather + 1))
    y0 = max(0, int(cy - rad - feather - 1))
    y1 = min(H - 1, int(cy + rad + feather + 1))
    rr = rad + feather
    for y in range(y0, y1 + 1):
        dy = y - cy
        for x in range(x0, x1 + 1):
            dx = x - cx
            d = math.sqrt(dx * dx + dy * dy)
            if d > rr:
                continue
            edge = rad - d
            cov = clamp(edge / feather + 0.5, 0.0, 1.0)
            a = alpha * cov
            if additive:
                add(x, y, r, g, b, a)
            else:
                blend(x, y, r, g, b, a)


def soft_ellipse(cx, cy, rx, ry, col, alpha=1.0, feather=1.3, additive=False):
    """Filled ellipse with a soft edge."""
    r, g, b = col
    x0 = max(0, int(cx - rx - feather - 1))
    x1 = min(W - 1, int(cx + rx + feather + 1))
    y0 = max(0, int(cy - ry - feather - 1))
    y1 = min(H - 1, int(cy + ry + feather + 1))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rx
            d = math.sqrt(dx * dx + dy * dy)
            if d > 1.0 + feather / min(rx, ry):
                continue
            edge = (1.0 - d) * min(rx, ry)
            cov = clamp(edge / feather + 0.5, 0.0, 1.0)
            a = alpha * cov
            if additive:
                add(x, y, r, g, b, a)
            else:
                blend(x, y, r, g, b, a)


def radial_glow(cx, cy, rx, ry, col, peak, power=2.2):
    """Additive elliptical glow fading to nothing at the edge."""
    r, g, b = col
    x0 = max(0, int(cx - rx))
    x1 = min(W - 1, int(cx + rx))
    y0 = max(0, int(cy - ry))
    y1 = min(H - 1, int(cy + ry))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rx
            d2 = dx * dx + dy * dy
            if d2 >= 1.0:
                continue
            a = peak * (1.0 - d2) ** power
            add(x, y, r, g, b, a)


def poly(pts, col, alpha=1.0):
    """Scanline-filled polygon (small shapes: boat hull, sail)."""
    r, g, b = col
    ys = [p[1] for p in pts]
    y0, y1 = int(min(ys)), int(max(ys))
    n = len(pts)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x0, ya = pts[i]
            x1, yb = pts[(i + 1) % n]
            if (ya <= y < yb) or (yb <= y < ya):
                t = (y - ya) / (yb - ya)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa, xb = int(xs[k]), int(xs[k + 1])
            for x in range(xa, xb + 1):
                blend(x, y, r, g, b, alpha)


def bezier(p0, p1, p2, p3, n):
    """Sample a cubic bezier curve into n points."""
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1.0 - t
        x = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0]
        y = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]
        pts.append((x, y))
    return pts


def tentacle(x0, y0, length, sway, drift, phase, r0, col, rnd):
    """One flowing tentacle: a smooth tapering tube, stamped as discs that
    always overlap (step ~0.85x the local radius), so it never reads beaded."""
    p0 = (x0, y0)
    p1 = (x0 + sway * 0.7, y0 + length * 0.35)
    p2 = (x0 - sway * 0.9 + drift * 0.5, y0 + length * 0.72)
    p3 = (x0 + drift, y0 + length)
    dense = bezier(p0, p1, p2, p3, 200)
    # A sine wobble on top, growing toward the tip, makes it flow.
    dense = [(x + math.sin(i / 200.0 * math.pi * 1.6 + phase) * sway * 0.35 * (i / 200.0), y)
             for i, (x, y) in enumerate(dense)]
    n = len(dense)
    # Walk the dense samples, stamping a disc each time we have moved about
    # 0.85x the current radius: the tube stays smooth at any taper.
    stamps = []
    acc = 0.0
    prev = dense[0]
    for i in range(1, n):
        t = i / (n - 1)
        rad = r0 * (1.0 - t) ** 0.8 + 1.0
        acc += math.hypot(dense[i][0] - prev[0], dense[i][1] - prev[1])
        if acc >= rad * 0.85:
            stamps.append((dense[i][0], dense[i][1], rad))
            acc = 0.0
            prev = dense[i]
    stamps.append((dense[-1][0], dense[-1][1], 1.2))
    # Soft glow pass first (wide, faint, additive).
    for (x, y, rad) in stamps[::2]:
        disc(x, y, rad * 2.6, col, alpha=0.07, feather=2.0, additive=True)
    # Main pass: the smooth tube.
    for (x, y, rad) in stamps:
        disc(x, y, rad, col, alpha=0.95, feather=1.2)
    # Bright tip.
    disc(dense[-1][0], dense[-1][1], 2.6, (235, 252, 255), alpha=0.9, feather=1.2)


def dome_ramp():
    """Colour ramp for the bell, by normalised distance from its centre (0..1)."""
    stops = [
        (0.00, (216, 242, 255)),
        (0.18, (190, 245, 255)),
        (0.45, (90, 225, 255)),
        (0.68, (80, 170, 255)),
        (0.85, (140, 100, 255)),
        (1.00, (120, 70, 230)),
    ]
    ramp = []
    for i in range(256):
        d = i / 255.0
        for j in range(len(stops) - 1):
            d0, c0 = stops[j]
            d1, c1 = stops[j + 1]
            if d0 <= d <= d1:
                t = 0.0 if d1 == d0 else (d - d0) / (d1 - d0)
                ramp.append(mix3(c0, c1, t))
                break
        else:
            ramp.append(stops[-1][1])
    return ramp


def draw_dome(cx, cy, rx, ry):
    """The glowing bell: radial gradient, ribs radiating from the apex,
    a bright rim ring, and a soft anti-aliased edge."""
    ramp = dome_ramp()
    apex_y = cy - ry
    x0 = max(0, int(cx - rx - 2))
    x1 = min(W - 1, int(cx + rx + 2))
    y0 = max(0, int(cy - ry - 2))
    y1 = min(H - 1, int(cy + ry + 2))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rx
            d2 = dx * dx + dy * dy
            if d2 > 1.02:
                continue
            d = math.sqrt(d2)
            # Anti-aliased edge.
            edge = (1.0 - d) * min(rx, ry)
            cov = clamp(edge / 1.4 + 0.5, 0.0, 1.0)
            if cov <= 0.0:
                continue
            base = ramp[int(d * 255.0)]
            # Ribs radiating from the bell's apex (kept subtle: the bell
            # should read as a jellyfish, not a striped balloon).
            ang = math.atan2(y - apex_y, x - cx)
            rib = 1.0 + 0.06 * math.sin(ang * 14.0) if d < 0.92 else 1.0
            # Brighter toward the top of the bell.
            light = 1.0 + 0.10 * max(0.0, -dy)
            r = base[0] * rib * light
            g = base[1] * rib * light
            b = base[2] * rib * light
            # Bright rim ring near the edge.
            if d > 0.90:
                t = (d - 0.90) / 0.10 * 0.75
                r = mix(r, RIM[0], t)
                g = mix(g, RIM[1], t)
                b = mix(b, RIM[2], t)
            # The rib/top-light multipliers can push a channel past 255.
            r = min(255.0, r)
            g = min(255.0, g)
            b = min(255.0, b)
            blend(x, y, r, g, b, cov)


def draw_scene():
    rnd = random.Random(20261113)

    # --- Sky and sea -------------------------------------------------------
    vgrad(0, 500, SKY_TOP, SKY_MID)
    vgrad(500, HORIZON, SKY_MID, SKY_HOR)
    vgrad(HORIZON, H - 1, SEA_TOP, SEA_BOT)

    # Faint violet and teal nebula glows for depth.
    radial_glow(220, 180, 300, 220, (90, 70, 180), 0.10)
    radial_glow(830, 300, 340, 240, (30, 120, 160), 0.08)

    # Stars.
    for _ in range(130):
        x = rnd.uniform(0, W)
        y = rnd.uniform(0, HORIZON - 24)
        r = rnd.uniform(0.8, 2.1)
        a = rnd.uniform(0.35, 1.0)
        col = (255, 255, 255) if rnd.random() < 0.7 else (170, 230, 255)
        disc(x, y, r, col, alpha=a, feather=1.0)
    # A few bright cross-sparkle stars.
    for _ in range(7):
        x = rnd.uniform(40, W - 40)
        y = rnd.uniform(30, HORIZON - 120)
        s = rnd.uniform(3.0, 5.0)
        for xx in range(int(x - s), int(x + s) + 1):
            blend(xx, int(y), 255, 255, 255, 0.85)
        for yy in range(int(y - s), int(y + s) + 1):
            blend(int(x), yy, 255, 255, 255, 0.85)

    # Horizon glow band where the jellyfish light meets the sea.
    radial_glow(512, HORIZON, 520, 34, CYAN, 0.16)

    # --- Reflection of the jellyfish on the sea -----------------------------
    for y in range(HORIZON + 2, H):
        t = (y - HORIZON) / (H - HORIZON)
        half = 130.0 * (0.55 + 0.45 * t)  # widening toward the viewer
        peak = 0.18 * (1.0 - t)
        for x in range(int(512 - half), int(512 + half) + 1):
            fall = 1.0 - abs(x - 512) / half
            add(x, y, CYAN[0], CYAN[1], CYAN[2], peak * fall * fall)

    # --- The jellyfish ------------------------------------------------------
    # Halo first (behind everything of the creature).
    radial_glow(512, 400, 440, 340, CYAN, 0.20)

    # Thin tentacles, hanging from the bell's lower edge. A wide, shallow
    # bell reads as a jellyfish; a round one reads as a balloon.
    dome_cx, dome_cy, dome_rx, dome_ry = 512.0, 400.0, 315.0, 215.0
    for k in range(12):
        frac = k / 11.0
        ax = 512.0 + (frac - 0.5) * 2.0 * 280.0
        # y on the bell's lower edge at this x.
        nx = (ax - dome_cx) / dome_rx
        ay = dome_cy + dome_ry * math.sqrt(max(0.0, 1.0 - nx * nx)) - 14.0
        length = 190.0 + rnd.uniform(0.0, 150.0)
        sway = rnd.uniform(28.0, 66.0) * (1 if k % 2 == 0 else -1)
        drift = rnd.uniform(-40.0, 40.0)
        col = CYAN
        if k in (3, 9):
            col = MAGENTA
        elif k == 6:
            col = VIOLET
        tentacle(ax, ay, length, sway, drift, rnd.uniform(0, 6.28),
                 rnd.uniform(6.5, 9.5), col, rnd)

    # Thicker oral arms, wavier, violet-pink, in front of the thin ones.
    for k, (ax, length, sway) in enumerate([(430.0, 210.0, 60.0),
                                            (512.0, 240.0, -70.0),
                                            (596.0, 205.0, 55.0)]):
        tentacle(ax, 545.0, length, sway, rnd.uniform(-25, 25),
                 rnd.uniform(0, 6.28), 15.0, (196, 96, 255), rnd)

    # The bell itself, covering the tentacles' tops.
    draw_dome(dome_cx, dome_cy, dome_rx, dome_ry)

    # Frilly skirt: a wavy band hugging the bell's lower edge (a filled
    # polygon, not separate beads, so it reads as one frill).
    upper = []
    lower = []
    for i in range(49):
        ang = math.pi * (0.06 + 0.88 * i / 48.0)
        ux = 512.0 + math.cos(ang) * 311.0 * 0.97
        uy = 400.0 + math.sin(ang) * 211.0 * 0.97
        upper.append((ux, uy))
        fringe = 12.0 + 6.0 * math.sin(i * 2.1)
        lx = 512.0 + math.cos(ang) * 311.0
        ly = 400.0 + math.sin(ang) * 211.0 + fringe
        lower.append((lx, ly))
    poly(upper + lower[::-1], (135, 100, 245), alpha=0.95)
    # A thin pale rim along the frill's lower edge, for definition.
    for (lx, ly) in lower[::2]:
        disc(lx, ly, 1.8, (200, 240, 255), alpha=0.7, feather=1.0)

    # Bright core glow near the top of the bell (kept gentle: the bell's own
    # gradient already carries the light).
    radial_glow(512, 330, 130, 80, (210, 248, 255), 0.16)

    # --- Plankton: tiny glowing dots ----------------------------------------
    for _ in range(90):
        x = rnd.uniform(60, W - 60)
        y = rnd.uniform(120, H - 60)
        r = rnd.uniform(1.0, 2.8)
        a = rnd.uniform(0.5, 1.0)
        col = CYAN if rnd.random() < 0.6 else ((255, 255, 255) if rnd.random() < 0.7 else MAGENTA)
        disc(x, y, r, col, alpha=a, feather=1.0)
        if r > 2.2:
            disc(x, y, r * 3.0, col, alpha=0.12, feather=2.0, additive=True)

    # --- Sea shimmer ---------------------------------------------------------
    for _ in range(16):
        y = int(rnd.uniform(HORIZON + 14, H - 20))
        x = int(rnd.uniform(60, W - 160))
        ln = int(rnd.uniform(22, 95))
        a = rnd.uniform(0.08, 0.22)
        for xx in range(x, x + ln):
            blend(xx, y, 150, 220, 240, a)

    # --- The tiny boat -------------------------------------------------------
    bx, by = 648, 786
    poly([(bx - 26, by), (bx + 26, by), (bx + 18, by + 12), (bx - 18, by + 12)], DARK)
    # Mast and pale sail, lit by the jellyfish.
    for yy in range(by - 30, by + 1):
        blend(bx, yy, 4, 7, 14, 1.0)
        blend(bx + 1, yy, 4, 7, 14, 1.0)
    poly([(bx, by - 30), (bx, by + 2), (bx + 20, by + 2)], (185, 232, 245), alpha=0.92)
    # One tiny figure and one warm lantern.
    disc(bx - 10, by - 5, 2.2, DARK, alpha=1.0, feather=1.0)
    disc(bx, by - 32, 2.6, LANTERN, alpha=1.0, feather=1.2)
    disc(bx, by - 32, 8.0, LANTERN, alpha=0.45, feather=2.0, additive=True)
    # Boat reflection.
    for yy in range(by + 14, by + 30):
        add(bx - 6, yy, CYAN[0], CYAN[1], CYAN[2], 0.10)
        add(bx + 8, yy, CYAN[0], CYAN[1], CYAN[2], 0.10)


def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(path):
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)  # filter: none
        raw += BUF[y * stride:(y + 1) * stride]
    idat = zlib.compress(bytes(raw), 9)
    png = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
           + _chunk(b"IDAT", idat) + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    draw_scene()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    size = write_png(path)
    print("wrote %s (%d bytes, %dx%d)" % (path, size, W, H))


if __name__ == "__main__":
    main()
