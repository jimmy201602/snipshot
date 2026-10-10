"""snipshot command line interface.

  snipshot            trigger daemon if running, else capture+overlay now
  snipshot shoot      capture + overlay in this process (oneshot)
  snipshot daemon     resident mode; listens for TRIGGER on local socket
  snipshot install    register hotkey (and autostart in daemon mode)
  snipshot uninstall  remove hotkey + autostart
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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "trigger"

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

    if cmd == "daemon":
        from .daemon import run_daemon
        return run_daemon()

    if cmd == "shoot":
        app = _app()
        from .app import run_shot
        run_shot(app, quit_on_done=True)
        return app.exec()

    if cmd != "trigger":
        print(f"未知命令: {cmd}", file=sys.stderr)
        _usage()
        return 2

    # default: try daemon, fall back to oneshot
    from .ipc import send_trigger
    if send_trigger():
        return 0
    app = _app()
    from .app import run_shot
    run_shot(app, quit_on_done=True)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
