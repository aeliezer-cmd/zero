#!/bin/zsh
cd "${0:A:h}"
python3 app.py --backup "respaldos/zero-$(date +%Y%m%d-%H%M%S).sqlite3"
printf '\nPulse Enter para cerrar.\n'
read
