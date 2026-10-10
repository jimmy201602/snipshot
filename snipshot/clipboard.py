"""Clipboard helpers.

On Wayland/GNOME there is no clipboard manager: clipboard data dies with
the process that offered it.  ``wl-copy`` / ``xclip`` fork a small serving
process, so the image survives after snipshot exits.  If neither exists we
fall back to the in-process clipboard and report that the app must stay
alive for the data to remain pasteable.
"""
import shutil
import subprocess

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QGuiApplication, QImage


def image_to_png_bytes(img: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.ReadWrite)
    img.save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()
    return data


def copy_image(img: QImage) -> bool:
    """Copy image to system clipboard.

    Returns True if the clipboard survives process exit (external helper
    used), False if the current process must stay alive to serve it.
    """
    png = image_to_png_bytes(img)

    if shutil.which("wl-copy"):
        try:
            res = subprocess.run(
                ["wl-copy", "-t", "image/png"], input=png, timeout=5)
            if res.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass

    if shutil.which("xclip"):
        try:
            res = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "image/png", "-i"],
                input=png, timeout=5)
            if res.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass

    cb = QGuiApplication.clipboard()
    if cb is not None:
        cb.setImage(img)
    return False
