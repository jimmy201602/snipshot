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
    # resident tray app must be running for the hotkey to work (unless
    # oneshot_fallback is on); NOT started at login unless autostart
    "autostart": False,
    "oneshot_fallback": False,
    # milliseconds between trigger and capture (lets transient UI settle)
    "capture_delay_ms": 40,
    # remembered across sessions (WeChat/QQ do this too)
    "last_color": "#00a2ff",
    "last_size": "M",
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
