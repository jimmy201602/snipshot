"""Resident daemon: stays running, listens for TRIGGER on a local socket,
and shows the capture overlay when triggered."""
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
        self.server = QLocalServer(self)
        path = str(ipc.socket_path())
        QLocalServer.removeServer(path)
        self.server.listen(path)
        self.server.newConnection.connect(self._on_conn)

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
        else:
            sock.write(b"OK\n")
        sock.flush()
        sock.disconnectFromServer()
        if data == "TRIGGER" and not self.busy:
            self.busy = True
            run_shot(self.app, quit_on_done=False,
                     on_session=lambda s: s.finished.connect(self._idle))

    def _idle(self) -> None:
        self.busy = False


def run_daemon() -> int:
    app = QApplication([])
    app.setApplicationName("snipshot")
    app.setQuitOnLastWindowClosed(False)
    daemon = Daemon(app)
    if not daemon.server.isListening():
        return 1
    return app.exec()
