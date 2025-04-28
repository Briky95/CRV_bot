#!/bin/bash

# Script per configurare l'ambiente di sviluppo

echo "Configurazione dell'ambiente di sviluppo per il bot Telegram..."

# Verifica se l'ambiente virtuale esiste
if [ ! -d ".venv" ]; then
    echo "Creazione dell'ambiente virtuale..."
    python3 -m venv .venv
fi

# Attiva l'ambiente virtuale
source .venv/bin/activate

# Aggiorna pip e setuptools
echo "Aggiornamento di pip e setuptools..."
pip install --upgrade pip setuptools wheel

# Installa le dipendenze di sviluppo
echo "Installazione delle dipendenze di sviluppo..."
pip install -r requirements-dev.txt

# Verifica che tutte le dipendenze siano soddisfatte
echo "Verifica delle dipendenze..."
pip check || echo "Attenzione: ci sono conflitti di dipendenze, ma procediamo comunque"

echo "Configurazione completata! Attiva l'ambiente virtuale con 'source .venv/bin/activate'"