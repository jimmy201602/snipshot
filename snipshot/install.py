"""Install/uninstall the desktop integration.

On GNOME-based desktops the global hotkey is registered through the
"custom keybindings" mechanism (the same place Settings > Keyboard uses),
because Wayland does not let apps grab keys globally.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import config

BASE_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
BIND_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
BIND_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/snipshot/"
AUTOSTART = Path.home() / ".config" / "autostart" / "snipshot-daemon.desktop"


def _gsettings(*args: str) -> str:
    res = subprocess.run(["gsettings", *args], capture_output=True,
                         text=True, timeout=10)
    if res.returncode != 0:
        raise RuntimeError(f"gsettings {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout.strip()


def launcher_path() -> Path:
    """Path of a small wrapper script the keybinding invokes."""
    bindir = Path.home() / ".local" / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    return bindir / "snipshot"


def write_launcher() -> Path:
    """Create ~/.local/bin/snipshot pointing at this installation."""
    path = launcher_path()
    exe = shutil.which("snipshot")
    if exe and Path(exe).resolve() != path:
        # installed via pip already
        path.write_text(f'#!/bin/sh\nexec "{exe}" "$@"\n')
    else:
        repo = Path(__file__).resolve().parent.parent
        path.write_text(
            "#!/bin/sh\n"
            f'PYTHONPATH="{repo}" exec "{sys.executable}" -m snipshot "$@"\n')
    path.chmod(0o755)
    return path


def _current_bindings() -> list[str]:
    out = _gsettings("get", BASE_SCHEMA, "custom-keybindings")
    # format: ['path1', 'path2'] or '@as []'
    out = out.strip()
    if out.startswith("@as "):
        out = out[4:]
    items = out.strip("[]")
    if not items.strip():
        return []
    return [i.strip().strip("'\"") for i in items.split(",") if i.strip()]


def install_hotkey() -> bool:
    """Register the hotkey as a GNOME custom keybinding. Returns success."""
    if not shutil.which("gsettings"):
        return False
    cfg = config.load()
    cmd = str(write_launcher())
    paths = _current_bindings()
    if BIND_PATH not in paths:
        paths.append(BIND_PATH)
        formatted = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
        _gsettings("set", BASE_SCHEMA, "custom-keybindings", formatted)
    base = ["gsettings", "set"]
    subprocess.run([*base, f"{BIND_SCHEMA}:{BIND_PATH}",
                    "name", "Snipshot 截图"], check=True)
    subprocess.run([*base, f"{BIND_SCHEMA}:{BIND_PATH}",
                    "command", f"'{cmd}'"], check=True)
    subprocess.run([*base, f"{BIND_SCHEMA}:{BIND_PATH}",
                    "binding", f"'{cfg['hotkey']}'"], check=True)
    return True


def remove_hotkey() -> None:
    if not shutil.which("gsettings"):
        return
    paths = [p for p in _current_bindings() if p != BIND_PATH]
    formatted = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
    subprocess.run(["gsettings", "set", BASE_SCHEMA,
                    "custom-keybindings", formatted],
                   capture_output=True)


def install_autostart() -> None:
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Snipshot Daemon\n"
        f"Exec={launcher_path()} daemon\n"
        "X-GNOME-Autostart-enabled=true\n"
        "NoDisplay=true\n")


def remove_autostart() -> None:
    AUTOSTART.unlink(missing_ok=True)


def install() -> str:
    cfg = config.load()
    config.save(cfg)
    msgs = []
    if install_hotkey():
        msgs.append(f"快捷键已注册: {cfg['hotkey']}  "
                    "(GNOME 自定义快捷键)")
    else:
        msgs.append("无法自动注册快捷键 (非 GNOME 或无 gsettings)。\n"
                    "请手动在系统设置中添加快捷键，命令: "
                    f"{write_launcher()}")
    if cfg.get("mode") == "daemon":
        install_autostart()
        msgs.append("已启用开机自启 (daemon 模式)")
    return "\n".join(msgs)


def uninstall() -> str:
    remove_hotkey()
    remove_autostart()
    return "已移除快捷键与自启动项"
