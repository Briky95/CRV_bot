#!/bin/bash

# Vai alla directory del bot
cd "$(dirname "$0")"

# Attiva l'ambiente virtuale se esiste
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Avvia il bot
python3 bot_fixed_corrected.py

# Se il bot si chiude, registra l'evento
echo "Bot terminato alle $(date)" >> bot_log.txt