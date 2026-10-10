# Snipshot

仿微信/QQ 的 Linux 截图工具：全局快捷键唤起 → 冻结屏幕 → 框选 → 标注 → 复制/保存/钉图。

## 快捷键

默认绑定 **Ctrl+Alt+A**（QQ 风格）。改键：编辑 `~/.config/snipshot/config.json`
的 `hotkey`（如 `"<Alt>a"` 为微信风格），再运行 `snipshot install`。

> Wayland 下应用无法自行抢注全局按键，快捷键通过桌面环境的
> “自定义快捷键”注册（GNOME: `org.gnome.settings-daemon.plugins.media-keys`）。

## 安装

```bash
pip install .          # 或直接用仓库源码
snipshot install       # 注册快捷键（daemon 模式下同时注册开机自启）
```

依赖：Python ≥3.9、PyQt6、Pillow；截图后端自动探测
（Wayland: `gnome-screenshot`/`grim`/`spectacle`，X11: `maim`/`import`/`scrot`）。
剪贴板持久化优先用 `wl-copy` / `xclip`（都没有时会常驻进程代管剪贴板，
直到下次复制后自动退出）。

## 用法

| 命令 | 说明 |
|---|---|
| `snipshot` | 有守护进程则触发，否则即时截图（快捷键执行的就是它） |
| `snipshot shoot` | 强制单次截图（调试/无守护时） |
| `snipshot daemon` | 常驻模式，监听 socket 触发 |
| `snipshot install` | 注册快捷键 + （daemon 模式）自启 |
| `snipshot uninstall` | 移除快捷键与自启 |

## 操作

- 拖拽框选；八个手柄调整；选区内拖动移动；双击/Enter 完成（复制）
- Ctrl+A 全选；Ctrl+Z 撤销；Ctrl+S 保存；Esc/右键 取消
- 工具栏：矩形 / 椭圆 / 箭头 / 画笔 / 马赛克 / 文字 / 撤销 / 钉图 / 保存 / 取消 / 完成
- 上方浮动条：8 色 + S/M/L 三档粗细
- 空闲时光标处有像素放大镜（放大图 + 坐标 + 十六进制色值）

## 测试

```bash
python3 -m pytest tests/        # offscreen 部件级测试（QTest）
```

真机验证：`snipshot daemon &` 再 `snipshot`，或按 Ctrl+Alt+A。

## 架构

```
gnome-screenshot ──> 全屏 PNG ──> Overlay(每屏一个, Frameless+Fullscreen)
                                     ├─ Session: 选区/标注(image-px 坐标)
                                     ├─ Toolbar/PaletteBar
                                     ├─ magnifier / shapes / pin
                                     └─ clipboard → wl-copy | 常驻托管
Ctrl+Alt+A ──gsettings──> ~/.local/bin/snipshot ──socket──> daemon(可选)
```

多显示器：每个屏幕一个覆盖层，截图按虚拟桌面几何等比映射；选区归属
发起拖拽的屏幕。混合 DPI 下按整体比例换算。
