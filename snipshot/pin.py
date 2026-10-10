"""Pin-to-screen window: a floating, always-on-top frameless image."""
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import QWidget

BORDER = QColor("#00a2ff")


class PinWindow(QWidget):
    """Shows a cropped image pinned on top of everything.

    - drag with left button to move (works on Wayland via xdg move)
    - Ctrl+wheel or wheel to zoom
    - Esc / double-click closes
    """
    def __init__(self, img: QImage):
        super().__init__()
        self.img = img
        self.zoom = 1.0
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._apply_size()
        self.setToolTip("拖动移动 · 滚轮缩放 · Esc/双击关闭")

    def _apply_size(self) -> None:
        self.resize(int(self.img.width() * self.zoom),
                    int(self.img.height() * self.zoom))

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.drawImage(self.rect(), self.img)
        p.setPen(QPen(BORDER, 2))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton \
                and self.windowHandle() is not None:
            # system move works on Wayland (uses the press serial)
            self.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.close()

    def wheelEvent(self, e: QWheelEvent) -> None:
        delta = e.angleDelta().y()
        if delta == 0:
            return
        factor = 1.1 if delta > 0 else 1 / 1.1
        self.zoom = min(8.0, max(0.05, self.zoom * factor))
        self._apply_size()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)
