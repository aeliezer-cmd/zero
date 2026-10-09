#!/bin/zsh
cd "${0:A:h}"
export PATH="/Users/user/.gemini/antigravity/bin:$PATH"
if /usr/bin/curl -fsS http://127.0.0.1:8000/ > /dev/null 2>&1; then
  open http://127.0.0.1:8000/
  exit 0
fi
open http://127.0.0.1:8000/
python3 app.py --host 0.0.0.0
