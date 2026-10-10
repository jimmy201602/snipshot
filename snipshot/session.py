"""Shared state for one screenshot session: the captured image, the
selection, committed annotations, and finish actions."""
from __future__ import annotations

import datetime
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter

from . import clipboard, config
from .shapes import (PALETTE, ShapeStack, TOOL_MOSAIC, TOOL_NONE,
                     make_mosaic_image)


def default_filename() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"snipshot-{ts}.png"


class Session(QObject):
    """One capture+annotation flow across all screens."""

    finished = pyqtSignal()          # all overlays should close
    selectionChanged = pyqtSignal()
    annotationsChanged = pyqtSignal()
    toolChanged = pyqtSignal()
    mosaicReady = pyqtSignal()

    def __init__(self, image: QImage, app_quit_on_done: bool = True):
        super().__init__()
        self.image = image
        self.mosaic: QImage | None = None   # computed off the UI thread
        self._mosaic_started = False
        self.stack = ShapeStack()
        self.sel: QRectF | None = None          # in image px
        self.tool: str = TOOL_NONE
        self.color_hex: str = PALETTE[4]
        self.size_name: str = "M"
        self.overlays: list = []
        self.pinned: list = []                  # keep PinWindows alive
        self.clipboard_persistent = True
        self._quit_on_done = app_quit_on_done
        self._handling = False

    # ---- helpers -------------------------------------------------------
    def has_selection(self) -> bool:
        return self.sel is not None and not self.sel.isNull() \
            and self.sel.width() >= 3 and self.sel.height() >= 3

    def sel_rect(self) -> QRectF:
        return self.sel.normalized() if self.sel else QRectF()

    def set_selection(self, r: QRectF | None) -> None:
        self.sel = r
        self.selectionChanged.emit()

    def set_tool(self, t: str) -> None:
        self.tool = t
        if t == TOOL_MOSAIC:
            self.start_mosaic_worker()  # background; shape appears on ready
        self.toolChanged.emit()

    # ---- mosaic (lazy, computed off the UI thread) ----------------------
    def start_mosaic_worker(self) -> None:
        """Kick off background pixelation; emits mosaicReady when done."""
        if self._mosaic_started:
            return
        self._mosaic_started = True
        self.mosaicReady.connect(self._apply_mosaic)
        # plain python thread: the signal emit is queued to the GUI thread
        threading.Thread(target=self._mosaic_work, daemon=True).start()

    def _apply_mosaic(self) -> None:
        self.mosaic = getattr(self, "_mosaic_result", None) \
            or make_mosaic_image(self.image)
        self.annotationsChanged.emit()

    def _mosaic_work(self) -> None:
        self._mosaic_result = make_mosaic_image(self.image)
        self.mosaicReady.emit()

    def ensure_mosaic(self) -> QImage:
        """Synchronous fallback if the worker hasn't finished yet."""
        res = getattr(self, "_mosaic_result", None)
        if res is None:
            res = make_mosaic_image(self.image)
            self._mosaic_result = res
        self.mosaic = res
        return res

    def render_crop(self) -> QImage | None:
        """Selection + annotations rendered at native image resolution."""
        if not self.has_selection():
            return None
        r = self.sel_rect().toAlignedRect().intersected(self.image.rect())
        if r.isEmpty():
            return None
        out = QImage(r.size(), QImage.Format.Format_ARGB32)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.translate(-r.topLeft())
        p.drawImage(0, 0, self.image)
        for s in self.stack.shapes:
            s.draw(p, self.mosaic or self.ensure_mosaic())
        p.end()
        return out

    # ---- actions -------------------------------------------------------
    def undo(self) -> None:
        if self._handling:
            return
        self.stack.undo()
        self.annotationsChanged.emit()

    def _finish(self, quit_app: bool = True) -> None:
        self.finished.emit()
        app = QGuiApplication.instance()
        if app and not self.clipboard_persistent:
            # keep the (now windowless) process alive to serve clipboard data
            app.setQuitOnLastWindowClosed(False)
        if quit_app and self._quit_on_done and app:
            app.quit()

    def cancel(self) -> None:
        self._finish()

    def confirm(self) -> None:
        """Done: copy to clipboard and close (QQ/WeChat ✓ button)."""
        if self._handling or not self.has_selection():
            return
        self._handling = True
        crop = self.render_crop()
        if crop is not None:
            self.clipboard_persistent = clipboard.copy_image(crop)
            if not self.clipboard_persistent:
                # in-process clipboard: stay alive headless until another
                # app takes over the clipboard, then exit
                self._quit_on_done = False
                self._clip_key = crop.cacheKey()
                cb = QGuiApplication.clipboard()
                if cb is not None:
                    cb.changed.connect(self._clipboard_taken)
        self._finish()

    def _clipboard_taken(self, _mode) -> None:
        cb = QGuiApplication.clipboard()
        if cb is None:
            return
        cur = cb.image()
        if cur.isNull() or cur.cacheKey() != self._clip_key:
            app = QGuiApplication.instance()
            if app:
                app.quit()

    def save(self, parent=None) -> None:
        if self._handling or not self.has_selection():
            return
        crop = self.render_crop()
        if crop is None:
            return
        from PyQt6.QtWidgets import QFileDialog
        cfg = config.load()
        start = str(Path(cfg["save_dir"]) / default_filename())
        path, _ = QFileDialog.getSaveFileName(
            parent, "保存截图", start, "PNG 图片 (*.png);;JPEG 图片 (*.jpg)")
        if path:
            crop.save(path)
            self._finish()

    def pin(self) -> None:
        if self._handling or not self.has_selection():
            return
        crop = self.render_crop()
        if crop is None:
            return
        from .pin import PinWindow
        w = PinWindow(crop)
        w.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.pinned.append(w)
        w.show()
        self._finish(quit_app=False)   # pin window keeps the app alive
