"""Offscreen widget tests for the selection overlay state machine,
annotation shapes, cropping and clipboard glue."""
import pytest
from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage
from PyQt6.QtTest import QTest

from snipshot import shapes
from snipshot.overlay import Overlay
from snipshot.session import Session


def _make(scale=1.0):
    """Build a session whose image exactly covers the primary screen."""
    screen = QGuiApplication.primaryScreen()
    geo = screen.geometry()
    img = QImage(int(geo.width() * scale), int(geo.height() * scale),
                 QImage.Format.Format_ARGB32)
    img.fill(QColor("#305070"))
    sess = Session(img, app_quit_on_done=False)
    ov = Overlay(sess, screen, QPoint(geo.x(), geo.y()), scale, scale)
    sess.overlays.append(ov)
    ov.show()
    return sess, ov


def _drag(w, a, b, steps=5):
    QTest.mousePress(w, Qt.MouseButton.LeftButton, pos=a)
    for i in range(1, steps + 1):
        p = QPointF(a.x() + (b.x() - a.x()) * i / steps,
                    a.y() + (b.y() - a.y()) * i / steps)
        QTest.mouseMove(w, p.toPoint())
    QTest.mouseRelease(w, Qt.MouseButton.LeftButton, pos=b)


# ---------------------------------------------------------------- sel ---
def test_drag_creates_selection(qapp):
    sess, ov = _make()
    _drag(ov, QPoint(100, 100), QPoint(400, 300))
    r = sess.sel_rect()
    assert r.width() == pytest.approx(300, abs=2)
    assert r.height() == pytest.approx(200, abs=2)
    assert r.x() == pytest.approx(100, abs=2)
    assert r.y() == pytest.approx(100, abs=2)


