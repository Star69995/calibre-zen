#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Draw the Calibre Zen Margin mark into imgsrc/calibre.svg.

The mark is an ensō in black ink with a bookmark of terracotta inside it,
both painted bristle by bristle: every stroke is a bundle of thin lines that
follow one centre path, spread across the brush's width and broken off where
the brush runs dry. It was designed as a canvas drawing; this is the same
algorithm and the same seed, writing SVG paths instead, so the icon is a
vector that every platform's renderer (Qt here) can scale.

Plain Python, no dependencies:

    python imgsrc/margin_mark.py            # writes imgsrc/calibre.svg
    python imgsrc/margin_mark.py <out.svg>

imgsrc/calibre.svg is the one source every icon is derived from (BUILDING.md,
"application icon"); after changing it, re-render the PNGs with
imgsrc/render_margin_pngs.py.
"""

import math
import os
import sys

SEED = 7
# The size the mark was designed at. Bristle count and the jitter of each
# bristle are in these units, so the mark is drawn here and scaled, never
# redrawn at the target size, or a bigger icon would be a different picture.
DESIGN = 150
INK = '#1c1917'
TERRACOTTA = '#b4532a'
PAPER = '#fafaf9'
INK_ALPHA = 0.92
# A full-bleed paper tile with Apple's corner (185.4 on a side of 824), so the
# macOS renderer's rounded mask (packaging/macos/render_icon.py) is the same
# shape and Windows gets a rounded tile rather than a hard square.
CANVAS = 1024
TILE_RADIUS = CANVAS * 185.4 / 824
# How much of the tile the mark's design square takes.
MARK_SCALE = 0.94


def rng(seed):
    "mulberry32, bit for bit as in JavaScript."
    a = seed & 0xFFFFFFFF

    def imul(x, y):
        return (x * y) & 0xFFFFFFFF

    def nxt():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = imul(a ^ (a >> 15), 1 | a)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return nxt


def js_round(x):
    return math.floor(x + 0.5)


def bezier(a, m, b):
    def at(u):
        v = 1 - u
        return (v * v * a[0] + 2 * v * u * m[0] + u * u * b[0], v * v * a[1] + 2 * v * u * m[1] + u * u * b[1])

    return at


def brush(r, path, width, steps, spread, dry):
    "One stroke: a list of (stroke width, [polyline, ...]) per bristle."
    n_bristles = max(8, js_round(width * 2.4))
    line = max(0.7, width / n_bristles * 2)
    out = []
    for i in range(n_bristles):
        t = i / (n_bristles - 1) - 0.5
        knots = [r() for _ in range(60)]
        lines, cur = [], None
        for s in range(steps + 1):
            u = s / steps
            p, q = path(u), path(u + 0.004)
            dx, dy = q[0] - p[0], q[1] - p[1]
            length = math.hypot(dx, dy) or 1
            f = u * 58
            j = int(f)
            noise = knots[j] + (knots[j + 1] - knots[j]) * (f - j)
            off = t * width * spread(u) + (noise - 0.5) * 1.2
            if noise > dry(u, abs(t)):
                pt = (p[0] - dy / length * off, p[1] + dx / length * off)
                if cur is None:
                    cur = [pt]
                    lines.append(cur)
                else:
                    cur.append(pt)
            else:
                cur = None
        out.append((line, [pl for pl in lines if len(pl) > 1]))
    return out


def enso_strokes(a=DESIGN, seed=SEED):
    r = rng(seed)
    c, R, W = a / 2, a * 0.31, a * 0.17
    p1, p2 = r() * 6, r() * 6
    th0 = 2.75 + r() * 0.3

    def ring(u):
        th = th0 + u * math.pi * 2.1
        rad = R * (1 + 0.035 * math.sin(th + p1) + 0.02 * math.sin(2 * th + p2)) - u * W * 0.25
        return (c + rad * math.cos(th), c + rad * math.sin(th))

    enso = brush(
        r, ring, W, 300,
        lambda u: (1.1 - 0.4 * u + 0.18 * math.sin(u * 9 + p1)) * (0.55 + u / 0.04 * 0.45 if u < 0.04 else 1),
        lambda u, t: -1 + 1.45 * u * u + t * 1.5 * u,
    )
    r2 = rng(seed + 99)
    ribbon = brush(
        r2, bezier((c + 0.01 * a, c - 0.2 * a), (c - 0.02 * a, c), (c + 0.005 * a, c + 0.19 * a)), 0.13 * a, 120,
        lambda u: (0.7 + u / 0.08 * 0.3 if u < 0.08 else 1) * (1 - 0.1 * u),
        lambda u, t: -1 + 1.1 * u * u + t * u + ((1 - 2 * t) * (u - 0.55) * 10 if u > 0.55 else 0),
    )
    return enso, ribbon


def paths(stroke, colour):
    out = []
    for width, lines in stroke:
        if not lines:
            continue
        d = ''.join('M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in pl) for pl in lines)
        out.append(f'<path stroke="{colour}" stroke-width="{width:.2f}" d="{d}"/>')
    return out


def mark_svg(tile=True):
    enso, ribbon = enso_strokes()
    body = '\n'.join(paths(enso, INK) + paths(ribbon, TERRACOTTA))
    scale = CANVAS / DESIGN * MARK_SCALE
    shift = CANVAS * (1 - MARK_SCALE) / 2
    back = f'<rect width="{CANVAS}" height="{CANVAS}" rx="{TILE_RADIUS:.1f}" fill="{PAPER}"/>\n' if tile else ''
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS} {CANVAS}" width="512" height="512">\n'
        '<!-- Calibre Zen Margin: generated by imgsrc/margin_mark.py, do not edit by hand -->\n'
        f'{back}'
        f'<g transform="translate({shift:g} {shift:g}) scale({scale:.5f})" fill="none" stroke-linecap="round" '
        f'stroke-linejoin="round" stroke-opacity="{INK_ALPHA}">\n{body}\n</g>\n</svg>\n'
    )


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'calibre.svg')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(mark_svg())
    print(out, os.path.getsize(out), 'bytes')


if __name__ == '__main__':
    main()
