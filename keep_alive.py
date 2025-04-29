#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script per mantenere attivo il bot su Render.
Questo script invia richieste periodiche al server per evitare che venga disattivato dopo 15 minuti di inattività.
"""

import os
import time
import logging
import requests
import threading
from datetime import datetime

# Configurazione del logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# URL del server Render (sostituisci con l'URL effettivo del tuo servizio)
RENDER_URL = os.getenv("RENDER_URL", "https://crv-bot.onrender.com")

# Intervallo di ping in secondi (ogni 5 minuti)
PING_INTERVAL = 300

def ping_server():
    """Invia una richiesta GET al server per mantenerlo attivo."""
    try:
        response = requests.get(RENDER_URL, timeout=10)
        if response.status_code == 200:
            logger.info(f"Ping riuscito: {response.status_code} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            logger.warning(f"Ping fallito con codice: {response.status_code}")
    except Exception as e:
        logger.error(f"Errore durante il ping: {e}")

def start_ping_thread():
    """Avvia un thread che invia ping periodici al server."""
    def ping_loop():
        while True:
            ping_server()
            time.sleep(PING_INTERVAL)
    
    # Avvia il thread
    ping_thread = threading.Thread(target=ping_loop, daemon=True)
    ping_thread.start()
    logger.info(f"Thread di ping avviato. Intervallo: {PING_INTERVAL} secondi.")
    return ping_thread

if __name__ == "__main__":
    logger.info("Avvio del servizio di keep-alive...")
    
    # Verifica che l'URL sia configurato
    if RENDER_URL == "https://crv-bot.onrender.com":
        logger.warning("Stai utilizzando l'URL di default. Assicurati di impostare la variabile d'ambiente RENDER_URL con l'URL corretto del tuo servizio.")
    
    # Avvia il thread di ping
    ping_thread = start_ping_thread()
    
    # Mantieni il processo principale in esecuzione
    try:
        while True:
            time.sleep(3600)  # Controlla ogni ora
            logger.info("Servizio keep-alive ancora attivo...")
    except KeyboardInterrupt:
        logger.info("Interruzione rilevata. Uscita in corso...")