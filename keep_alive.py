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
        # Aggiungi un parametro casuale per evitare la cache
        random_param = f"nocache={datetime.now().timestamp()}"
        url = f"{RENDER_URL}?{random_param}"
        
        # Imposta un timeout più breve per evitare blocchi
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            logger.info(f"Ping riuscito: {response.status_code} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            logger.warning(f"Ping fallito con codice: {response.status_code}")
            
            # Riprova dopo un breve ritardo in caso di errore
            time.sleep(5)
            retry_response = requests.get(url, timeout=5)
            logger.info(f"Retry ping: {retry_response.status_code}")
    except requests.exceptions.Timeout:
        logger.warning("Timeout durante il ping. Il server potrebbe essere sovraccarico.")
    except requests.exceptions.ConnectionError:
        logger.warning("Errore di connessione durante il ping. Il server potrebbe essere temporaneamente non disponibile.")
    except Exception as e:
        logger.error(f"Errore durante il ping: {e}")

def start_ping_thread():
    """Avvia un thread che invia ping periodici al server."""
    def ping_loop():
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        # Ping immediato all'avvio
        try:
            ping_server()
            consecutive_errors = 0
        except Exception as e:
            logger.error(f"Errore nel ping iniziale: {e}")
            consecutive_errors += 1
        
        while True:
            try:
                # Attendi l'intervallo di ping
                time.sleep(PING_INTERVAL)
                
                # Esegui il ping
                ping_server()
                consecutive_errors = 0  # Resetta il contatore degli errori
            except Exception as e:
                logger.error(f"Errore nel ciclo di ping: {e}")
                consecutive_errors += 1
                
                # Se ci sono troppi errori consecutivi, riduci l'intervallo temporaneamente
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning(f"Rilevati {consecutive_errors} errori consecutivi. Riduzione temporanea dell'intervallo di ping.")
                    time.sleep(60)  # Attendi solo 1 minuto prima del prossimo tentativo
                    consecutive_errors = 0  # Resetta il contatore
    
    # Avvia il thread
    ping_thread = threading.Thread(target=ping_loop, daemon=True)
    ping_thread.name = "KeepAliveThread"  # Assegna un nome al thread per il debug
    ping_thread.start()
    logger.info(f"Thread di ping avviato. Intervallo: {PING_INTERVAL} secondi.")
    
    # Ping immediato per verificare che tutto funzioni
    ping_server()
    
    return ping_thread

def check_url_configuration():
    """Verifica che l'URL sia configurato correttamente."""
    if not RENDER_URL or RENDER_URL == "https://crv-bot.onrender.com":
        logger.warning("Stai utilizzando l'URL di default. Assicurati di impostare la variabile d'ambiente RENDER_URL con l'URL corretto del tuo servizio.")
        return False
    
    # Verifica che l'URL sia raggiungibile
    try:
        response = requests.get(RENDER_URL, timeout=5)
        logger.info(f"URL di Render verificato: {RENDER_URL} - Stato: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Impossibile raggiungere l'URL di Render: {e}")
        return False

if __name__ == "__main__":
    logger.info("Avvio del servizio di keep-alive...")
    
    # Verifica che l'URL sia configurato
    url_ok = check_url_configuration()
    if not url_ok:
        logger.warning("L'URL potrebbe non essere configurato correttamente, ma il servizio verrà avviato comunque.")
    
    # Avvia il thread di ping
    ping_thread = start_ping_thread()
    
    # Mantieni il processo principale in esecuzione
    try:
        while True:
            # Controlla ogni ora
            for i in range(12):  # 12 controlli da 5 minuti = 1 ora
                time.sleep(300)  # 5 minuti
                
                # Verifica che il thread sia ancora attivo
                if not ping_thread.is_alive():
                    logger.warning("Thread di ping non più attivo. Riavvio...")
                    ping_thread = start_ping_thread()
                else:
                    logger.info("Servizio keep-alive ancora attivo...")
    except KeyboardInterrupt:
        logger.info("Interruzione rilevata. Uscita in corso...")
    except Exception as e:
        logger.error(f"Errore nel ciclo principale: {e}")
        # Riavvia il servizio in caso di errore
        logger.info("Tentativo di riavvio del servizio...")
        ping_thread = start_ping_thread()