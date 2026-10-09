#!/bin/zsh
cd "${0:A:h}"
export PATH="/Users/user/.gemini/antigravity/bin:$PATH"
python3 iniciar_red.py
read -k 1
