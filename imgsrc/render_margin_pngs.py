#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Render imgsrc/calibre.svg into the PNGs the application ships, with Qt.

imgsrc/generate.py does the same job with rsvg-convert, zopflipng and
inkscape; this needs only a calibre binary, whose Qt is the renderer the
application itself uses:

    calibre-debug -e imgsrc/render_margin_pngs.py

It also copies the SVG to resources/images/calibre.svg.
"""

import os
import shutil

from qt.core import QGuiApplication, QImage, QPainter, Qt, QSvgRenderer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# path relative to the repository -> side in pixels
TARGETS = {
    'icons/calibre.png': 512,
    'resources/images/lt.png': 256,
    'resources/images/library.png': 1024,
    'resources/images/favicon-192.png': 192,
    'resources/images/favicon-512.png': 512,
}


def render(renderer, side):
    img = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(p)
    p.end()
    return img


def main():
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 -- QPainter needs one
    svg = os.path.join(HERE, 'calibre.svg')
    renderer = QSvgRenderer(svg)
    if not renderer.isValid():
        raise SystemExit(f'cannot read {svg}')
    for rel, side in TARGETS.items():
        out = os.path.join(ROOT, *rel.split('/'))
        if not render(renderer, side).save(out, 'PNG'):
            raise SystemExit(f'cannot write {out}')
        print(rel, side)
    shutil.copyfile(svg, os.path.join(ROOT, 'resources', 'images', 'calibre.svg'))
    print('resources/images/calibre.svg')


main()
