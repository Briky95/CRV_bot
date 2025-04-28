#!/bin/bash

# Vai alla directory del bot
cd "$(dirname "$0")"

# Attiva l'ambiente virtuale se esiste
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Avvia l'interfaccia web
python3 web_admin/app.py