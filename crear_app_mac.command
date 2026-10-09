#!/bin/zsh
set -e
cd "${0:A:h}"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Instala Python 3 desde https://www.python.org/downloads/macos/"
  read -k 1
  exit 1
fi
python3 -m pip install --upgrade pyinstaller
rm -rf build dist
python3 -m PyInstaller --noconfirm --clean --windowed --onedir --name Zero --add-data "static:static" app.py
if [[ -d "dist/Zero.app" ]]; then
  mkdir -p "dist/Zero.app/Contents/MacOS/data"
  if [[ -f "data/zero.sqlite3" ]]; then cp "data/zero.sqlite3" "dist/Zero.app/Contents/MacOS/data/zero.sqlite3"; fi
else
  mkdir -p "dist/Zero/data"
  if [[ -f "data/zero.sqlite3" ]]; then cp "data/zero.sqlite3" "dist/Zero/data/zero.sqlite3"; fi
fi
echo "Listo: $(pwd)/dist/Zero.app"
open dist
