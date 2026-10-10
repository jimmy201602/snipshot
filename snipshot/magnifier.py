"""Pixel magnifier shown next to the cursor while picking a region."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter

CELL = 10          # logical px per source pixel
NCELLS = 11        # source pixels across
PAD = 14           # distance from cursor
INFO_H = 40        # info strip height
BOX_W = NCELLS * CELL
BOX_H = NCELLS * CELL + INFO_H


def magnifier_rect(cursor: QPointF, widget_w: int, widget_h: int) -> QRectF:
    """Widget-space rect occupied by the magnifier (for dirty tracking)."""
    x = cursor.x() + PAD
    y = cursor.y() + PAD
    if x + BOX_W > widget_w - 2:
        x = cursor.x() - PAD - BOX_W
    if y + BOX_H > widget_h - 2:
        y = cursor.y() - PAD - BOX_H
    return QRectF(max(2.0, x), max(2.0, y), BOX_W, BOX_H)


def draw_magnifier(p: QPainter, cursor: QPointF, widget_w: int, widget_h: int,
                   image: QImage, img_origin: QPointF, scale: float) -> None:
    """cursor: widget coords. img_origin: image-px coord of widget (0,0).
    scale: image px per logical px."""
    img_pt = img_origin + cursor * scale
    r = magnifier_rect(cursor, widget_w, widget_h)
    x, y, box_w, box_h = r.x(), r.y(), r.width(), r.height()

    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    half = NCELLS // 2
    src = QRectF(img_pt.x() - half, img_pt.y() - half, NCELLS, NCELLS)
    # draw zoomed pixels
    p.drawImage(QRectF(x, y, box_w, NCELLS * CELL), image, src)

    # center-pixel highlight
    cx = x + half * CELL
    cy = y + half * CELL
    p.setPen(QColor("#00a2ff"))
    p.drawRect(QRectF(cx, cy, CELL, CELL))

    # frame + info strip
    p.setPen(QColor(255, 255, 255, 140))
    p.drawRect(QRectF(x - .5, y - .5, box_w + 1, box_h + 1))
    p.fillRect(QRectF(x, y + NCELLS * CELL, box_w, INFO_H),
               QColor(20, 20, 20, 235))

    ix, iy = int(img_pt.x()), int(img_pt.y())
    if 0 <= ix < image.width() and 0 <= iy < image.height():
        col = image.pixelColor(ix, iy)
        hexv = col.name().upper()
    else:
        hexv = "------"
    f = QFont()
    f.setPixelSize(11)
    p.setFont(f)
    p.setPen(QColor("#e8e8e8"))
    p.drawText(QRectF(x + 6, y + NCELLS * CELL, box_w, INFO_H / 2),
               Qt.AlignmentFlag.AlignVCenter, f"{hexv}")
    p.setPen(QColor("#9aa0a6"))
    p.drawText(QRectF(x + 6, y + NCELLS * CELL + INFO_H / 2, box_w, INFO_H / 2),
               Qt.AlignmentFlag.AlignVCenter, f"({ix}, {iy})")
    p.restore()
