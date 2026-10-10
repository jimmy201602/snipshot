"""Programmatically drawn toolbar icons (no resource files needed)."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _pix(name: str, size: int = 22, color: QColor | None = None) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = color or QColor("#e8e8e8")
    pen = QPen(c, 1.8, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = 4.5  # margin
    s = float(size)

    if name == "rect":
        p.drawRect(QRectF(m, m + 2, s - 2 * m, s - 2 * m - 4))
    elif name == "ellipse":
        p.drawEllipse(QRectF(m, m + 1, s - 2 * m, s - 2 * m - 2))
    elif name == "arrow":
        p.drawLine(QPointF(m + 1, s - m - 1), QPointF(s - m - 1, m + 1))
        p.drawLine(QPointF(s - m - 1, m + 1), QPointF(s - m - 1, m + 8))
        p.drawLine(QPointF(s - m - 1, m + 1), QPointF(s - m - 8, m + 1))
    elif name == "pen":
        path = QPainterPath(QPointF(m + 1, s - m - 2))
        path.cubicTo(QPointF(m + 5, m + 2), QPointF(s - m - 5, s - m - 5),
                     QPointF(s - m - 1, m + 4))
        p.drawPath(path)
    elif name == "mosaic":
        step = (s - 2 * m) / 3
        for i in range(3):
            for j in range(3):
                if (i + j) % 2 == 0:
                    p.fillRect(QRectF(m + i * step, m + j * step, step, step), c)
        p.drawRect(QRectF(m, m, s - 2 * m, s - 2 * m))
    elif name == "text":
        f = p.font()
        f.setPixelSize(int(s - 2 * m + 2))
        f.setBold(True)
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "T")
    elif name == "undo":
        path = QPainterPath()
        path.moveTo(QPointF(s - m - 1, s - m - 2))
        path.arcTo(QRectF(m, m - 1, s - 2 * m, s - 2 * m), -35, -230)
        p.drawPath(path)
        p.drawLine(QPointF(m + 1.5, m + 4), QPointF(m + 4.5, m - 2))
        p.drawLine(QPointF(m + 4.5, m - 2), QPointF(m + 8, m + 4.5))
    elif name == "save":
        p.drawLine(QPointF(s / 2, m), QPointF(s / 2, s - m - 5))
        p.drawLine(QPointF(s / 2, s - m - 5), QPointF(m + 2, s - m - 9))
        p.drawLine(QPointF(s / 2, s - m - 5), QPointF(s - m - 2, s - m - 9))
        p.drawLine(QPointF(m, s - m - 2), QPointF(s - m, s - m - 2))
    elif name == "pin":
        p.drawEllipse(QRectF(s / 2 - 3, m, 6, 6))
        p.drawLine(QPointF(s / 2, m + 6), QPointF(s / 2, s - m - 2))
        p.drawLine(QPointF(m + 3, s - m - 2), QPointF(s - m - 3, s - m - 2))
    elif name == "cancel":
        p.drawLine(QPointF(m, m), QPointF(s - m, s - m))
        p.drawLine(QPointF(s - m, m), QPointF(m, s - m))
    elif name == "done":
        p.drawLine(QPointF(m - 1, s / 2 + 1), QPointF(s / 2 - 2, s - m))
        p.drawLine(QPointF(s / 2 - 2, s - m), QPointF(s - m + 1, m))
    p.end()
    return pm


def icon(name: str) -> QIcon:
    return QIcon(_pix(name))
