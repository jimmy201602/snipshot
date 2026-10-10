"""Fullscreen capture backends.

On Wayland there is no generic screen-grab API for regular apps, so we
delegate to the compositor's own tools:
  * GNOME/Unity : ``gnome-screenshot -f`` (uses the private Shell API)
  * wlroots     : ``grim``
  * KDE Plasma  : ``spectacle -b -n -o``
On X11 we prefer ``maim`` / ``import`` (ImageMagick) / ``scrot``.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PyQt6.QtGui import QImage


def _candidate_cmds() -> list[list[str]]:
    on_wayland = bool(os.environ.get("WAYLAND_DISPLAY")) \
        and os.environ.get("XDG_SESSION_TYPE", "wayland").lower() != "x11"

    if on_wayland:
        specs = [
            ("gnome-screenshot", ["gnome-screenshot", "-f"]),
            ("grim", ["grim"]),
            ("spectacle", ["spectacle", "-b", "-n", "-o"]),
        ]
    else:
        specs = [
            ("maim", ["maim"]),
            ("import", ["import", "-window", "root"]),
            ("scrot", ["scrot"]),
            ("gnome-screenshot", ["gnome-screenshot", "-f"]),
        ]
    return [cmd for exe, cmd in specs if shutil.which(exe)]


def capture() -> QImage | None:
    """Capture the whole virtual screen, return a QImage or None."""
    fd, name = tempfile.mkstemp(prefix="snipshot-", suffix=".png")
    os.close(fd)
    out = Path(name)

    try:
        for cmd in _candidate_cmds():
            out.unlink(missing_ok=True)
            try:
                res = subprocess.run(
                    cmd + [str(out)], timeout=15,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if res.returncode == 0 and out.exists() and out.stat().st_size > 0:
                img = QImage(str(out))
                if not img.isNull():
                    return img
    finally:
        out.unlink(missing_ok=True)
    return None
