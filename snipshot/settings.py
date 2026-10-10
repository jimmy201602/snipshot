"""Settings dialog (opened from the tray menu or `snipshot settings`)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
                             QPushButton, QSpinBox, QVBoxLayout)

from . import config, install

HOTKEY_PRESETS = [
    ("Ctrl+Alt+A（QQ 风格）", "<Ctrl><Alt>a"),
    ("Alt+A（微信风格）", "<Alt>a"),
    ("自定义…", ""),
]

_DIALOG_STYLE = """
QDialog { background: #202126; color: #e8e8e8; }
QLabel, QCheckBox { color: #e8e8e8; }
QLineEdit, QComboBox, QSpinBox {
    background: #2b2d33; color: #e8e8e8;
    border: 1px solid #3c3f47; border-radius: 4px; padding: 4px 6px;
}
QComboBox QAbstractItemView { background: #2b2d33; color: #e8e8e8; }
QPushButton {
    background: #2b2d33; border: 1px solid #3c3f47;
    border-radius: 4px; padding: 5px 14px;
}
QPushButton:hover { background: #35383f; }
QPushButton:default { background: #0a84ff; border-color: #0a84ff; }
"""


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Snipshot 设置")
        self.setStyleSheet(_DIALOG_STYLE)
        self.cfg = config.load()

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.hk_combo = QComboBox()
        for label, _v in HOTKEY_PRESETS:
            self.hk_combo.addItem(label)
        cur = self.cfg.get("hotkey", "<Ctrl><Alt>a")
        idx = next((i for i, (_l, v) in enumerate(HOTKEY_PRESETS) if v == cur),
                   len(HOTKEY_PRESETS) - 1)
        self.hk_combo.setCurrentIndex(idx)
        self.hk_combo.currentIndexChanged.connect(self._hk_changed)
        self.hk_edit = QLineEdit(cur)
        self.hk_edit.setPlaceholderText("gsettings 格式，如 <Ctrl><Alt>a")
        row = QHBoxLayout()
        row.addWidget(self.hk_combo)
        row.addWidget(self.hk_edit)
        form.addRow("截图快捷键", row)
        self._hk_changed(idx)

        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit(self.cfg.get("save_dir", ""))
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse)
        dir_row.addWidget(self.dir_edit)
        dir_row.addWidget(browse)
        form.addRow("保存目录", dir_row)

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 2000)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setValue(int(self.cfg.get("capture_delay_ms", 40)))
        form.addRow("触发延迟", self.delay_spin)

        self.windetect_chk = QCheckBox(
            "窗口边缘吸附（悬停自动选中窗口，需系统辅助功能接口）")
        self.windetect_chk.setChecked(bool(self.cfg.get("window_detect", True)))
        form.addRow("", self.windetect_chk)

        self.oneshot_chk = QCheckBox("软件未运行时，快捷键也可直接截图（单次模式）")
        self.oneshot_chk.setChecked(bool(self.cfg.get("oneshot_fallback")))
        form.addRow("", self.oneshot_chk)

        self.autostart_chk = QCheckBox("登录时自动启动")
        self.autostart_chk.setChecked(bool(self.cfg.get("autostart")))
        form.addRow("", self.autostart_chk)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(btns)

    def _hk_changed(self, idx: int) -> None:
        self.hk_edit.setEnabled(idx == len(HOTKEY_PRESETS) - 1)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择保存目录",
                                             self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def accept(self) -> None:
        cfg = self.cfg
        idx = self.hk_combo.currentIndex()
        if idx < len(HOTKEY_PRESETS) - 1:
            cfg["hotkey"] = HOTKEY_PRESETS[idx][1]
        else:
            custom = self.hk_edit.text().strip()
            if custom:
                cfg["hotkey"] = custom
        cfg["save_dir"] = self.dir_edit.text().strip() or cfg["save_dir"]
        cfg["capture_delay_ms"] = self.delay_spin.value()
        cfg["oneshot_fallback"] = self.oneshot_chk.isChecked()
        cfg["window_detect"] = self.windetect_chk.isChecked()
        cfg["autostart"] = self.autostart_chk.isChecked()
        config.save(cfg)

        if cfg["window_detect"]:
            # AT-SPI window enumeration needs the desktop a11y tree on
            from .winlist import enable_toolkit_accessibility
            enable_toolkit_accessibility()

        install.install_hotkey()
        if cfg["autostart"]:
            install.install_autostart()
        else:
            install.remove_autostart()
        super().accept()
