"""Tray icon drawn programmatically: blue tile + white crop corners."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def tray_icon() -> QIcon:
    s = 64.0
    pm = QPixmap(int(s), int(s))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # blue tile
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#0a84ff"))
    p.drawRoundedRect(QRectF(2, 2, s - 4, s - 4), 14, 14)

    # white "selection corners" glyph
    p.setPen(QPen(QColor("#ffffff"), 5.5, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    m, c = 15.0, 28.0                    # margin, corner arm length
    for ox, oy, dx, dy in ((m, m, 1, 0), (m, m, 0, 1),
                           (s - m, m, -1, 0), (s - m, m, 0, 1),
                           (m, s - m, 1, 0), (m, s - m, 0, -1),
                           (s - m, s - m, -1, 0), (s - m, s - m, 0, -1)):
        p.drawLine(int(ox), int(oy), int(ox + dx * c), int(oy + dy * c))

    # centre dot (crosshair centre)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawEllipse(QRectF(s / 2 - 3, s / 2 - 3, 6, 6))
    p.end()
    return QIcon(pm)
