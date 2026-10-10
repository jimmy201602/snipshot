#!/usr/bin/env bash
# Build a self-contained single-file binary: dist/snipshot
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m PyInstaller \
    --onefile \
    --name snipshot \
    --clean \
    --noconfirm \
    --paths . \
    --hidden-import PIL \
    --hidden-import snipshot.daemon \
    --hidden-import snipshot.install \
    --hidden-import snipshot.pin \
    packaging/entry.py

echo
echo "Built: $(pwd)/dist/snipshot"
ls -lh dist/snipshot
