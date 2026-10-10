"""Top-level window enumeration for hover-snap selection (WeChat-style).

Wayland has no public API for window geometry, so we go through the
AT-SPI accessibility tree (org.gnome desktop + apps that expose a11y).
On GNOME this needs `org.gnome.desktop.interface toolkit-accessibility`
enabled for full coverage — the settings dialog turns it on.

Degrades gracefully: returns [] when pyatspi is missing or the tree
is empty, and the overlay just behaves like free-select only.
"""
import sys
from pathlib import Path

from PyQt6.QtCore import QRectF

MIN_DIM = 100         # ignore thin bars / sub-frames smaller than this


def _ensure_path() -> None:
    """Frozen binaries can't see the system python3-pyatspi/gi."""
    if getattr(sys, "frozen", False):
        p = "/usr/lib/python3/dist-packages"
        if Path(p).exists() and p not in sys.path:
            sys.path.append(p)


def toolkit_accessibility_enabled() -> bool:
    import shutil
    import subprocess
    if not shutil.which("gsettings"):
        return True
    try:
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface",
             "toolkit-accessibility"],
            capture_output=True, text=True, timeout=5).stdout.strip()
        return out.lower() == "true"
    except (OSError, subprocess.TimeoutExpired):
        return True


def enable_toolkit_accessibility() -> None:
    import shutil
    import subprocess
    if shutil.which("gsettings"):
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface",
             "toolkit-accessibility", "true"],
            capture_output=True, timeout=5)


def enum_windows_logical() -> list[tuple[str, QRectF]]:
    """Return [(app_name, rect-in-desktop-logical-px)] for real windows."""
    _ensure_path()
    try:
        import pyatspi
    except Exception:
        return []
    try:
        desktop = pyatspi.Registry.getDesktop(0)
    except Exception:
        return []

    desk_w = desk_h = 0
    out: list[tuple[str, QRectF]] = []
    roles = {getattr(pyatspi, f"ROLE_{r}")
             for r in ("FRAME", "WINDOW", "DIALOG")
             if hasattr(pyatspi, f"ROLE_{r}")}

    for i in range(desktop.childCount):
        app = desktop.getChildAtIndex(i)
        if app is None or app.name in ("gnome-shell",):
            continue
        for j in range(app.childCount):
            w = app.getChildAtIndex(j)
            if w is None:
                continue
            try:
                if w.getRole() not in roles:
                    continue
                ext = w.queryComponent().getExtents(pyatspi.XY_SCREEN)
            except Exception:
                continue
            if ext.width < MIN_DIM or ext.height < MIN_DIM:
                continue
            desk_w = max(desk_w, ext.x + ext.width)
            desk_h = max(desk_h, ext.y + ext.height)
            out.append((app.name or "",
                        QRectF(ext.x, ext.y, ext.width, ext.height)))

    if desk_w and desk_h:
        # drop exact-desktop-size rects (shell background, our own
        # fullscreen overlay, F11 apps) but keep maximized windows
        out = [(n, r) for n, r in out
               if not (r.width() >= desk_w - 4 and r.height() >= desk_h - 4)]
    # de-duplicate identical rects (some apps report shadow frames)
    seen: set = set()
    uniq: list[tuple[str, QRectF]] = []
    for n, r in out:
        key = (round(r.x()), round(r.y()), round(r.width()),
               round(r.height()))
        if key not in seen:
            seen.add(key)
            uniq.append((n, r))
    return uniq
