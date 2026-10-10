#!/usr/bin/env bash
# Build snipshot_<ver>-1_amd64.deb from the PyInstaller binary.
# Usage: bash packaging/build-deb.sh   (builds dist/snipshot first if missing)
set -euo pipefail
cd "$(dirname "$0")/.."

VER="$(python3 -c 'import tomllib,sys; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])' 2>/dev/null \
       || grep -oP '__version__ = "\K[^"]+' snipshot/__init__.py)"
PKG="snipshot_${VER}-1_amd64"
ROOT="build/deb/${PKG}"

[ -x dist/snipshot ] || bash packaging/build.sh
command -v dpkg-deb >/dev/null || { echo "需要 dpkg-deb (apt install dpkg)"; exit 1; }

rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" \
         "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/icons/hicolor/256x256/apps" \
         "$ROOT/usr/share/doc/snipshot"

# --- payload ------------------------------------------------------------
cp dist/snipshot "$ROOT/usr/bin/snipshot"
chmod 755 "$ROOT/usr/bin/snipshot"

QT_QPA_PLATFORM=offscreen python3 -c "
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from snipshot.trayicon import tray_icon
tray_icon().pixmap(256, 256).save('$ROOT/usr/share/icons/hicolor/256x256/apps/snipshot.png')"

cat > "$ROOT/usr/share/applications/snipshot.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Snipshot
Name[zh_CN]=Snipshot 截图
Comment=WeChat/QQ-style screenshot tool (Ctrl+Alt+A)
Comment[zh_CN]=仿微信/QQ 的截图工具（Ctrl+Alt+A）
Exec=snipshot
Icon=snipshot
Terminal=false
Categories=Utility;Graphics;
Keywords=screenshot;snip;capture;截图;
StartupNotify=false
EOF

cat > "$ROOT/usr/share/doc/snipshot/copyright" <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: snipshot
Source: https://github.com/jimmy201602/snipshot

Files: *
Copyright: 2026 jimmy201602 <jimmy201602@users.noreply.github.com>
License: see https://github.com/jimmy201602/snipshot
EOF

cat > /tmp/snipshot-changelog <<EOF
snipshot (${VER}-1) unstable; urgency=medium

  * Release ${VER}.

 -- jimmy201602 <jimmy201602@users.noreply.github.com>  $(date -R)
EOF
gzip -9 -c /tmp/snipshot-changelog > "$ROOT/usr/share/doc/snipshot/changelog.gz"

# --- DEBIAN -------------------------------------------------------------
SIZE=$(du -sk "$ROOT" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<EOF
Package: snipshot
Version: ${VER}-1
Architecture: amd64
Maintainer: jimmy201602 <jimmy201602@users.noreply.github.com>
Installed-Size: ${SIZE}
Section: utils
Priority: optional
Homepage: https://github.com/jimmy201602/snipshot
Recommends: wl-clipboard | xclip, python3-pyatspi
Suggests: grim | spectacle
Description: WeChat/QQ-style screenshot tool for Linux
 Ctrl+Alt+A global hotkey, hover-to-snap window capture (AT-SPI),
 free-form region selection, annotations (rect/ellipse/arrow/pen/
 mosaic/text), clipboard copy, PNG save, pin-to-desktop, tray icon
 with settings. Works on Wayland and X11; detects gnome-screenshot,
 grim, spectacle, maim, import or scrot as capture backend.
 .
 After installing, run "snipshot install" once as your desktop user
 to register the Ctrl+Alt+A hotkey (per-user gsettings).
EOF

cat > "$ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
# best-effort: register the hotkey for the user who ran sudo
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    uid=$(id -u "$SUDO_USER" 2>/dev/null || true)
    if [ -n "$uid" ]; then
        sudo -u "$SUDO_USER" \
            DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
            XDG_RUNTIME_DIR="/run/user/$uid" \
            /usr/bin/snipshot install >/dev/null 2>&1 || true
    fi
fi
exit 0
EOF
chmod 755 "$ROOT/DEBIAN/postinst"

# Debian perms: dirs/exes 755, files 644, all root:root
find "$ROOT" -type d -exec chmod 755 {} +
find "$ROOT/usr" -type f ! -name snipshot -exec chmod 644 {} +
chmod 755 "$ROOT/usr/bin/snipshot"

fakeroot dpkg-deb --root-owner-group --build "$ROOT" \
    "dist/${PKG}.deb" 2>/dev/null \
    || dpkg-deb --root-owner-group --build "$ROOT" "dist/${PKG}.deb"
echo "Built: dist/${PKG}.deb"
