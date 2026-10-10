"""High-level flows: run one capture+overlay session (oneshot or daemon)."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtGui import QGuiApplication, QImage
from PyQt6.QtWidgets import QApplication, QMessageBox

from . import capture, config
from .overlay import Overlay
from .session import Session

_active_session: Session | None = None


def virtual_origin() -> tuple[int, int]:
    tl_x = tl_y = 0
    screens = QGuiApplication.screens()
    if screens:
        tl_x = min(s.geometry().x() for s in screens)
        tl_y = min(s.geometry().y() for s in screens)
    return tl_x, tl_y


def show_overlays(image: QImage, quit_on_done: bool = True) -> Session:
    """Create a Session and a fullscreen Overlay per screen."""
    global _active_session
    session = Session(image, app_quit_on_done=quit_on_done)
    _active_session = session

    screens = QGuiApplication.screens()
    tl_x, tl_y = virtual_origin()
    vw = max(s.geometry().right() for s in screens) - tl_x + 1
    vh = max(s.geometry().bottom() for s in screens) - tl_y + 1
    sx = image.width() / vw
    sy = image.height() / vh

    for screen in screens:
        ov = Overlay(session, screen, QPoint(tl_x, tl_y), sx, sy)
        session.overlays.append(ov)
    for ov in session.overlays:
        ov.show_on_screen()
    if session.overlays:
        session.overlays[0].setFocus()
    return session


def run_shot(app: QApplication, quit_on_done: bool = True,
             on_session=None) -> bool:
    """Capture the screen and open the overlay UI.

    on_session: optional callback invoked with the Session once the
    overlays are shown (used by the daemon to track its busy state).
    """
    cfg = config.load()
    delay = int(cfg.get("capture_delay_ms", 0))

    def _go() -> None:
        img = capture.capture()
        if img is None or img.isNull():
            QMessageBox.critical(
                None, "Snipshot",
                "截图失败：没有找到可用的截图后端。\n"
                "Wayland: 需要 gnome-screenshot / grim / spectacle\n"
                "X11: 需要 maim / imagemagick / scrot")
            if quit_on_done:
                app.quit()
            return
        s = show_overlays(img, quit_on_done=quit_on_done)
        if on_session:
            on_session(s)

    if delay > 0:
        QTimer.singleShot(delay, _go)
        return True
    _go()
    return True
