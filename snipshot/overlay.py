"""Fullscreen selection overlay — the WeChat/QQ-style snipping UI.

One Overlay widget is created per screen.  All selection/annotation data
lives in *image pixel* coordinates inside the shared Session; each overlay
maps between its widget coordinates (logical px) and image px.
"""
from __future__ import annotations

from PyQt6.QtCore import (QEvent, QLineF, QObject, QPoint, QPointF, QRectF,
                         QSizeF, Qt)
from PyQt6.QtGui import (QColor, QFont, QKeyEvent, QMouseEvent, QPainter,
                        QPainterPath, QPen, QPixmap, QScreen)
from PyQt6.QtWidgets import QLineEdit, QWidget

from .magnifier import draw_magnifier, magnifier_rect
from .shapes import (SIZES, TEXT_SIZES, TOOL_ARROW, TOOL_ELLIPSE,
                     TOOL_MOSAIC, TOOL_NONE, TOOL_PEN, TOOL_RECT, TOOL_TEXT,
                     Shape)
from .session import Session
from .toolbar import PaletteBar, Toolbar

DIM = QColor(0, 0, 0, 96)
ACCENT = QColor("#00a2ff")
HANDLE = 8           # handle square, logical px
HIT = 9              # handle hit radius, logical px
STATE_IDLE = "idle"
STATE_DRAG = "drag"          # creating selection
STATE_MOVE = "move"          # moving selection
STATE_RESIZE = "resize"      # resizing selection
STATE_SHAPE = "shape"        # drawing an annotation
STATE_TEXT = "text"          # editing a text annotation


