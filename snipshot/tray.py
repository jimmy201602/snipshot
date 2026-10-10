"""System tray integration: icon + menu + settings entry.

On GNOME this needs an AppIndicator/KStatusNotifier extension to be
visible (KDE shows it natively); if the tray is unavailable the daemon
still works, and settings can be opened via `snipshot settings`.
"""
from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import config, install
from .settings import SettingsDialog
from .trayicon import tray_icon


class TrayApp(QObject):
    def __init__(self, app: QApplication, daemon):
        super().__init__()
        self.daemon = daemon
        self.tray: QSystemTrayIcon | None = None
        self._dlg: SettingsDialog | None = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("系统托盘不可用（GNOME 需要 AppIndicator 扩展）;"
                  "仍可通过快捷键和 `snipshot settings` 使用。")
            return

        self.tray = QSystemTrayIcon(tray_icon(), app)
        self.tray.setToolTip("Snipshot 截图")

        menu = QMenu()
        act_shot = menu.addAction("截图")
        act_shot.triggered.connect(daemon.trigger)
        menu.addSeparator()

        act_set = menu.addAction("设置…")
        act_set.triggered.connect(self.open_settings)

        self.act_auto = menu.addAction("开机自启")
        self.act_auto.setCheckable(True)
        self.act_auto.setChecked(bool(config.load().get("autostart")))
        self.act_auto.toggled.connect(self._toggle_autostart)

        menu.addSeparator()
        act_quit = menu.addAction("退出")
        act_quit.triggered.connect(app.quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._activated)
        self.tray.show()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_settings()

    def open_settings(self) -> None:
        if self._dlg is not None and self._dlg.isVisible():
            self._dlg.raise_()
            self._dlg.activateWindow()
            return
        # WindowStaysOnTopHint: on Wayland a background daemon can't
        # raise its own window — without this the dialog opens *behind*
        # the focused window and the icon click looks like a no-op
        self._dlg = SettingsDialog()
        self._dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self._dlg.exec()
        self._dlg = None
        self.act_auto.setChecked(bool(config.load().get("autostart")))

    def _toggle_autostart(self, on: bool) -> None:
        cfg = config.load()
        cfg["autostart"] = on
        config.save(cfg)
        if on:
            install.install_autostart()
        else:
            install.remove_autostart()