def test_tiny_click_clears_selection(qapp):
    sess, ov = _make()
    _drag(ov, QPoint(100, 100), QPoint(400, 300))
    assert sess.has_selection()
    QTest.mouseClick(ov, Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
    assert not sess.has_selection()


def test_move_selection(qapp):
    sess, ov = _make()
    _drag(ov, QPoint(100, 100), QPoint(300, 200))
    _drag(ov, QPoint(150, 150), QPoint(180, 170))
    r = sess.sel_rect()
    assert r.x() == pytest.approx(130, abs=3)
    assert r.y() == pytest.approx(120, abs=3)


def test_resize_via_handle(qapp):
    sess, ov = _make()
    _drag(ov, QPoint(100, 100), QPoint(300, 200))
    # bottom-right handle at sel bottom-right
    _drag(ov, QPoint(300, 200), QPoint(350, 260))
    r = sess.sel_rect()
    assert r.width() == pytest.approx(250, abs=3)
    assert r.height() == pytest.approx(160, abs=3)


def test_select_all(qapp):
    sess, ov = _make()
    QTest.keyClick(ov, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    r = sess.sel_rect()
    assert r.width() == pytest.approx(sess.image.width(), abs=2)


# ------------------------------------------------------------ shapes ----
def test_rect_shape_and_undo(qapp):
    sess, ov = _make()
    _drag(ov, QPoint(100, 100), QPoint(400, 300))
    sess.set_tool(shapes.TOOL_RECT)
    _drag(ov, QPoint(150, 150), QPoint(250, 220))
    assert len(sess.stack.shapes) == 1
    assert sess.stack.shapes[0].tool == shapes.TOOL_RECT
    sess.undo()
    assert len(sess.stack.shapes) == 0


def test_arrow_shape(qapp):
    sess, ov = _make()
    _drag(ov, QPoint(100, 100), QPoint(400, 300))
    sess.set_tool(shapes.TOOL_ARROW)
    _drag(ov, QPoint(150, 250), QPoint(300, 140))
    s = sess.stack.shapes[0]
    assert s.tool == shapes.TOOL_ARROW
    assert s.p1.x() == pytest.approx(150, abs=2)
    assert s.p2.y() == pytest.approx(140, abs=2)


def test_pen_shape(qapp):
    sess, ov = _make()
    _drag(ov, QPoint(100, 100), QPoint(400, 300))
    sess.set_tool(shapes.TOOL_PEN)
    _drag(ov, QPoint(150, 150), QPoint(300, 250), steps=8)
    s = sess.stack.shapes[0]
    assert s.tool == shapes.TOOL_PEN
    assert s.path.elementCount() > 5


def test_text_shape(qapp):
    sess, ov = _make()
    _drag(ov, QPoint(100, 100), QPoint(400, 300))
    sess.set_tool(shapes.TOOL_TEXT)
    QTest.mouseClick(ov, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    assert ov.text_edit is not None
    ov.text_edit.setText("hello")
    ov._commit_text()
    s = sess.stack.shapes[0]
    assert s.tool == shapes.TOOL_TEXT
    assert s.text == "hello"


# ------------------------------------------------------------ output ----
def test_render_crop(qapp):
    sess, ov = _make()
    _drag(ov, QPoint(100, 100), QPoint(300, 240))
    sess.set_tool(shapes.TOOL_RECT)
    _drag(ov, QPoint(120, 120), QPoint(180, 160))
    crop = sess.render_crop()
    assert crop is not None
    assert crop.width() == pytest.approx(200, abs=3)
    assert crop.height() == pytest.approx(140, abs=3)
    # border pixel of the drawn rect should be the default accent (#00a2ff)
    px = crop.pixelColor(20, 20)
    assert px.blue() > 200 and 100 < px.green() < 210 and px.red() < 60


def test_mosaic_blurs(qapp):
    screen = QGuiApplication.primaryScreen()
    geo = screen.geometry()
    img = QImage(geo.width(), geo.height(), QImage.Format.Format_ARGB32)
    # fine checkerboard: any real blur must average it to grey
    for x in range(img.width()):
        for y in range(img.height()):
            img.setPixelColor(x, y,
                              QColor("#000000") if (x + y) % 2
                              else QColor("#ffffff"))
    sess = Session(img, app_quit_on_done=False)
    ov = Overlay(sess, screen, QPoint(geo.x(), geo.y()), 1.0, 1.0)
    sess.overlays.append(ov)
    ov.show()

    _drag(ov, QPoint(100, 100), QPoint(500, 400))
    sess.set_tool(shapes.TOOL_MOSAIC)
    _drag(ov, QPoint(150, 200), QPoint(350, 200), steps=6)
    assert len(sess.stack.shapes) == 1
    crop = sess.render_crop()
    # a point on the mosaic stroke should be ~grey, not pure black/white
    c = crop.pixelColor(150, 100)   # img (250, 200) on the stroke
    assert 60 < c.red() < 200 and abs(c.red() - c.green()) < 20


def test_magnifier_and_dims_do_not_crash(qapp):
    """paint the overlay in every state to catch paint-time exceptions."""
    sess, ov = _make()
    ov.grab()                                    # idle + crosshair
    _drag(ov, QPoint(100, 100), QPoint(400, 300))
    ov.grab()                                    # selection + chrome
    sess.set_tool(shapes.TOOL_RECT)
    _drag(ov, QPoint(120, 120), QPoint(200, 200))
    ov.grab()                                    # shape + toolbar state
    sess.set_tool(shapes.TOOL_TEXT)
    QTest.mouseClick(ov, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    ov.grab()                                    # text editing
    ov._commit_text()
    ov.grab()


# ------------------------------------------------- window snap (AT-SPI) --
def _inject_windows(sess, ov, rects):
    """Feed fake desktop-logical window rects as if the worker found them."""
    sess.windows = [("app", r) for r in rects]
    ov._on_windows()


def test_window_hover_and_snap(qapp):
    sess, ov = _make()
    win = QRectF(200, 150, 500, 350)
    _inject_windows(sess, ov, [win])
    QTest.mouseMove(ov, QPoint(300, 250))
    assert ov.hover_img is not None
    assert ov.hover_img == win
    # a plain click (no drag) snaps the selection to the window
    QTest.mouseClick(ov, Qt.MouseButton.LeftButton, pos=QPoint(300, 250))
    assert sess.has_selection()
    r = sess.sel_rect()
    assert r == win


def test_window_snap_prefers_smallest(qapp):
    sess, ov = _make()
    big = QRectF(50, 50, 800, 600)
    small = QRectF(200, 200, 300, 200)
    _inject_windows(sess, ov, [big, small])
    QTest.mouseMove(ov, QPoint(300, 280))
    assert ov.hover_img == small          # tightest containing window wins


def test_window_hover_outside_is_none(qapp):
    sess, ov = _make()
    _inject_windows(sess, ov, [QRectF(200, 150, 300, 200)])
    QTest.mouseMove(ov, QPoint(30, 30))   # outside every window
    assert ov.hover_img is None


def test_window_snap_replaces_selection(qapp):
    sess, ov = _make()
    win = QRectF(400, 300, 400, 300)
    _inject_windows(sess, ov, [win])
    _drag(ov, QPoint(50, 50), QPoint(200, 200))
    assert sess.has_selection()
    QTest.mouseMove(ov, QPoint(500, 400)) # hover outside current sel
    assert ov.hover_img == win
    QTest.mouseClick(ov, Qt.MouseButton.LeftButton, pos=QPoint(500, 400))
    r = sess.sel_rect()
    assert r == win


def test_drag_still_free_selects_over_window(qapp):
    """Dragging (not clicking) inside a detected window must free-select."""
    sess, ov = _make()
    _inject_windows(sess, ov, [QRectF(0, 0, 900, 700)])
    _drag(ov, QPoint(100, 100), QPoint(350, 300))
    r = sess.sel_rect()
    assert r.width() == pytest.approx(250, abs=3)
    assert r.x() == pytest.approx(100, abs=3)


def test_no_windows_falls_back_to_free_select(qapp):
    """Empty window list (pyatspi missing) → click still clears as before."""
    sess, ov = _make()
    _inject_windows(sess, ov, [])
    QTest.mouseMove(ov, QPoint(300, 300))
    assert ov.hover_img is None
    QTest.mouseClick(ov, Qt.MouseButton.LeftButton, pos=QPoint(300, 300))
    assert not sess.has_selection()


# ------------------------------------------------------------ keys ------
def test_esc_cancels(qapp):
    sess, ov = _make()
    hit = []
    sess.finished.connect(lambda: hit.append(1))
    QTest.keyClick(ov, Qt.Key.Key_Escape)
    assert hit == [1]


def test_undo_shortcut(qapp):
    sess, ov = _make()
    _drag(ov, QPoint(100, 100), QPoint(400, 300))
    sess.set_tool(shapes.TOOL_RECT)
    _drag(ov, QPoint(150, 150), QPoint(250, 220))
    assert len(sess.stack.shapes) == 1
    QTest.keyClick(ov, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert len(sess.stack.shapes) == 0


# ------------------------------------------------------------ prefs -----
def test_color_size_persist(qapp):
    from snipshot import config
    sess, ov = _make()
    sess.set_color("#e9262c")
    sess.set_size("L")
    cfg = config.load()
    assert cfg["last_color"] == "#e9262c"
    assert cfg["last_size"] == "L"
    # a new session must pick up the persisted prefs
    img2 = QImage(64, 64, QImage.Format.Format_ARGB32)
    sess2 = Session(img2, app_quit_on_done=False)
    assert sess2.color_hex == "#e9262c"
    assert sess2.size_name == "L"


def test_settings_dialog_roundtrip(qapp, monkeypatch):
    from snipshot import config, install
    from snipshot.settings import SettingsDialog
    # stub out real gsettings/autostart side effects
    monkeypatch.setattr(install, "install_hotkey", lambda: True)
    monkeypatch.setattr(install, "install_autostart", lambda: None)
    monkeypatch.setattr(install, "remove_autostart", lambda: None)
    dlg = SettingsDialog()
    dlg.hk_combo.setCurrentIndex(1)           # Alt+A preset
    dlg.dir_edit.setText("/tmp/shots")
    dlg.autostart_chk.setChecked(False)
    dlg.oneshot_chk.setChecked(True)
    dlg.accept()
    cfg = config.load()
    assert cfg["hotkey"] == "<Alt>a"
    assert cfg["save_dir"] == "/tmp/shots"
    assert cfg["oneshot_fallback"] is True
    assert cfg["autostart"] is False
