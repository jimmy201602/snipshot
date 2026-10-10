"""Annotation shapes. All coordinates are in *image pixel* space so shapes
render identically inside the overlay (scaled) and in the exported crop."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QPainter,
                        QPainterPath, QPainterPathStroker, QPen, QPolygonF)

TOOL_NONE = "none"
TOOL_RECT = "rect"
TOOL_ELLIPSE = "ellipse"
TOOL_ARROW = "arrow"
TOOL_PEN = "pen"
TOOL_MOSAIC = "mosaic"
TOOL_TEXT = "text"

PALETTE = [
    "#e9262c", "#ff7d00", "#ffcd00", "#2fb457",
    "#00a2ff", "#8e44ad", "#000000", "#ffffff",
]
SIZES = {"S": 2.0, "M": 4.0, "L": 7.0}          # pen stroke, image px
TEXT_SIZES = {"S": 16, "M": 24, "L": 40}        # font px, image px
MOSAIC_BLOCK = 12                               # mosaic block, image px


@dataclass
class Shape:
    tool: str
    color: QColor
    width: float                       # stroke width in image px
    rect: QRectF | None = None         # rect/ellipse/arrow/mosaic region
    path: QPainterPath | None = None   # pen / mosaic freehand
    p1: QPointF | None = None          # arrow endpoints
    p2: QPointF | None = None
    text: str = ""                     # text payload
    pos: QPointF | None = None         # text anchor (top-left)
    font_px: int = 24

    def draw(self, p: QPainter, mosaic_img: QImage | None = None) -> None:
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.color, self.width, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        if self.tool == TOOL_RECT and self.rect:
            p.drawRect(self.rect)
        elif self.tool == TOOL_ELLIPSE and self.rect:
            p.drawEllipse(self.rect)
        elif self.tool == TOOL_ARROW and self.p1 is not None and self.p2 is not None:
            _draw_arrow(p, self.p1, self.p2, self.width)
        elif self.tool == TOOL_PEN and self.path:
            p.drawPath(self.path)
        elif self.tool == TOOL_MOSAIC and mosaic_img is not None:
            _draw_mosaic(p, self, mosaic_img)
        elif self.tool == TOOL_TEXT and self.pos is not None:
            f = QFont()
            f.setPixelSize(self.font_px)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QPen(self.color))
            _draw_text(p, self)
        p.restore()


def _draw_arrow(p: QPainter, p1: QPointF, p2: QPointF, width: float) -> None:
    p.drawLine(p1, p2)
    ang = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
    head = 8.0 + width * 3.2
    wing = math.radians(28)
    a1 = ang + math.pi - wing
    a2 = ang + math.pi + wing
    tip1 = QPointF(p2.x() + head * math.cos(a1), p2.y() + head * math.sin(a1))
    tip2 = QPointF(p2.x() + head * math.cos(a2), p2.y() + head * math.sin(a2))
    p.drawPolygon(QPolygonF([tip1, p2, tip2]))


def _draw_mosaic(p: QPainter, shape: Shape, mosaic_img: QImage) -> None:
    if shape.path is not None:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(shape.width, MOSAIC_BLOCK * 1.5))
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        clip = stroker.createStroke(shape.path)
    elif shape.rect is not None:
        clip = QPainterPath()
        clip.addRect(shape.rect)
    else:
        return
    p.setClipPath(clip)
    p.drawImage(0, 0, mosaic_img)


def _draw_text(p: QPainter, shape: Shape) -> None:
    fm = QFontMetricsF(p.font())
    lines = shape.text.split("\n")
    y = shape.pos.y()
    for line in lines:
        p.drawText(QPointF(shape.pos.x(), y + fm.ascent()), line)
        y += fm.height()


def make_mosaic_image(img: QImage, block: int = MOSAIC_BLOCK) -> QImage:
    """Downscale+upscale pixelation of the full screenshot.

    Qt's SmoothTransformation undersamples at ~10x+ ratios, so the box
    average goes through Pillow (a true area filter), then nearest-
    neighbour upscale gives the blocky look.
    """
    from PIL import Image
    rgba = img.convertToFormat(QImage.Format.Format_RGBA8888)
    src = Image.frombytes(
        "RGBA", (rgba.width(), rgba.height()),
        bytes(rgba.constBits().asstring(rgba.sizeInBytes())))
    small = src.resize((max(1, img.width() // block),
                        max(1, img.height() // block)), Image.BOX)
    big = small.resize((img.width(), img.height()), Image.NEAREST)
    out = QImage(big.tobytes(), img.width(), img.height(),
                 QImage.Format.Format_RGBA8888)
    return out.copy()


@dataclass
class ShapeStack:
    """Undo stack of committed shapes."""
    shapes: list[Shape] = field(default_factory=list)

    def push(self, s: Shape) -> None:
        self.shapes.append(s)

    def undo(self) -> Shape | None:
        return self.shapes.pop() if self.shapes else None

    def clear(self) -> None:
        self.shapes.clear()
