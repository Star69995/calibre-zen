#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Draw the website's link-preview cards, site/img/og-en.png and og-he.png
(1200x630): the mark from imgsrc/calibre.svg, the name and the tagline, on
paper. Keep the text in step with og:title and og:description in site/.

    QT_QPA_PLATFORM=offscreen calibre-debug -e scripts/og_image.py
"""

import importlib.util
import os

from qt.core import QByteArray, QColor, QFont, QGuiApplication, QImage, QPainter, QRectF, QSvgRenderer, Qt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The mark's drawing and colours, from the one place they are declared.
_spec = importlib.util.spec_from_file_location('margin_mark', os.path.join(ROOT, 'imgsrc', 'margin_mark.py'))
mark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mark)
W, H = 1200, 630
MUTED = '#6b645e'
CARDS = {
    'en': ('calibre, simple and intuitive.', 'Every feature kept. Free and open source.', Qt.LayoutDirection.LeftToRight),
    'he': ('calibre, פשוט ואינטואיטיבי.', 'בלי לוותר על אף יכולת. חינמי וקוד פתוח.', Qt.LayoutDirection.RightToLeft),
}


def card(lang):
    tagline, sub, direction = CARDS[lang]
    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(mark.PAPER))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    rtl = direction == Qt.LayoutDirection.RightToLeft
    box = QRectF(W - 100 - 340 if rtl else 100, (H - 340) / 2, 340, 340)
    QSvgRenderer(QByteArray(mark.mark_svg(tile=False).encode('utf-8'))).render(p, box)
    text = QRectF(100 if rtl else 500, 150, 600, 330)
    align = (Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignAbsolute

    name = QFont('Georgia', 1)
    name.setPixelSize(64)
    name.setBold(True)
    p.setFont(name)
    p.setPen(QColor(mark.INK))
    # The wordmark is Latin either way, drawn left to right in two colours.
    zen = 'Calibre Zen '
    zen_w = p.fontMetrics().horizontalAdvance(zen)
    margin_w = p.fontMetrics().horizontalAdvance('Margin')
    x = text.right() - zen_w - margin_w if rtl else text.left()
    p.drawText(QRectF(x, text.top(), zen_w + 4, 80), Qt.AlignmentFlag.AlignLeft, zen)
    p.setPen(QColor(mark.TERRACOTTA))
    p.drawText(QRectF(x + zen_w, text.top(), margin_w + 4, 80), Qt.AlignmentFlag.AlignLeft, 'Margin')

    # Hebrew lines are laid out right to left, so their punctuation lands at the end.
    p.setLayoutDirection(direction)
    body = QFont('Segoe UI', 1)
    body.setPixelSize(40)
    p.setFont(body)
    p.setPen(QColor(mark.INK))
    p.drawText(QRectF(text.left(), text.top() + 110, text.width(), 60), align, tagline)
    body.setPixelSize(30)
    p.setFont(body)
    p.setPen(QColor(MUTED))
    p.drawText(QRectF(text.left(), text.top() + 175, text.width(), 50), align, sub)
    p.drawText(QRectF(text.left(), text.top() + 250, text.width(), 50), align, 'star69995.github.io/calibre-zen-margin')
    p.end()
    out = os.path.join(ROOT, 'site', 'img', f'og-{lang}.png')
    img.save(out)
    print(out)


app = QGuiApplication.instance() or QGuiApplication([])
for lang in CARDS:
    card(lang)
