"""Single-instance IPC.

The daemon listens with QLocalServer on an explicit unix-socket path; the
trigger client is a plain unix socket so it doesn't need to start Qt at
all (a hotkey press round-trips in ~5ms).
"""
import os
import socket
from pathlib import Path

SERVER_NAME = "snipshot"


def socket_path() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return Path(base) / "snipshot.sock"


def send_trigger(timeout: float = 1.5) -> bool:
    """Ping a running daemon. Returns True if it acknowledged."""
    path = socket_path()
    if not path.exists():
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(str(path))
        s.sendall(b"TRIGGER\n")
        s.recv(8)
        s.close()
        return True
    except OSError:
        return False


def query(msg: str, timeout: float = 0.5) -> str | None:
    """Send a raw line to the daemon, return its reply (or None)."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(str(socket_path()))
        s.sendall(msg.encode() + b"\n")
        data = s.recv(64).decode().strip()
        s.close()
        return data
    except OSError:
        return None
