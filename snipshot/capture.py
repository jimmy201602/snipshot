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


def _run_backend(cmd: list[str], out: Path) -> bool:
    try:
        res = subprocess.run(
            cmd + [str(out)], timeout=15,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return res.returncode == 0 and out.exists() and out.stat().st_size > 0


def _kill_stale_gs_service() -> None:
    """gnome-screenshot is a GApplication: calls delegate to a persistent
    ``--gapplication-service`` process over D-Bus.  When that service hangs
    every later call returns 0 but writes nothing — kill it so the next
    call spawns a fresh one."""
    subprocess.run(["pkill", "-f", "gnome-screenshot --gapplication-service"],
                   capture_output=True, timeout=5)


def capture() -> QImage | None:
    """Capture the whole virtual screen, return a QImage or None."""
    fd, name = tempfile.mkstemp(prefix="snipshot-", suffix=".png")
    os.close(fd)
    out = Path(name)

    try:
        for cmd in _candidate_cmds():
            for attempt in range(2):
                out.unlink(missing_ok=True)
                if _run_backend(cmd, out):
                    img = QImage(str(out))
                    if not img.isNull():
                        return img
                if attempt == 0 and cmd[0] == "gnome-screenshot":
                    _kill_stale_gs_service()   # hung delegate → retry once
    finally:
        out.unlink(missing_ok=True)
    return None
