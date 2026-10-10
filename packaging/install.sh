#!/usr/bin/env bash
# Install the packaged binary: copy to ~/.local/bin + register hotkey.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${1:-$DIR/dist/snipshot}"

if [ ! -f "$BIN" ]; then
    echo "找不到二进制: $BIN"
    echo "先运行 packaging/build.sh 构建，或传入路径: $0 /path/to/snipshot"
    exit 1
fi

install -Dm755 "$BIN" "$HOME/.local/bin/snipshot"
"$HOME/.local/bin/snipshot" install

echo
echo "安装完成 ✔  按 Ctrl+Alt+A 开始截图"
echo "配置文件: ~/.config/snipshot/config.json"
