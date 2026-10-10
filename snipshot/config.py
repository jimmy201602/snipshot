"""User configuration, stored in ~/.config/snipshot/config.json."""
import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "snipshot"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    # GNOME keybinding notation, e.g. "<Ctrl><Alt>a" (QQ style) or "<Alt>a" (WeChat)
    "hotkey": "<Ctrl><Alt>a",
    # Where "save" puts screenshots by default
    "save_dir": str(Path.home() / "Pictures"),
    # "daemon":  resident process shows the overlay instantly (WeChat-like,
    #            verified to receive keyboard focus on GNOME Wayland)
    # "oneshot": every hotkey press runs capture+overlay in a fresh process
    "mode": "daemon",
    # milliseconds between trigger and capture (lets transient UI settle)
    "capture_delay_ms": 120,
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text()))
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")


def runtime_dir() -> Path:
    """Directory for sockets/temp capture files."""
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    d = Path(base) / "snipshot"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path("/tmp") / f"snipshot-{os.getuid()}"
        d.mkdir(parents=True, exist_ok=True)
    return d
