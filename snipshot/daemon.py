"""Resident app: tray icon + local socket listener for TRIGGER."""
from PyQt6.QtCore import QObject
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication

from . import ipc
from .app import run_shot


class Daemon(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.busy = False
        self._tray = None
        self.server = QLocalServer(self)
        path = str(ipc.socket_path())
        QLocalServer.removeServer(path)
        self.server.listen(path)
        self.server.newConnection.connect(self._on_conn)

    def trigger(self) -> None:
        """Start a capture+overlay session (socket or tray entry point)."""
        if not self.busy:
            self.busy = True
            run_shot(self.app, quit_on_done=False,
                     on_session=lambda s: s.finished.connect(self._idle))

    def _idle(self) -> None:
        self.busy = False

    def _on_conn(self) -> None:
        while self.server.hasPendingConnections():
            sock: QLocalSocket = self.server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._on_msg(s))
            sock.waitForReadyRead(500)
            self._on_msg(sock)

    def _on_msg(self, sock: QLocalSocket) -> None:
        data = bytes(sock.readAll()).decode(errors="replace").strip()
        if data == "STATUS":
            from PyQt6.QtGui import QGuiApplication
            fw = QGuiApplication.focusWindow()
            sock.write(b"FOCUSED\n" if fw is not None else b"NONE\n")
        elif data == "SETTINGS":
            sock.write(b"OK\n")
            sock.flush()
            sock.disconnectFromServer()
            self._open_settings()
            return
        else:
            sock.write(b"OK\n")
        sock.flush()
        sock.disconnectFromServer()
        if data == "TRIGGER":
            self.trigger()

    def _open_settings(self) -> None:
        if self._tray is not None:
            self._tray.open_settings()
        else:
            from .settings import SettingsDialog
            SettingsDialog().exec()


def run_daemon() -> int:
    app = QApplication([])
    app.setApplicationName("snipshot")
    app.setQuitOnLastWindowClosed(False)
    # a live daemon may be momentarily unreachable while its GUI thread is
    # blocked (e.g. mid-capture) — probe with a generous timeout BEFORE
    # touching the socket, or we'd steal it from a running instance
    if ipc.query("STATUS", timeout=3.0) is not None:
        print("snipshot daemon 已在运行")
        return 0
    daemon = Daemon(app)
    if not daemon.server.isListening():
        print("snipshot daemon 已在运行")
        return 1
    from .tray import TrayApp
    daemon._tray = TrayApp(app, daemon)
    return app.exec()
