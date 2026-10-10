"""snipshot command line interface.

  snipshot            open the app (tray daemon); if already running,
                      opens the settings window instead
  snipshot trigger    hotkey target: trigger daemon, or shoot oneshot if
                      "oneshot_fallback" is enabled; silent no-op otherwise
  snipshot shoot      capture + overlay in this process (oneshot)
  snipshot settings   open the settings dialog
  snipshot daemon     resident tray app; listens for TRIGGER on local socket
  snipshot wincheck   list windows visible to the AT-SPI hover-snap detector
  snipshot install    register hotkey (and autostart if enabled)
  snipshot uninstall  remove hotkey + autostart + menu entry
"""
import sys

from . import __version__


def _usage() -> None:
    print(__doc__)
    print(f"version: {__version__}")


def _app():
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv[:1])
    app.setApplicationName("snipshot")
    app.setApplicationVersion(__version__)
    return app


def _shoot() -> int:
    app = _app()
    from .app import run_shot
    run_shot(app, quit_on_done=True)
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "open"

    if cmd in ("-h", "--help", "help"):
        _usage()
        return 0
    if cmd in ("-v", "--version"):
        print(__version__)
        return 0

    if cmd == "install":
        from .install import install
        print(install())
        return 0
    if cmd == "uninstall":
        from .install import uninstall
        print(uninstall())
        return 0

    if cmd == "wincheck":
        from .winlist import (enum_windows_logical,
                              toolkit_accessibility_enabled)
        print("toolkit-accessibility:",
              toolkit_accessibility_enabled())
        wins = enum_windows_logical()
        for name, r in wins:
            print(f"{name:24} {r.x():7.0f},{r.y():6.0f} "
                  f"{r.width():6.0f}x{r.height():5.0f}")
        print(f"{len(wins)} windows detected")
        return 0

    if cmd == "settings":
        app = _app()
        from .settings import SettingsDialog
        SettingsDialog().exec()
        return 0

    if cmd == "shoot":
        return _shoot()

    if cmd == "daemon":
        from .ipc import query
        if query("STATUS") is not None:
            print("snipshot daemon 已在运行")
            return 0
        from .daemon import run_daemon
        return run_daemon()

    if cmd == "trigger":
        # hotkey entry: only while the app is running, unless the user
        # opted into the oneshot fallback in settings
        from .ipc import send_trigger
        if send_trigger():
            return 0
        from . import config
        if config.load().get("oneshot_fallback"):
            return _shoot()
        return 0

    if cmd == "open":
        # launched from menu/desktop: if the app is already running the
        # user meant "open the app", not "take a screenshot" — surface
        # the settings window; otherwise start the tray daemon
        from .ipc import query
        if query("SETTINGS") is not None:
            return 0
        from .daemon import run_daemon
        return run_daemon()

    print(f"未知命令: {cmd}", file=sys.stderr)
    _usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