class Overlay(QWidget):
    def __init__(self, session: Session, screen: QScreen, virt_tl: QPoint,
                 scale_x: float, scale_y: float):
        super().__init__()
        self.session = session
        self.screen = screen
        self.sx = scale_x
        self.sy = scale_y
        geo = screen.geometry()
        self.geo = geo
        # this screen's sub-rect inside the full screenshot (image px)
        self.img_rect = QRectF(
            (geo.x() - virt_tl.x()) * scale_x,
            (geo.y() - virt_tl.y()) * scale_y,
            geo.width() * scale_x,
            geo.height() * scale_y,
        )
        self.crop_img = session.image.copy(self.img_rect.toAlignedRect())

        # --- prebaked pixmaps -------------------------------------------
        # Rendered once at the window's buffer resolution so paintEvent is
        # a couple of straight blits instead of a full-screen scale+dim.
        self.buf_dpr = screen.devicePixelRatio() or 1.0
        target = self.crop_img.size() * self.buf_dpr / self.sx
        sized = self.crop_img
        if target != sized.size():
            sized = sized.scaled(target, Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        self.bright_pm = QPixmap.fromImage(sized)
        self.bright_pm.setDevicePixelRatio(self.buf_dpr)
        self.dim_pm = QPixmap(self.bright_pm)
        dp = QPainter(self.dim_pm)
        dp.fillRect(QRectF(0, 0, self.dim_pm.width(), self.dim_pm.height()),
                    DIM)
        dp.end()

        self.state = STATE_IDLE
        self.cursor_pos = QPointF(-1, -1)
        self.press_img = QPointF()          # mouse-down point, image px
        self.press_sel = QRectF()           # selection at press time
        self.handle_idx = -1
        self.cur_shape: Shape | None = None
        self.shape_anchor = QPointF()
        self.last_shape_pt = QPointF()
        self.text_edit: QLineEdit | None = None
        self.text_anchor = QPointF()        # image px
        self._owns_sel = False              # this overlay owns the selection
        self._last_sel = QRectF()           # last painted sel, widget px

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.toolbar = Toolbar(self)
        self.toolbar.ensurePolished()
        self.toolbar.hide()
        self.palette = PaletteBar(self)
        self.palette.ensurePolished()
        self.palette.hide()

        self.toolbar.set_undo_enabled(False)
        self.toolbar.toolPicked.connect(self._on_tool)
        self.toolbar.undoRequested.connect(session.undo)
        self.toolbar.saveRequested.connect(lambda: session.save(self))
        self.toolbar.pinRequested.connect(session.pin)
        self.toolbar.cancelRequested.connect(session.cancel)
        self.toolbar.doneRequested.connect(session.confirm)
        self.palette.colorPicked.connect(self._on_color)
        self.palette.sizePicked.connect(self._on_size)
        session.selectionChanged.connect(self._on_sel_changed)
        session.annotationsChanged.connect(self._on_annots)
        session.mosaicReady.connect(self._on_mosaic)
        session.finished.connect(self.close)

    # ------------------------------------------------------------------
    # coordinate transforms
    def to_img(self, pt: QPointF) -> QPointF:
        return QPointF(pt.x() * self.sx + self.img_rect.x(),
                       pt.y() * self.sy + self.img_rect.y())

    def to_w(self, pt: QPointF) -> QPointF:
        return QPointF((pt.x() - self.img_rect.x()) / self.sx,
                       (pt.y() - self.img_rect.y()) / self.sy)

    def sel_local(self) -> QRectF:
        r = self.session.sel_rect()
        return QRectF(self.to_w(r.topLeft()), self.to_w(r.bottomRight()))

    def _pmrect(self, r: QRectF) -> QRectF:
        """Widget-space rect → pixmap source rect (buffer px)."""
        d = self.buf_dpr
        return QRectF(r.x() * d, r.y() * d, r.width() * d, r.height() * d)

    # ------------------------------------------------------------------
    # dirty-region helpers (partial repaints — a 4K blit per mousemove
    # is what made the first version feel laggy)
    def _mark(self, r: QRectF | None) -> None:
        if r is None or r.isEmpty():
            return
        self.update(r.toAlignedRect().adjusted(-2, -2, 2, 2)
                    .intersected(self.rect()))

    def _sel_dirty(self, r: QRectF | None = None) -> QRectF:
        r = self.sel_local() if r is None else r
        # handles + size label above + arrowheads can stick past the rect
        return r.adjusted(-20, -50, 20, 50)

    def _cursor_rects(self, pt: QPointF) -> list:
        out: list = []
        if pt.x() < 0:
            return out
        # mark the crosshair strips whenever they are (or just were)
        # drawable — otherwise the last lines would stay painted
        if self.state in (STATE_IDLE, STATE_DRAG):
            out.append(QRectF(pt.x() - 1.5, 0, 3, self.height()))
            out.append(QRectF(0, pt.y() - 1.5, self.width(), 3))
        if self._magnifier_visible(pt):
            out.append(magnifier_rect(pt, self.width(), self.height()))
        return out

    def _magnifier_visible(self, pt: QPointF) -> bool:
        return (self.state in (STATE_IDLE, STATE_DRAG)
                and not (self.session.has_selection()
                         and self._inside_sel(pt)))

    # ------------------------------------------------------------------
    # session callbacks
    def _on_tool(self, tool: str) -> None:
        self.session.set_tool(tool)
        self._relayout()

    def _on_color(self, c: QColor) -> None:
        self.session.color_hex = c.name()

    def _on_size(self, name: str) -> None:
        self.session.size_name = name

    def _on_annots(self) -> None:
        self.toolbar.set_undo_enabled(bool(self.session.stack.shapes))
        self._mark(self._sel_dirty())

    def _on_mosaic(self) -> None:
        # background pixelation finished → repaint selection area
        self._mark(self._sel_dirty())

    def _on_sel_changed(self) -> None:
        newr = self.sel_local() if self.session.sel is not None else QRectF()
        self._mark(self._sel_dirty(self._last_sel))
        self._mark(self._sel_dirty(newr))
        self._last_sel = QRectF(newr)
        self._relayout()

    def _relayout(self) -> None:
        has = (self.session.has_selection() and self._owns_sel
               and self.state not in (STATE_DRAG, STATE_MOVE, STATE_RESIZE))
        self.toolbar.setVisible(has)
        self.palette.setVisible(has and self.session.tool != TOOL_NONE)
        if has:
            self._place_bars()

    def _place_bars(self) -> None:
        r = self.sel_local()
        tw = self.toolbar.sizeHint().width()
        th = self.toolbar.sizeHint().height()
        x = min(max(2.0, r.right() - tw), self.width() - tw - 2)
        y = r.bottom() + 8
        if y + th > self.height() - 2:
            y = r.top() - th - 8
        if y < 2:
            y = r.bottom() - th - 8          # inside, bottom-right
        self.toolbar.setGeometry(int(x), int(y), int(tw), int(th))
        if self.session.tool != TOOL_NONE:
            pw = self.palette.sizeHint().width()
            ph = self.palette.sizeHint().height()
            px = min(max(2.0, r.right() - pw), self.width() - pw - 2)
            py = y - ph - 6
            if py < 2:
                py = y + th + 6
            self.palette.setGeometry(int(px), int(py), int(pw), int(ph))

    # ------------------------------------------------------------------
    # hit testing (widget coords)
    def _handles(self) -> list[QPointF]:
        r = self.sel_local()
        x0, y0, x1, y1 = r.left(), r.top(), r.right(), r.bottom()
        cx, cy = r.center().x(), r.center().y()
        return [QPointF(x0, y0), QPointF(cx, y0), QPointF(x1, y0),
                QPointF(x0, cy), QPointF(x1, cy),
                QPointF(x0, y1), QPointF(cx, y1), QPointF(x1, y1)]

    def _handle_at(self, pt: QPointF) -> int:
        for i, hp in enumerate(self._handles()):
            if abs(pt.x() - hp.x()) <= HIT and abs(pt.y() - hp.y()) <= HIT:
                return i
        return -1

    def _inside_sel(self, pt: QPointF) -> bool:
        return self.session.has_selection() and self.sel_local().contains(pt)

    # ------------------------------------------------------------------
    # events
    def mousePressEvent(self, e: QMouseEvent) -> None:
        self.cursor_pos = e.position()
        if e.button() == Qt.MouseButton.RightButton:
            self.session.cancel()
            return
        if e.button() != Qt.MouseButton.LeftButton:
            return

        if self.state == STATE_TEXT:
            self._commit_text()
            return

        pt = e.position()
        img_pt = self.to_img(pt)

        # drawing tool on existing selection
        if (self.session.has_selection() and self._inside_sel(pt)
                and self.session.tool != TOOL_NONE):
            self._begin_shape(img_pt)
            return

        if self.session.has_selection():
            hi = self._handle_at(pt)
            if hi >= 0:
                self.state = STATE_RESIZE
                self.handle_idx = hi
                self.press_img = img_pt
                self.press_sel = self.session.sel_rect()
                return
            if self._inside_sel(pt):
                self.state = STATE_MOVE
                self.press_img = img_pt
                self.press_sel = self.session.sel_rect()
                return

        # otherwise start a new selection
        self.state = STATE_DRAG
        self.press_img = img_pt
        self._owns_sel = True
        for o in self.session.overlays:
            if o is not self:
                o._owns_sel = False
        self.session.set_selection(QRectF(img_pt, img_pt))

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        pt = e.position()
        for r in self._cursor_rects(self.cursor_pos):
            self._mark(r)
        self.cursor_pos = pt
        for r in self._cursor_rects(pt):
            self._mark(r)
        img_pt = self.to_img(pt)

        if self.state == STATE_DRAG:
            self.session.set_selection(QRectF(self.press_img, img_pt))
        elif self.state == STATE_MOVE:
            d = img_pt - self.press_img
            self.session.set_selection(self.press_sel.translated(d))
        elif self.state == STATE_RESIZE:
            self._resize_to(img_pt)
        elif self.state == STATE_SHAPE:
            self._extend_shape(img_pt)
        else:
            self._update_cursor(pt)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self.state == STATE_DRAG:
            if not self.session.has_selection():
                self.session.set_selection(None)   # click without drag
            self.state = STATE_IDLE
        elif self.state in (STATE_MOVE, STATE_RESIZE):
            self.state = STATE_IDLE
        elif self.state == STATE_SHAPE:
            self._commit_shape()
            self.state = STATE_IDLE
        self._update_cursor(e.position())
        self._mark(self._sel_dirty())
        self._relayout()

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        if (e.button() == Qt.MouseButton.LeftButton
                and self.session.has_selection()
                and self._inside_sel(e.position())):
            self.session.confirm()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        key, mods = e.key(), e.modifiers()
        if key == Qt.Key.Key_Escape:
            self.session.cancel()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.session.confirm()
        elif key == Qt.Key.Key_Z and mods & Qt.KeyboardModifier.ControlModifier:
            self.session.undo()
        elif key == Qt.Key.Key_S and mods & Qt.KeyboardModifier.ControlModifier:
            self.session.save(self)
        elif key == Qt.Key.Key_A and mods & Qt.KeyboardModifier.ControlModifier:
            r = self.session.image.rect()
            self._owns_sel = True
            self.session.set_selection(QRectF(r))
            self.state = STATE_IDLE
        else:
            super().keyPressEvent(e)

    # ------------------------------------------------------------------
    # selection editing
    def _resize_to(self, img_pt: QPointF) -> None:
        r = QRectF(self.press_sel)
        i = self.handle_idx
        # edges/corners: 0=tl 1=tm 2=tr 3=ml 4=mr 5=bl 6=bm 7=br
        if i in (0, 3, 5):
            r.setLeft(img_pt.x())
        if i in (2, 4, 7):
            r.setRight(img_pt.x())
        if i in (0, 1, 2):
            r.setTop(img_pt.y())
        if i in (5, 6, 7):
            r.setBottom(img_pt.y())
        self.session.set_selection(r.normalized())

    def _update_cursor(self, pt: QPointF) -> None:
        if self.session.has_selection():
            cursors = {0: Qt.CursorShape.SizeFDiagCursor,
                       1: Qt.CursorShape.SizeVerCursor,
                       2: Qt.CursorShape.SizeBDiagCursor,
                       3: Qt.CursorShape.SizeHorCursor,
                       4: Qt.CursorShape.SizeHorCursor,
                       5: Qt.CursorShape.SizeBDiagCursor,
                       6: Qt.CursorShape.SizeVerCursor,
                       7: Qt.CursorShape.SizeFDiagCursor}
            hi = self._handle_at(pt)
            if hi >= 0:
                self.setCursor(cursors[hi])
                return
            if self._inside_sel(pt):
                self.setCursor(Qt.CursorShape.SizeAllCursor
                               if self.session.tool == TOOL_NONE
                               else Qt.CursorShape.CrossCursor)
                return
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ------------------------------------------------------------------
    # annotations
    def _begin_shape(self, img_pt: QPointF) -> None:
        s = self.session
        color = QColor(s.color_hex)
        if s.tool == TOOL_TEXT:
            self.state = STATE_TEXT
            self.text_anchor = img_pt
            self._open_text_edit(img_pt)
            return
        self.state = STATE_SHAPE
        self.shape_anchor = img_pt
        width = SIZES.get(s.size_name, 4.0)
        if s.tool == TOOL_RECT:
            self.cur_shape = Shape(TOOL_RECT, color, width,
                                   rect=QRectF(img_pt, img_pt))
        elif s.tool == TOOL_ELLIPSE:
            self.cur_shape = Shape(TOOL_ELLIPSE, color, width,
                                   rect=QRectF(img_pt, img_pt))
        elif s.tool == TOOL_ARROW:
            self.cur_shape = Shape(TOOL_ARROW, color, width,
                                   p1=img_pt, p2=img_pt)
        elif s.tool in (TOOL_PEN, TOOL_MOSAIC):
            path = QPainterPath(img_pt)
            self.cur_shape = Shape(s.tool, color,
                                   SIZES.get(s.size_name, 4.0) *
                                   (6.0 if s.tool == TOOL_MOSAIC else 1.0),
                                   path=path)
        self.last_shape_pt = img_pt

    def _extend_shape(self, img_pt: QPointF) -> None:
        c = self.cur_shape
        if c is None:
            return
        pad = c.width * 2 + 40          # stroke + arrowhead, image px
        if c.tool in (TOOL_RECT, TOOL_ELLIPSE):
            new = QRectF(self.shape_anchor, img_pt).normalized()
            old = c.rect or new
            c.rect = new
            area = old.united(new).adjusted(-pad, -pad, pad, pad)
        elif c.tool == TOOL_ARROW:
            old2 = c.p2 or img_pt
            c.p2 = img_pt
            area = QRectF(c.p1, c.p2).normalized().adjusted(-pad, -pad,
                                                           pad, pad)
            area = area.united(QRectF(c.p1, old2).normalized()
                               .adjusted(-pad, -pad, pad, pad))
        elif c.tool in (TOOL_PEN, TOOL_MOSAIC) and c.path is not None:
            c.path.lineTo(img_pt)
            area = QRectF(self.last_shape_pt, img_pt).normalized() \
                .adjusted(-pad, -pad, pad, pad)
        else:
            return
        self.last_shape_pt = img_pt
        # image-px rect → widget rect
        self._mark(QRectF(self.to_w(area.topLeft()),
                          self.to_w(area.bottomRight())))

    def _commit_shape(self) -> None:
        c = self.cur_shape
        if c is not None and not self._degenerate(c):
            self.session.stack.push(c)
            self.session.annotationsChanged.emit()
        self.cur_shape = None

    @staticmethod
    def _degenerate(c: Shape) -> bool:
        if c.tool in (TOOL_RECT, TOOL_ELLIPSE) and c.rect is not None:
            return c.rect.width() < 3 or c.rect.height() < 3
        if c.tool == TOOL_ARROW and c.p1 is not None and c.p2 is not None:
            return (c.p1 - c.p2).manhattanLength() < 6
        if c.tool in (TOOL_PEN, TOOL_MOSAIC) and c.path is not None:
            return c.path.elementCount() < 2
        return False

    # ------------------------------------------------------------------
    # text editing
    def _open_text_edit(self, img_pt: QPointF) -> None:
        pos = self.to_w(img_pt)
        fpx = TEXT_SIZES.get(self.session.size_name, 24)
        logical_px = max(10, int(fpx / self.sx))
        e = QLineEdit(self)
        f = e.font()
        f.setPixelSize(logical_px)
        f.setBold(True)
        e.setFont(f)
        e.setStyleSheet(
            f"QLineEdit {{ background: rgba(0,0,0,120); color: "
            f"{self.session.color_hex}; border: 1px dashed "
            f"rgba(255,255,255,80); padding: 1px 4px; }}")
        h = int(logical_px * 1.5)
        ew = max(120, int(self.width() - pos.x() - 8))
        e.setGeometry(int(pos.x()), int(pos.y()), ew, h)
        e.setPlaceholderText("")
        e.returnPressed.connect(self._commit_text)
        e.installEventFilter(self)
        e.show()
        e.setFocus()
        self.text_edit = e

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:
        if (obj is self.text_edit
                and ev.type() == QEvent.Type.KeyPress
                and ev.key() == Qt.Key.Key_Escape):
            self._commit_text()
            return True
        return super().eventFilter(obj, ev)

    def _commit_text(self) -> None:
        e = self.text_edit
        self.text_edit = None
        if e is None:
            return
        txt = e.text()
        e.hide()
        e.deleteLater()
        self.state = STATE_IDLE
        if txt.strip():
            shape = Shape(TOOL_TEXT, QColor(self.session.color_hex), 0,
                          text=txt, pos=QPointF(self.text_anchor),
                          font_px=TEXT_SIZES.get(self.session.size_name, 24))
            self.session.stack.push(shape)
            self.session.annotationsChanged.emit()
        self._mark(self._sel_dirty())

    # ------------------------------------------------------------------
    # painting
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        w, h = self.width(), self.height()

        # 1+2. prebaked dimmed screenshot (opaque blit, clipped by Qt to
        # the event's update region automatically)
        p.drawPixmap(0, 0, self.dim_pm)

        # restore the bright area inside the selection
        if self.session.has_selection():
            r = self.sel_local()
            p.drawPixmap(r, self.bright_pm, self._pmrect(r))

        # 3. annotations in image-px space (skip those outside the
        # event's dirty rect — cheap cull when there are many)
        dirty_img = QRectF(self.to_img(_e.rect().topLeft()),
                           self.to_img(_e.rect().bottomRight()))
        p.save()
        p.translate(-self.img_rect.topLeft())
        p.scale(1.0 / self.sx, 1.0 / self.sy)
        for s in self.session.stack.shapes:
            if self._shape_bounds(s).intersects(dirty_img):
                s.draw(p, self.session.mosaic)
        if self.cur_shape is not None:
            self.cur_shape.draw(p, self.session.mosaic)
        p.restore()

        # 4. selection chrome
        if self.session.has_selection():
            r = self.sel_local()
            p.setPen(QPen(ACCENT, 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)

            if self._owns_sel and self.state in (STATE_IDLE, STATE_SHAPE):
                p.setPen(QPen(QColor("#333333"), 1))
                p.setBrush(QColor("#ffffff"))
                for hp in self._handles():
                    p.drawRect(QRectF(hp.x() - HANDLE / 2, hp.y() - HANDLE / 2,
                                      HANDLE, HANDLE))
            self._draw_size_label(p, r)
        else:
            self._draw_crosshair(p)

        # 5. magnifier while picking / creating the selection
        if self._magnifier_visible(self.cursor_pos):
            draw_magnifier(p, self.cursor_pos, w, h, self.session.image,
                           self.img_rect.topLeft(), self.sx)

        p.end()

    def _draw_size_label(self, p: QPainter, r: QRectF) -> None:
        img_r = self.session.sel_rect()
        text = f"{int(img_r.width())} × {int(img_r.height())}"
        f = QFont()
        f.setPixelSize(12)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(text) + 16
        hh = 22
        x = r.left()
        y = r.top() - hh - 6
        if y < 2:
            y = r.top() + 6
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 20, 20, 220))
        p.drawRoundedRect(QRectF(x, y, w, hh), 4, 4)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(x, y, w, hh), Qt.AlignmentFlag.AlignCenter, text)

    @staticmethod
    def _shape_bounds(s: Shape) -> QRectF:
        if s.rect is not None:
            r = QRectF(s.rect)
        elif s.path is not None:
            r = s.path.boundingRect()
        elif s.p1 is not None and s.p2 is not None:
            r = QRectF(s.p1, s.p2).normalized()
        elif s.pos is not None:
            r = QRectF(s.pos, QSizeF(800, s.font_px * 2.5))
        else:
            return QRectF()
        pad = max(24.0, s.width * 3.5)
        return r.adjusted(-pad, -pad, pad, pad)

    def _draw_crosshair(self, p: QPainter) -> None:
        if self.cursor_pos.x() < 0:
            return
        p.setPen(QPen(QColor(0, 162, 255, 90), 1))
        p.drawLine(QLineF(self.cursor_pos.x(), 0,
                          self.cursor_pos.x(), self.height()))
        p.drawLine(QLineF(0, self.cursor_pos.y(),
                          self.width(), self.cursor_pos.y()))

    # ------------------------------------------------------------------
    def show_on_screen(self) -> None:
        """Fullscreen this overlay onto its screen."""
        self.winId()  # force native window so we can pick the screen
        if self.windowHandle() is not None:
            self.windowHandle().setScreen(self.screen)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
