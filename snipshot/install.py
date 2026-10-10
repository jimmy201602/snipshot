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


def keybind_command() -> str:
    """The command line the desktop hotkey should invoke.

    Priority:
      1. PyInstaller binary (we ARE the frozen executable)
      2. a `snipshot` already on PATH (pip install / packaged binary)
      3. source checkout -> write a wrapper into ~/.local/bin
    """
    if getattr(sys, "frozen", False):
        return sys.executable
    exe = shutil.which("snipshot")
    if exe:
        return exe
    path = launcher_path()
    if not (path.exists() and "snipshot" in path.read_text(errors="replace")):
        repo = Path(__file__).resolve().parent.parent
        path.write_text(
            "#!/bin/sh\n"
            f'PYTHONPATH="{repo}" exec "{sys.executable}" -m snipshot "$@"\n')
        path.chmod(0o755)
    return str(path)


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
    cmd = keybind_command()
    paths = _current_bindings()
    if BIND_PATH not in paths:
        paths.append(BIND_PATH)
        formatted = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
        _gsettings("set", BASE_SCHEMA, "custom-keybindings", formatted)
    base = ["gsettings", "set"]
    subprocess.run([*base, f"{BIND_SCHEMA}:{BIND_PATH}",
                    "name", "Snipshot 截图"], check=True)
    subprocess.run([*base, f"{BIND_SCHEMA}:{BIND_PATH}",
                    "command", f"'{cmd} trigger'"], check=True)
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


DESKTOP_FILE = (Path.home() / ".local" / "share" / "applications"
                / "snipshot.desktop")


def install_autostart() -> None:
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Snipshot Daemon\n"
        f"Exec={keybind_command()} daemon\n"
        "X-GNOME-Autostart-enabled=true\n"
        "NoDisplay=true\n")


def remove_autostart() -> None:
    AUTOSTART.unlink(missing_ok=True)


def install_desktop_entry() -> None:
    DESKTOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    DESKTOP_FILE.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Snipshot 截图\n"
        "Comment=仿微信/QQ 的截图工具 (Ctrl+Alt+A)\n"
        f"Exec={keybind_command()}\n"
        "Icon=applets-screenshooter\n"
        "Categories=Utility;\n")


def remove_desktop_entry() -> None:
    DESKTOP_FILE.unlink(missing_ok=True)


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
                    f"{keybind_command()}")
    install_desktop_entry()
    if cfg.get("autostart"):
        install_autostart()
        msgs.append("已启用开机自启")
    else:
        remove_autostart()   # clean up a stale entry from older installs
    return "\n".join(msgs)


def uninstall() -> str:
    remove_hotkey()
    remove_autostart()
    remove_desktop_entry()
    return "已移除快捷键、自启动项与应用菜单项"
