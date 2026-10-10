"""Annotation toolbar + palette bar, styled like QQ/WeChat's dark pill bar."""
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QSizePolicy, QToolButton,
                             QVBoxLayout, QWidget)

from .icons import icon
from .shapes import PALETTE

_BAR_STYLE = """
QWidget#bar {
    background: rgba(24, 26, 30, 235);
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 6px;
}
QToolButton {
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px;
}
QToolButton:hover { background: rgba(255,255,255,36); }
QToolButton:checked { background: rgba(0, 162, 255, 90); }
QToolButton:disabled { opacity: 0.35; }
"""


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color: rgba(255,255,255,45);")
    return f


class PaletteBar(QWidget):
    """Color swatches + stroke-size dots, shown above the main toolbar
    while a drawing tool is active."""
    colorPicked = pyqtSignal(QColor)
    sizePicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(_BAR_STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(5)

        self._color_btns: list[QToolButton] = []
        for hexv in PALETTE:
            b = QToolButton()
            b.setCheckable(True)
            b.setFixedSize(18, 18)
            b.setStyleSheet(
                f"QToolButton {{ background: {hexv}; border: 2px solid "
                f"rgba(255,255,255,60); border-radius: 9px; padding: 0; }}"
                f"QToolButton:checked {{ border: 2px solid #00a2ff; }}")
            b.clicked.connect(lambda _=False, h=hexv: self._pick_color(h))
            lay.addWidget(b)
            self._color_btns.append(b)

        lay.addWidget(_sep())

        self._size_btns: list[QToolButton] = []
        for name, d in (("S", 5), ("M", 9), ("L", 14)):
            b = QToolButton()
            b.setCheckable(True)
            b.setFixedSize(22, 22)
            b.setProperty("sz", name)
            b.setStyleSheet(
                "QToolButton { background: transparent; border: none; }"
                f"QToolButton::indicator {{ width: {d}px; height: {d}px; "
                "border-radius: 3px; background: #aaa; }"
                "QToolButton:checked::indicator { background: #00a2ff; }")
            b.clicked.connect(lambda _=False, n=name: self._pick_size(n))
            lay.addWidget(b)
            self._size_btns.append(b)

        self._hexes = PALETTE
        self.set_current(PALETTE[4], "M")

    def _pick_color(self, hexv: str) -> None:
        for b, h in zip(self._color_btns, self._hexes):
            b.setChecked(h == hexv)
        self.colorPicked.emit(QColor(hexv))

    def _pick_size(self, name: str) -> None:
        for b, n in zip(self._size_btns, ("S", "M", "L")):
            b.setChecked(n == name)
        self.sizePicked.emit(name)

    def set_current(self, hexv: str, size: str) -> None:
        self._pick_color(hexv)
        self._pick_size(size)


class Toolbar(QWidget):
    toolPicked = pyqtSignal(str)     # TOOL_* constant or "none"
    undoRequested = pyqtSignal()
    saveRequested = pyqtSignal()
    pinRequested = pyqtSignal()
    cancelRequested = pyqtSignal()
    doneRequested = pyqtSignal()

    TOOLS = ["rect", "ellipse", "arrow", "pen", "mosaic", "text"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(_BAR_STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 3, 6, 3)
        lay.setSpacing(1)

        self._tool_btns: dict[str, QToolButton] = {}
        for name in self.TOOLS:
            b = self._btn(name, checkable=True)
            b.setToolTip({
                "rect": "矩形", "ellipse": "椭圆", "arrow": "箭头",
                "pen": "画笔", "mosaic": "马赛克", "text": "文字"}[name])
            b.clicked.connect(lambda _=False, n=name: self.pick_tool(n))
            self._tool_btns[name] = b
            lay.addWidget(b)

        lay.addWidget(_sep())

        self.undo_btn = self._btn("undo")
        self.undo_btn.setToolTip("撤销 (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.undoRequested)
        lay.addWidget(self.undo_btn)

        lay.addWidget(_sep())

        pin = self._btn("pin")
        pin.setToolTip("钉在屏幕上")
        pin.clicked.connect(self.pinRequested)
        lay.addWidget(pin)

        save = self._btn("save")
        save.setToolTip("保存 (Ctrl+S)")
        save.clicked.connect(self.saveRequested)
        lay.addWidget(save)

        cancel = self._btn("cancel")
        cancel.setToolTip("取消 (Esc)")
        cancel.clicked.connect(self.cancelRequested)
        lay.addWidget(cancel)

        done = self._btn("done")
        done.setToolTip("完成 (Enter / 双击)")
        done.clicked.connect(self.doneRequested)
        lay.addWidget(done)

        self._active = "none"

    def _btn(self, name: str, checkable: bool = False) -> QToolButton:
        b = QToolButton()
        b.setIcon(icon(name))
        b.setIconSize(QSize(22, 22))
        b.setFixedSize(28, 28)
        b.setCheckable(checkable)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return b

    def pick_tool(self, name: str) -> None:
        if self._active == name:
            name = "none"
        self._set_active(name)
        self.toolPicked.emit(name)

    def _set_active(self, name: str) -> None:
        self._active = name
        for n, b in self._tool_btns.items():
            b.setChecked(n == name)

    def clear_tool(self) -> None:
        self._set_active("none")

    def set_undo_enabled(self, ok: bool) -> None:
        self.undo_btn.setEnabled(ok)
