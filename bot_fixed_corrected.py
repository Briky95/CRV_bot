#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import json
import os
import time
import pandas as pd
import threading
import socket
import sys
import atexit
import tempfile
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from modules.export_manager import genera_excel_riepilogo_weekend, genera_pdf_riepilogo_weekend
from modules.db_manager import carica_utenti, salva_utenti, carica_risultati, salva_risultati, carica_squadre, salva_squadre
from modules.data_manager import carica_reazioni, salva_reazioni
from modules.monitor import bot_monitor
from conferma_callback import conferma_callback

# Abilita logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Stati della conversazione
CATEGORIA, GENERE, TIPO_PARTITA, SQUADRA1, SQUADRA2, SQUADRA3, DATA_PARTITA, PUNTEGGIO1, PUNTEGGIO2, PUNTEGGIO3, METE1, METE2, METE3, ARBITRO, SEZIONE_ARBITRALE, CONFERMA = range(16)

# Categorie di rugby predefinite
CATEGORIE = ["Serie A Elite", "Serie A", "Serie B", "Serie C1", "U18 Nazionale", "U18", "U16", "U14"]

# Sezioni arbitrali
SEZIONI_ARBITRALI = [
    "Padova",
    "Rovigo",
    "San Donà",
    "Treviso",
    "Verona",
    "S.U. FVG"
]

# Squadre di default in caso di errore
SQUADRE_DEFAULT = [
    "ASD AVALON",
    "BOLZANO RUGBY ASD",
    "ASD C'E' L'ESTE RUGBY",
    "PATAVIUM RUGBY JUNIOR A.S.D.",
    "ASD I MAI SOBRI - BEACH RUGBY",
    "OMBRE ROSSE WLFTM OLD R.PADOVA ASD PD",
    "ASD RUGBY TRENTO",
    "RUGBY ROVIGO DELTA SRL SSD",
    "RUGBY PAESE ASD",
    "RUGBY BASSANO 1976 ASD",
    "RUGBY FELTRE ASD",
    "RUGBY BELLUNO ASD",
    "RUGBY CONEGLIANO ASD",
    "RUGBY CASALE ASD",
    "RUGBY VICENZA ASD",
    "RUGBY MIRANO 1957 ASD",
    "RUGBY VALPOLICELLA ASD",
    "VERONA RUGBY ASD"
]

# Variabile per memorizzare le squadre
_squadre_cache = None
_squadre_last_load = 0

# Carica le squadre all'avvio del bot
def get_squadre_list():
    squadre_list = carica_squadre()
    
    # Se non ci sono squadre, usa quelle di default
    if not squadre_list:
        return SQUADRE_DEFAULT
    
    return squadre_list

# Carica le squadre all'avvio del bot
SQUADRE = get_squadre_list()

# Token del bot Telegram
from dotenv import load_dotenv
load_dotenv()  # Carica le variabili d'ambiente dal file .env

# Funzione per caricare il token dal file token.txt (per retrocompatibilità)
def carica_token():
    try:
        # Prova prima con il percorso assoluto
        token_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'token.txt')
        if os.path.exists(token_path):
            with open(token_path, "r") as file:
                return file.read().strip()
        
        # Prova con il percorso relativo
        if os.path.exists("token.txt"):
            with open("token.txt", "r") as file:
                return file.read().strip()
        
        return None
    except Exception as e:
        print(f"Errore nel caricare il token: {e}")
        return None

# Usa il token dal file .env o dal file token.txt come fallback
TOKEN = os.getenv("BOT_TOKEN") or carica_token() or "8108188221:AAEBSfi29p63lPbIxDooDuu9VB0iMWeYJzo"

# Log per debug
print(f"Token utilizzato: {TOKEN[:5]}...{TOKEN[-5:]}")
print(f"Variabile d'ambiente BOT_TOKEN: {'Impostata' if os.getenv('BOT_TOKEN') else 'Non impostata'}")
print(f"Token caricato da file: {'Sì' if carica_token() else 'No'}")
print(f"Ambiente: {'AWS Lambda' if os.environ.get('AWS_EXECUTION_ENV') else 'Locale'}")

# ID del canale Telegram dove inviare gli aggiornamenti
# Nota: deve essere nel formato @nome_canale o -100xxxxxxxxxx
CHANNEL_ID = "@CRV_Rugby_Risultati_Partite"  # Sostituisci con l'ID o il nome del tuo canale

# Percorso del file JSON
RISULTATI_FILE = "risultati.json"
UTENTI_FILE = "utenti.json"
REAZIONI_FILE = "reazioni.json"

# ID degli amministratori del bot (possono approvare altri utenti)
ADMIN_IDS = [30658851]  # Sostituisci con il tuo ID Telegram

# Cache per i dati
_cache = {
    'risultati': None,
    'utenti': None,
    'reazioni': None,
    'last_load': {
        'risultati': 0,
        'utenti': 0,
        'reazioni': 0
    }
}

# Tempo di validità della cache in secondi (5 secondi)
CACHE_TTL = 5

# Le funzioni carica_risultati e salva_risultati sono ora importate dal modulo db_manager

# Le funzioni carica_utenti e salva_utenti sono ora importate dal modulo db_manager

# Cache per gli utenti autorizzati
_utenti_autorizzati_cache = {}
_utenti_autorizzati_last_update = 0

# Funzione per verificare se un utente è autorizzato
def is_utente_autorizzato(user_id):
    global _utenti_autorizzati_cache, _utenti_autorizzati_last_update
    current_time = time.time()
    
    # Verifica se l'utente è un amministratore (non richiede cache)
    if user_id in ADMIN_IDS:
        return True
    
    # Aggiorna la cache degli utenti autorizzati se necessario (ogni 10 secondi)
    if not _utenti_autorizzati_cache or (current_time - _utenti_autorizzati_last_update) > 10:
        utenti = carica_utenti()
        _utenti_autorizzati_cache = {}
        
        # Popola la cache con gli ID degli utenti autorizzati
        for utente in utenti["autorizzati"]:
            if isinstance(utente, dict):
                _utenti_autorizzati_cache[utente.get("id")] = True
            else:
                _utenti_autorizzati_cache[utente] = True
                
        _utenti_autorizzati_last_update = current_time
    
    # Verifica se l'utente è nella cache degli autorizzati
    return _utenti_autorizzati_cache.get(user_id, False)

# Funzione per verificare se un utente è amministratore
def is_admin(user_id):
    return user_id in ADMIN_IDS

# Le funzioni carica_reazioni e salva_reazioni sono ora importate dal modulo data_manager

# Funzione per aggiungere una reazione
def aggiungi_reazione(message_id, user_id, user_name, reaction_type):
    """Aggiunge una reazione a un messaggio."""
    reazioni = carica_reazioni()
    
    # Converti message_id in stringa per usarlo come chiave del dizionario
    message_id_str = str(message_id)
    
    # Inizializza la struttura per il messaggio se non esiste
    if message_id_str not in reazioni:
        reazioni[message_id_str] = {
            "like": [],
            "love": [],
            "fire": [],
            "clap": [],
            "rugby": []
        }
    
    # Rimuovi l'utente da tutte le reazioni per questo messaggio
    for tipo in reazioni[message_id_str]:
        reazioni[message_id_str][tipo] = [r for r in reazioni[message_id_str][tipo] if r["id"] != user_id]
    
    # Aggiungi la nuova reazione
    reazioni[message_id_str][reaction_type].append({
        "id": user_id,
        "name": user_name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Salva le reazioni
    salva_reazioni(reazioni)
    
    # Restituisci il conteggio delle reazioni per questo messaggio
    return {tipo: len(utenti) for tipo, utenti in reazioni[message_id_str].items()}

# Funzione per verificare la congruenza tra punteggio e mete
def verifica_congruenza_punteggio_mete(punteggio, mete):
    """
    Verifica che il punteggio sia congruente con il numero di mete.
    
    Regole:
    - Una meta vale 5 punti
    - Una trasformazione (dopo meta) vale 2 punti
    - Un calcio di punizione vale 3 punti
    - Un drop vale 3 punti
    
    Quindi il punteggio minimo per n mete è 5*n, e il massimo è 7*n + altri punti.
    Consideriamo ragionevole un massimo di 5 calci/drop (15 punti) oltre alle mete.
    """
    # Punteggio minimo: 5 punti per meta
    punteggio_minimo = mete * 5
    
    # Punteggio massimo: 7 punti per meta (meta + trasformazione) + 15 punti (5 calci/drop)
    punteggio_massimo = mete * 7 + 15
    
    # Se non ci sono mete, il punteggio deve essere divisibile per 3 (calci/drop)
    if mete == 0 and punteggio % 3 != 0:
        return False, f"Con 0 mete, il punteggio dovrebbe essere divisibile per 3 (calci/drop da 3 punti)"
    
    # Verifica che il punteggio sia nell'intervallo ragionevole
    if punteggio < punteggio_minimo:
        return False, f"Il punteggio ({punteggio}) è troppo basso per {mete} mete (minimo {punteggio_minimo})"
    
    if punteggio > punteggio_massimo:
        return False, f"Il punteggio ({punteggio}) sembra troppo alto per {mete} mete (massimo ragionevole {punteggio_massimo})"
    
    return True, "Punteggio congruente con le mete"

# Comando /dashboard per mostrare la dashboard personalizzata
async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra la dashboard personalizzata dell'utente."""
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    # Verifica che l'utente sia autorizzato
    if not is_utente_autorizzato(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Non sei autorizzato a utilizzare questo comando.\n"
            "Usa /start per richiedere l'accesso.",
            parse_mode='HTML'
        )
        return
    
    # Carica i risultati
    risultati = carica_risultati()
    
    # Filtra i risultati inseriti dall'utente
    risultati_utente = [r for r in risultati if r.get('inserito_da') == user_name]
    
    # Ordina i risultati per data (più recenti prima)
    risultati_utente.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Prendi solo gli ultimi 5 risultati
    ultimi_risultati = risultati_utente[:5]
    
    # Calcola statistiche dell'utente
    num_partite_inserite = len(risultati_utente)
    
    # Trova le squadre più inserite dall'utente
    squadre_count = {}
    for r in risultati_utente:
        squadra1 = r.get('squadra1', 'N/D')
        squadra2 = r.get('squadra2', 'N/D')
        squadre_count[squadra1] = squadre_count.get(squadra1, 0) + 1
        squadre_count[squadra2] = squadre_count.get(squadra2, 0) + 1
    
    # Trova le 3 squadre più inserite
    top_squadre = sorted(squadre_count.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Calcola la percentuale di contributo dell'utente
    percentuale_contributo = (num_partite_inserite / len(risultati) * 100) if risultati else 0
    
    # Crea il messaggio della dashboard
    messaggio = f"🏉 <b>DASHBOARD PERSONALE</b> 🏉\n\n"
    messaggio += f"👋 Ciao <b>{user_name}</b>!\n\n"
    
    messaggio += f"📊 <b>LE TUE STATISTICHE</b>\n"
    messaggio += f"• Partite inserite: <b>{num_partite_inserite}</b>\n"
    messaggio += f"• Contributo totale: <b>{percentuale_contributo:.1f}%</b>\n\n"
    
    if top_squadre:
        messaggio += "<b>LE TUE SQUADRE PIÙ INSERITE</b>\n"
        for squadra, count in top_squadre:
            messaggio += f"• {squadra}: <b>{count}</b> partite\n"
        messaggio += "\n"
    
    if ultimi_risultati:
        messaggio += "<b>LE TUE ULTIME PARTITE INSERITE</b>\n"
        for i, r in enumerate(ultimi_risultati, 1):
            data = r.get('data_partita', 'N/D')
            if r.get('tipo_partita') == 'triangolare':
                messaggio += f"{i}. <b>{data}</b> - Triangolare {r.get('categoria')} {r.get('genere')}\n"
                messaggio += f"   {r.get('squadra1')}, {r.get('squadra2')}, {r.get('squadra3')}\n"
            else:
                messaggio += f"{i}. <b>{data}</b> - {r.get('categoria')} {r.get('genere')}\n"
                messaggio += f"   {r.get('squadra1')} {r.get('punteggio1', 0)}-{r.get('punteggio2', 0)} {r.get('squadra2')}\n"
    else:
        messaggio += "<i>Non hai ancora inserito partite.</i>\n\n"
    
    # Crea i pulsanti per le azioni rapide
    keyboard = [
        [
            InlineKeyboardButton("🆕 Nuova Partita", callback_data="dashboard_nuova"),
            InlineKeyboardButton("📋 Risultati", callback_data="dashboard_risultati")
        ],
        [
            InlineKeyboardButton("📊 Statistiche", callback_data="dashboard_statistiche"),
            InlineKeyboardButton("⚙️ Menu Principale", callback_data="dashboard_menu")
        ]
    ]
    
    # Aggiungi pulsanti per esportazione solo per gli admin
    if is_admin(user_id):
        keyboard.append([
            InlineKeyboardButton("📊 Esporta Excel", callback_data="dashboard_excel"),
            InlineKeyboardButton("📄 Esporta PDF", callback_data="dashboard_pdf")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        # Handle the case where update.callback_query exists
        if not is_utente_autorizzato(user_id):
            await update.callback_query.answer("Non sei autorizzato a utilizzare questa funzione.")
            await update.callback_query.edit_message_text(
                "⚠️ <b>Accesso non autorizzato</b>\n\n"
                "Non sei autorizzato a utilizzare questo comando.\n"
                "Usa /start per richiedere l'accesso.",
                parse_mode='HTML'
            )
            return
        
        await update.callback_query.message.edit_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        # Handle the non-callback query case
        await update.message.reply_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

# Comando /menu
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra un menu con tutte le funzioni disponibili."""
    user_id = update.effective_user.id
    
    # Verifica che l'utente sia autorizzato
    if not is_utente_autorizzato(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Non sei autorizzato a utilizzare questo comando.\n"
            "Usa /start per richiedere l'accesso.",
            parse_mode='HTML'
        )
        return
    
    # Crea i pulsanti per le funzioni standard
    keyboard = [
        [InlineKeyboardButton("📝 Inserisci nuova partita", callback_data="menu_nuova")],
        [InlineKeyboardButton("🏁 Ultimi risultati", callback_data="menu_risultati")],
        [InlineKeyboardButton("📊 Statistiche", callback_data="menu_statistiche")],
        [InlineKeyboardButton("👤 Dashboard personale", callback_data="menu_dashboard")]
    ]
    
    # Aggiungi il pulsante per il riepilogo weekend solo per gli admin
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🗓️ Riepilogo weekend", callback_data="menu_riepilogo_weekend")])
    
    # Aggiungi pulsanti per le funzioni amministrative se l'utente è un admin
    if is_admin(user_id):
        keyboard.extend([
            [InlineKeyboardButton("👥 Gestione utenti", callback_data="menu_utenti")],
            [InlineKeyboardButton("🏉 Gestione squadre", callback_data="menu_squadre")],
            [InlineKeyboardButton("🔄 Test canale", callback_data="menu_test_canale")]
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        "<b>🏉 MENU PRINCIPALE</b>\n\n"
        "Seleziona una funzione:",
        reply_markup=reply_markup
    )

# Funzione per creare i pulsanti di reazione per i messaggi del canale
# Funzione crea_pulsanti_reazione è stata spostata in modules/message_manager.py
from modules.message_manager import crea_pulsanti_reazione

# Funzione per inviare un risultato di partita (versione asincrona per l'interfaccia web)
async def invia_risultato_partita(bot, risultato):
    """Invia un messaggio con il risultato della partita al canale Telegram (versione asincrona)."""
    try:
        # Verifica che l'ID del canale sia stato configurato correttamente
        if CHANNEL_ID == "@nome_canale" or not CHANNEL_ID:
            logger.error("ID del canale Telegram non configurato correttamente. Modifica la costante CHANNEL_ID nel file bot.py.")
            return None
        
        # Formatta il messaggio
        genere = risultato.get('genere', '')
        categoria = risultato.get('categoria', '')
        tipo_partita = risultato.get('tipo_partita', 'normale')
        info_categoria = f"{categoria} {genere}".strip()
        
        # Ottieni la data della partita, se disponibile
        data_partita = risultato.get('data_partita', 'N/D')
        
        # Crea il messaggio con un layout più compatto e chiaro
        messaggio = f"🏉 <b>{info_categoria}</b> 🏉\n"
        if tipo_partita == 'triangolare':
            messaggio += f"📅 <i>{data_partita}</i> - <b>TRIANGOLARE</b>\n"
        else:
            messaggio += f"📅 <i>{data_partita}</i>\n"
        messaggio += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        
        # Gestione diversa per triangolari e partite normali
        if tipo_partita == 'triangolare':
            # Log per debug
            logger.info(f"Formattazione messaggio per triangolare: {risultato['squadra1']} vs {risultato['squadra2']} vs {risultato['squadra3']}")
            
            # Verifica che tutti i dati necessari siano presenti
            for key in ['partita1_punteggio1', 'partita1_punteggio2', 'partita2_punteggio1', 'partita2_punteggio2', 
                       'partita3_punteggio1', 'partita3_punteggio2', 'partita1_mete1', 'partita1_mete2', 
                       'partita2_mete1', 'partita2_mete2', 'partita3_mete1', 'partita3_mete2']:
                if key not in risultato:
                    logger.error(f"Manca il campo {key} nei dati del triangolare")
                    return None
                
                # Assicurati che i valori siano numeri interi
                if key.startswith('partita') and key.endswith(('punteggio1', 'punteggio2', 'mete1', 'mete2')):
                    try:
                        risultato[key] = int(risultato[key])
                    except (ValueError, TypeError):
                        logger.error(f"Il campo {key} non è un numero valido: {risultato[key]}")
                        return None
            
            # Formatta le partite del triangolare
            messaggio += f"<b>Squadre partecipanti:</b>\n"
            messaggio += f"• {risultato['squadra1']}\n"
            messaggio += f"• {risultato['squadra2']}\n"
            messaggio += f"• {risultato['squadra3']}\n\n"
            
            messaggio += f"<b>Risultati:</b>\n"
            
            # Partita 1: Squadra1 vs Squadra2
            punteggio1 = risultato['partita1_punteggio1']
            punteggio2 = risultato['partita1_punteggio2']
            mete1 = risultato['partita1_mete1']
            mete2 = risultato['partita1_mete2']
            
            if punteggio1 > punteggio2:
                messaggio += f"• <b>{risultato['squadra1']}</b> <code>{punteggio1}:{punteggio2}</code> {risultato['squadra2']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"• {risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> <b>{risultato['squadra2']}</b> 🏆\n"
            else:
                messaggio += f"• {risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> {risultato['squadra2']} 🤝\n"
            
            # Partita 2: Squadra1 vs Squadra3
            punteggio1 = risultato['partita2_punteggio1']
            punteggio2 = risultato['partita2_punteggio2']
            mete1 = risultato['partita2_mete1']
            mete2 = risultato['partita2_mete2']
            
            if punteggio1 > punteggio2:
                messaggio += f"• <b>{risultato['squadra1']}</b> <code>{punteggio1}:{punteggio2}</code> {risultato['squadra3']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"• {risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> <b>{risultato['squadra3']}</b> 🏆\n"
            else:
                messaggio += f"• {risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> {risultato['squadra3']} 🤝\n"
            
            # Partita 3: Squadra2 vs Squadra3
            punteggio1 = risultato['partita3_punteggio1']
            punteggio2 = risultato['partita3_punteggio2']
            mete1 = risultato['partita3_mete1']
            mete2 = risultato['partita3_mete2']
            
            if punteggio1 > punteggio2:
                messaggio += f"• <b>{risultato['squadra2']}</b> <code>{punteggio1}:{punteggio2}</code> {risultato['squadra3']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"• {risultato['squadra2']} <code>{punteggio1}:{punteggio2}</code> <b>{risultato['squadra3']}</b> 🏆\n"
            else:
                messaggio += f"• {risultato['squadra2']} <code>{punteggio1}:{punteggio2}</code> {risultato['squadra3']} 🤝\n"
            
        else:
            # Partita normale
            punteggio1 = int(risultato.get('punteggio1', 0))
            punteggio2 = int(risultato.get('punteggio2', 0))
            mete1 = int(risultato.get('mete1', 0))
            mete2 = int(risultato.get('mete2', 0))
            
            # Determina il vincitore
            if punteggio1 > punteggio2:
                messaggio += f"<b>{risultato['squadra1']}</b> <code>{punteggio1}:{punteggio2}</code> {risultato['squadra2']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"{risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> <b>{risultato['squadra2']}</b> 🏆\n"
            else:
                messaggio += f"{risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> {risultato['squadra2']} 🤝\n"
            
            # Aggiungi informazioni sulle mete
            messaggio += f"<i>Mete:</i> {mete1} - {mete2}\n"
        
        # Aggiungi informazioni sull'arbitro se disponibili
        arbitro = risultato.get('arbitro', '')
        if arbitro:
            messaggio += f"\n<i>Arbitro:</i> {arbitro}\n"
        
        # Aggiungi un disclaimer
        messaggio += "\n<i>⚠️ Risultato in attesa di omologazione ufficiale</i>"
        
        # Crea i pulsanti di reazione
        keyboard = crea_pulsanti_reazione()
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Invia il messaggio al canale
        sent_message = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=messaggio,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Salva l'ID del messaggio e aggiorna i pulsanti con l'ID
        message_id = sent_message.message_id
        keyboard = crea_pulsanti_reazione(message_id)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=message_id,
            reply_markup=reply_markup
        )
        
        # Inizializza le reazioni per questo messaggio
        reazioni = carica_reazioni()
        message_id_str = str(message_id)
        if message_id_str not in reazioni:
            reazioni[message_id_str] = {
                "like": [],
                "love": [],
                "fire": [],
                "clap": [],
                "rugby": []
            }
            salva_reazioni(reazioni)
        
        logger.info(f"Messaggio inviato al canale {CHANNEL_ID} con ID {message_id}")
        return sent_message
    
    except Exception as e:
        logger.error(f"Errore nell'invio del messaggio al canale: {e}")
        return None

# Funzione per inviare un messaggio al canale Telegram
# Funzione invia_messaggio_canale è stata spostata in modules/message_manager.py
from modules.message_manager import invia_messaggio_canale

# Funzione per generare il riepilogo del weekend
def genera_riepilogo_weekend():
    """Genera un riepilogo delle partite del weekend corrente o precedente."""
    risultati = carica_risultati()
    
    if not risultati:
        return None, None, None, []
    
    # Ottieni la data corrente
    oggi = datetime.now()
    
    # Calcola l'inizio e la fine del weekend corrente (venerdì, sabato, domenica)
    giorno_settimana = oggi.weekday()  # 0 = lunedì, 6 = domenica
    
    # Se oggi è lunedì, martedì, mercoledì o giovedì, mostra il weekend precedente
    if giorno_settimana < 4:  # lunedì, martedì, mercoledì, giovedì
        # Calcola il venerdì della settimana precedente
        giorni_da_venerdi_scorso = giorno_settimana + 3  # +3 perché venerdì è 4 giorni prima di lunedì
        inizio_weekend = oggi - timedelta(days=giorni_da_venerdi_scorso)
        fine_weekend = inizio_weekend + timedelta(days=2)  # domenica
    else:  # venerdì, sabato, domenica
        # Calcola il venerdì di questa settimana
        giorni_da_venerdi = giorno_settimana - 4  # -4 perché venerdì è il giorno 4 della settimana
        inizio_weekend = oggi - timedelta(days=giorni_da_venerdi)
        fine_weekend = inizio_weekend + timedelta(days=2)  # domenica
    
    # Formatta le date per il confronto
    inizio_weekend_str = inizio_weekend.strftime("%d/%m/%Y")
    fine_weekend_str = fine_weekend.strftime("%d/%m/%Y")
    
    # Filtra i risultati per il weekend
    risultati_weekend = []
    for r in risultati:
        try:
            data_partita_raw = r.get('data_partita')
            if data_partita_raw is None or data_partita_raw == '':
                # Salta i risultati senza data
                continue
                
            data_partita = datetime.strptime(data_partita_raw, '%d/%m/%Y')
            data_partita_str = data_partita.strftime("%d/%m/%Y")
            
            # Verifica se la data è nel weekend
            if inizio_weekend_str <= data_partita_str <= fine_weekend_str:
                risultati_weekend.append(r)
        except ValueError:
            # Ignora le date in formato non valido
            continue
    
    if not risultati_weekend:
        return inizio_weekend_str, fine_weekend_str, None, []
    
    # Ordina i risultati per categoria e data
    risultati_weekend.sort(key=lambda x: (x.get('categoria', ''), x.get('data_partita', '')))
    
    # Raggruppa i risultati per categoria
    risultati_per_categoria = {}
    for r in risultati_weekend:
        categoria = r.get('categoria', 'Altra categoria')
        genere = r.get('genere', '')
        key = f"{categoria} {genere}".strip()
        
        if key not in risultati_per_categoria:
            risultati_per_categoria[key] = []
        
        risultati_per_categoria[key].append(r)
    
    # Usa la funzione di formattazione migliorata dal modulo message_manager
    from modules.message_manager import formatta_messaggio_riepilogo_weekend
    
    # Formatta le date per il messaggio
    inizio_weekend_str_format = inizio_weekend.strftime('%d/%m/%Y')
    fine_weekend_str_format = fine_weekend.strftime('%d/%m/%Y')
    
    # Usa la funzione migliorata per formattare il messaggio
    messaggio = formatta_messaggio_riepilogo_weekend(risultati_weekend, inizio_weekend_str_format, fine_weekend_str_format)
    

    
    return inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend

# Callback per esportare il riepilogo in Excel
async def esporta_excel_riepilogo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Esporta il riepilogo del weekend in formato Excel."""
    query = update.callback_query
    await query.answer()
    
    # Verifica che l'utente sia autorizzato
    if not is_utente_autorizzato(query.from_user.id):
        await query.edit_message_text(
            "⚠️ Solo gli utenti autorizzati possono esportare il riepilogo.",
            parse_mode='HTML'
        )
        return
    
    # Genera il riepilogo
    inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
    
    if not messaggio or not risultati_weekend:
        await query.edit_message_text(
            "⚠️ Nessun risultato trovato per il weekend corrente o precedente.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )
        return
    
    # Genera il file Excel
    try:
        excel_buffer = genera_excel_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
        
        # Crea un nome per il file
        inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
        fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
        filename = f"Riepilogo_Rugby_{inizio_weekend.strftime('%d-%m-%Y')}_{fine_weekend.strftime('%d-%m-%Y')}.xlsx"
        
        # Invia il file all'utente
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=excel_buffer,
            filename=filename,
            caption=f"📊 Riepilogo weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')} in formato Excel"
        )
        
        # Invia un messaggio di conferma
        await query.edit_message_text(
            f"✅ <b>File Excel inviato!</b>\n\n"
            f"Il riepilogo del weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')} "
            f"è stato inviato in formato Excel.\n\n"
            f"<i>Controlla i messaggi privati del bot per scaricare il file.</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )
    except Exception as e:
        logger.error(f"Errore durante la generazione del file Excel: {e}")
        await query.edit_message_text(
            "⚠️ Si è verificato un errore durante la generazione del file Excel.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )

# Callback per esportare il riepilogo in PDF
async def esporta_pdf_riepilogo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Esporta il riepilogo del weekend in formato PDF."""
    query = update.callback_query
    await query.answer()
    
    # Verifica che l'utente sia autorizzato
    if not is_utente_autorizzato(query.from_user.id):
        await query.edit_message_text(
            "⚠️ Solo gli utenti autorizzati possono esportare il riepilogo.",
            parse_mode='HTML'
        )
        return
    
    # Genera il riepilogo
    inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
    
    if not messaggio or not risultati_weekend:
        await query.edit_message_text(
            "⚠️ Nessun risultato trovato per il weekend corrente o precedente.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )
        return
    
    # Genera il file PDF
    try:
        pdf_buffer = genera_pdf_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
        
        # Crea un nome per il file
        inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
        fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
        filename = f"Riepilogo_Rugby_{inizio_weekend.strftime('%d-%m-%Y')}_{fine_weekend.strftime('%d-%m-%Y')}.pdf"
        
        # Invia il file all'utente
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=pdf_buffer,
            filename=filename,
            caption=f"📄 Riepilogo weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')} in formato PDF"
        )
        
        # Invia un messaggio di conferma
        await query.edit_message_text(
            f"✅ <b>File PDF inviato!</b>\n\n"
            f"Il riepilogo del weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')} "
            f"è stato inviato in formato PDF.\n\n"
            f"<i>Controlla i messaggi privati del bot per scaricare il file.</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )
    except Exception as e:
        logger.error(f"Errore durante la generazione del file PDF: {e}")
        await query.edit_message_text(
            "⚠️ Si è verificato un errore durante la generazione del file PDF.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )

# Callback per pubblicare il riepilogo sul canale
async def pubblica_riepilogo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pubblica il riepilogo del weekend sul canale."""
    query = update.callback_query
    await query.answer()
    
    # Verifica che l'utente sia un amministratore
    if not is_admin(query.from_user.id):
        await query.edit_message_text(
            "⚠️ Solo gli amministratori possono pubblicare il riepilogo sul canale.",
            parse_mode='HTML'
        )
        return
    
    # Genera il riepilogo
    inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
    
    if not messaggio:
        await query.edit_message_text(
            f"Non ci sono risultati per il weekend {inizio_weekend_str} - {fine_weekend_str}.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )
        return
    
    try:
        # Verifica che l'ID del canale sia stato configurato correttamente
        if CHANNEL_ID == "@nome_canale" or not CHANNEL_ID:
            await query.edit_message_text(
                "⚠️ ID del canale Telegram non configurato correttamente. Modifica la costante CHANNEL_ID nel file bot.py.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
            return
        
        # Prova a ottenere informazioni sul canale per verificare che il bot abbia accesso
        try:
            chat = await context.bot.get_chat(CHANNEL_ID)
            logger.info(f"Connessione al canale riuscita: {chat.title}")
        except Exception as chat_error:
            await query.edit_message_text(
                f"⚠️ Impossibile accedere al canale {CHANNEL_ID}: {chat_error}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
            return
        
        # Crea i pulsanti di reazione con opzioni di esportazione per il riepilogo del weekend
        keyboard = crea_pulsanti_reazione(include_export=True)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Invia il messaggio al canale con i pulsanti di reazione e di esportazione
        sent_message = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=messaggio,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Salva l'ID del messaggio e aggiorna i pulsanti con l'ID
        message_id = sent_message.message_id
        keyboard = crea_pulsanti_reazione(message_id, include_export=True)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=message_id,
            reply_markup=reply_markup
        )
        
        # Notifica l'utente
        await query.edit_message_text(
            f"✅ Riepilogo del weekend {inizio_weekend_str} - {fine_weekend_str} pubblicato con successo sul canale {chat.title}!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )
        
        logger.info(f"Riepilogo del weekend pubblicato con successo sul canale {CHANNEL_ID}")
    except Exception as e:
        # Notifica l'errore
        await query.edit_message_text(
            f"❌ Errore durante la pubblicazione del riepilogo: {e}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )

# Funzione per inviare automaticamente il riepilogo del weekend
async def invia_riepilogo_automatico(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia automaticamente il riepilogo del weekend al canale."""
    # Genera il riepilogo
    inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
    
    if not messaggio:
        logger.info(f"Nessun risultato trovato per il weekend {inizio_weekend_str} - {fine_weekend_str}. Riepilogo non inviato.")
        return
    
    try:
        # Verifica che l'ID del canale sia stato configurato correttamente
        if CHANNEL_ID == "@nome_canale" or not CHANNEL_ID:
            logger.error("ID del canale Telegram non configurato correttamente. Modifica la costante CHANNEL_ID nel file bot.py.")
            return
        
        # Prova a ottenere informazioni sul canale per verificare che il bot abbia accesso
        try:
            chat = await context.bot.get_chat(CHANNEL_ID)
            logger.info(f"Connessione al canale riuscita: {chat.title}")
        except Exception as chat_error:
            logger.error(f"Impossibile accedere al canale {CHANNEL_ID}: {chat_error}")
            return
            
        # Crea i pulsanti di reazione con opzioni di esportazione per il riepilogo del weekend
        keyboard = crea_pulsanti_reazione(include_export=True)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Invia il messaggio al canale con i pulsanti di reazione e di esportazione
        sent_message = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=messaggio,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Salva l'ID del messaggio e aggiorna i pulsanti con l'ID
        message_id = sent_message.message_id
        keyboard = crea_pulsanti_reazione(message_id, include_export=True)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=message_id,
            reply_markup=reply_markup
        )
        
        logger.info(f"Riepilogo del weekend pubblicato automaticamente sul canale {CHANNEL_ID}")
        
        # Genera e invia anche i file Excel e PDF
        try:
            # Genera il file Excel
            excel_buffer = genera_excel_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
            
            # Crea un nome per il file Excel
            inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
            fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
            excel_filename = f"Riepilogo_Rugby_{inizio_weekend.strftime('%d-%m-%Y')}_{fine_weekend.strftime('%d-%m-%Y')}.xlsx"
            
            # Invia il file Excel al canale
            await context.bot.send_document(
                chat_id=CHANNEL_ID,
                document=excel_buffer,
                filename=excel_filename,
                caption=f"📊 Riepilogo weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')} in formato Excel"
            )
            
            logger.info(f"File Excel inviato automaticamente al canale {CHANNEL_ID}")
            
            # Genera il file PDF
            pdf_buffer = genera_pdf_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
            
            # Crea un nome per il file PDF
            pdf_filename = f"Riepilogo_Rugby_{inizio_weekend.strftime('%d-%m-%Y')}_{fine_weekend.strftime('%d-%m-%Y')}.pdf"
            
            # Invia il file PDF al canale
            await context.bot.send_document(
                chat_id=CHANNEL_ID,
                document=pdf_buffer,
                filename=pdf_filename,
                caption=f"📄 Riepilogo weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')} in formato PDF"
            )
            
            logger.info(f"File PDF inviato automaticamente al canale {CHANNEL_ID}")
        except Exception as file_error:
            logger.error(f"Errore durante l'invio automatico dei file: {file_error}")
    except Exception as e:
        logger.error(f"Errore durante l'invio automatico del riepilogo: {e}")

# Callback per gestire le reazioni ai messaggi
async def reaction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce le reazioni ai messaggi."""
    query = update.callback_query
    await query.answer()
    
    # Estrai il tipo di callback
    callback_data = query.data
    
    if callback_data.startswith("reaction:"):
        # Formato: "reaction:tipo:message_id"
        parts = callback_data.split(":")
        if len(parts) < 3:
            await query.answer("Dati di callback non validi", show_alert=True)
            return
            
        reaction_type = parts[1]
        message_id = int(parts[2])
        
        # Aggiungi la reazione
        user_id = query.from_user.id
        user_name = f"{query.from_user.first_name} {query.from_user.last_name if query.from_user.last_name else ''}".strip()
        
        # Aggiungi la reazione e ottieni il conteggio aggiornato
        conteggio = aggiungi_reazione(message_id, user_id, user_name, reaction_type)
        
        # Crea un messaggio di conferma
        emoji_map = {
            "like": "👍",
            "love": "❤️",
            "fire": "🔥",
            "clap": "👏",
            "rugby": "🏉"
        }
        emoji = emoji_map.get(reaction_type, "")
        
        await query.answer(f"Hai reagito con {emoji} {reaction_type.capitalize()}", show_alert=False)
        
    elif callback_data.startswith("view_reactions:"):
        # Formato: "view_reactions:message_id"
        parts = callback_data.split(":")
        if len(parts) < 2:
            await query.answer("Dati di callback non validi", show_alert=True)
            return
            
        message_id = int(parts[1])
        
        # Carica le reazioni per questo messaggio
        reazioni = carica_reazioni()
        message_id_str = str(message_id)
        
        if message_id_str not in reazioni:
            await query.answer("Nessuna reazione per questo messaggio", show_alert=True)
            return
        
        # Crea un messaggio con le reazioni
        messaggio = "<b>🔍 Chi ha reagito:</b>\n\n"
        
        # Emoji per ogni tipo di reazione
        emoji_map = {
            "like": "👍",
            "love": "❤️",
            "fire": "🔥",
            "clap": "👏",
            "rugby": "🏉"
        }
        
        # Aggiungi le reazioni al messaggio
        for tipo, utenti in reazioni[message_id_str].items():
            if utenti:
                emoji = emoji_map.get(tipo, "")
                messaggio += f"<b>{emoji} {tipo.capitalize()}:</b>\n"
                for utente in utenti:
                    messaggio += f"• {utente['name']}\n"
                messaggio += "\n"
        
        # Se non ci sono reazioni
        if messaggio == "<b>🔍 Chi ha reagito:</b>\n\n":
            messaggio += "<i>Nessuna reazione finora</i>"
        
        # Mostra il messaggio come alert
        await query.answer(messaggio, show_alert=True)

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un messaggio quando viene eseguito il comando /start."""
    user = update.effective_user
    user_id = update.effective_user.id
    
    # Verifica se l'utente è già autorizzato
    if is_utente_autorizzato(user_id):
        await update.message.reply_html(
            f"🏉 <b>Benvenuto nel Bot partite del CRV Rugby!</b> 🏉\n\n"
            f"Ciao {user.mention_html()}! Questo bot ti aiuterà a registrare i risultati delle partite di rugby del nostro Comitato.\n\n"
            f"Usa /menu per visualizzare tutte le funzioni disponibili\n"
            f"Usa /dashboard per accedere alla tua dashboard personale\n"
            f"Usa /nuova per inserire una nuova partita\n"
            f"Usa /risultati per vedere le ultime partite inserite"
        )
    else:
        pass  # Add a valid statement or logic here if needed
        # Verifica se l'utente è già in attesa di approvazione
        utenti = carica_utenti()
        utente_in_attesa = False
        for utente in utenti["in_attesa"]:
            if isinstance(utente, dict) and utente.get("id") == user_id:
                utente_in_attesa = True
                break
            elif not isinstance(utente, dict) and utente == user_id:
                utente_in_attesa = True
                break
                
        if utente_in_attesa:
            await update.message.reply_html(
                f"🏉 <b>Benvenuto nel Bot partite del CRV Rugby!</b> 🏉\n\n"
                f"Ciao {user.mention_html()}! La tua richiesta di accesso è in attesa di approvazione.\n\n"
                f"Un amministratore esaminerà la tua richiesta il prima possibile."
            )
        else:
            # Crea un dizionario con i dettagli dell'utente
            data_registrazione = datetime.now().strftime("%d/%m/%Y %H:%M")
            nuovo_utente = {
                "id": user_id,
                "nome": user.full_name,
                "username": user.username,
                "data_registrazione": data_registrazione
            }
            
            # Aggiungi l'utente alla lista di attesa
            utenti["in_attesa"].append(nuovo_utente)
            salva_utenti(utenti)
            
            # Informa l'utente
            await update.message.reply_html(
                f"🏉 <b>Benvenuto nel Bot partite del CRV Rugby!</b> 🏉\n\n"
                f"Ciao {user.mention_html()}! Per utilizzare questo bot è necessaria l'approvazione di un amministratore.\n\n"
                f"La tua richiesta è stata registrata. Riceverai una notifica quando sarai autorizzato."
            )
            
            # Notifica gli amministratori con pulsanti di approvazione/rifiuto
            for admin_id in ADMIN_IDS:
                try:
                    # Crea i pulsanti per approvare o rifiutare
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Approva", callback_data=f"approva_{user_id}"),
                            InlineKeyboardButton("❌ Rifiuta", callback_data=f"rifiuta_{user_id}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🔔 <b>Nuova richiesta di accesso</b>\n\n"
                             f"<b>Utente:</b> {user.full_name}\n"
                             f"<b>Username:</b> @{user.username if user.username else 'Non disponibile'}\n"
                             f"<b>ID:</b> {user_id}\n\n"
                             f"Clicca sui pulsanti qui sotto per approvare o rifiutare la richiesta.",
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Impossibile inviare notifica all'amministratore {admin_id}: {e}")

# Comando /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un messaggio quando viene emesso il comando /help."""
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    is_admin_user = is_admin(user_id)
    
    # Traccia il comando nel monitor
    start_time = bot_monitor.track_command(
        user_id=user_id,
        user_name=user_name,
        command="/help",
        is_admin=is_admin_user
    )
    
    # Verifica che l'utente sia autorizzato
    if not is_utente_autorizzato(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Non sei autorizzato a utilizzare questo comando.\n"
            "Usa /start per richiedere l'accesso.",
            parse_mode='HTML'
        )
        # Traccia l'errore
        bot_monitor.track_error("Accesso non autorizzato", "Tentativo di accesso non autorizzato al comando /help", user_id, "/help")
        return
    
    help_text = (
        "<b>🏉 GUIDA AL BOT</b>\n\n"
        "Questo bot ti permette di inserire e visualizzare i risultati delle partite di rugby del CRV.\n\n"
        "<b>Comandi disponibili:</b>\n"
        "/start - Avvia il bot e richiedi l'accesso\n"
        "/menu - Mostra il menu principale\n"
        "/dashboard - Mostra la tua dashboard personalizzata\n"
        "/nuova - Inserisci una nuova partita\n"
        "/risultati - Visualizza gli ultimi risultati\n"
        "/help - Mostra questo messaggio di aiuto\n"
    )
    
    # Aggiungi comandi admin se l'utente è amministratore
    if is_admin_user:
        help_text += (
            "\n<b>🔐 Comandi amministratore:</b>\n"
            "/utenti - Gestisci gli utenti autorizzati\n"
            "/squadre - Gestisci l'elenco delle squadre\n"
            "/health - Visualizza lo stato di salute del bot\n"
        )
    
    help_text += (
        "\n<b>Come inserire una nuova partita:</b>\n"
        "1. Usa il comando /nuova o seleziona 'Inserisci nuova partita' dal menu\n"
        "2. Seleziona la categoria e il genere della partita\n"
        "3. Seleziona le squadre che hanno giocato\n"
        "4. Inserisci la data della partita (formato: GG/MM/AAAA)\n"
        "5. Inserisci il punteggio e le mete per entrambe le squadre\n"
        "6. Inserisci il nome dell'arbitro\n"
        "7. Conferma i dati inseriti\n\n"
        "<b>Note:</b>\n"
        "- I risultati vengono pubblicati automaticamente sul canale @CRV_Rugby_Risultati_Partite\n"
        "- Solo gli utenti autorizzati possono inserire nuovi risultati\n"
        "- Per problemi o suggerimenti, contatta un amministratore"
    )
    
    await update.message.reply_html(help_text)
    
    # Registra il completamento del comando
    bot_monitor.track_command_completion(start_time)

# Comando /health per mostrare lo stato di salute del bot
async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra lo stato di salute del bot (solo per amministratori)."""
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    # Traccia il comando nel monitor
    start_time = bot_monitor.track_command(
        user_id=user_id,
        user_name=user_name,
        command="/health",
        is_admin=is_admin(user_id)
    )
    
    # Verifica che l'utente sia un amministratore
    if not is_admin(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Solo gli amministratori possono visualizzare lo stato di salute del bot.",
            parse_mode='HTML'
        )
        # Traccia l'errore
        bot_monitor.track_error("Accesso non autorizzato", "Tentativo di accesso non autorizzato al comando /health", user_id, "/health")
        return
    
    # Ottieni e formatta il messaggio di stato
    health_message = bot_monitor.format_health_message()
    
    # Crea pulsanti per azioni aggiuntive
    keyboard = [
        [InlineKeyboardButton("🔄 Aggiorna", callback_data="health_refresh")],
        [
            InlineKeyboardButton("📊 Esporta dati", callback_data="health_export"),
            InlineKeyboardButton("🧹 Pulisci errori", callback_data="health_clear_errors")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Invia il messaggio con i pulsanti
    await update.message.reply_html(
        health_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    # Registra il completamento del comando
    bot_monitor.track_command_completion(start_time)

# Callback per il comando health
async def health_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce i callback del comando health."""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Verifica che l'utente sia un amministratore
    if not is_admin(user_id):
        await query.answer("Solo gli amministratori possono eseguire questa azione.")
        return
    
    await query.answer()
    
    action = query.data.replace("health_", "")
    
    if action == "refresh":
        # Aggiorna le metriche e mostra il messaggio aggiornato
        health_message = bot_monitor.format_health_message()
        
        keyboard = [
            [InlineKeyboardButton("🔄 Aggiorna", callback_data="health_refresh")],
            [
                InlineKeyboardButton("📊 Esporta dati", callback_data="health_export"),
                InlineKeyboardButton("🧹 Pulisci errori", callback_data="health_clear_errors")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            health_message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif action == "export":
        # Esporta i dati di monitoraggio in formato JSON
        health_data = bot_monitor.get_health_status()
        json_data = json.dumps(health_data, indent=2, default=str)
        
        # Crea un file temporaneo
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            temp_file.write(json_data.encode('utf-8'))
            temp_file_path = temp_file.name
        
        # Invia il file JSON
        with open(temp_file_path, 'rb') as file:
            await context.bot.send_document(
                chat_id=user_id,
                document=file,
                filename=f"bot_health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                caption="📊 Dati di monitoraggio del bot"
            )
        
        # Elimina il file temporaneo
        os.unlink(temp_file_path)
        
        await query.edit_message_text(
            "✅ I dati di monitoraggio sono stati esportati con successo.\n\n"
            "Usa il pulsante qui sotto per tornare alla dashboard di monitoraggio.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Torna al monitoraggio", callback_data="health_refresh")]]),
            parse_mode='HTML'
        )
    
    elif action == "clear_errors":
        # Pulisci la cronologia degli errori
        bot_monitor.error_history.clear()
        bot_monitor.metrics['errors'] = 0
        
        await query.edit_message_text(
            "✅ La cronologia degli errori è stata pulita con successo.\n\n"
            "Usa il pulsante qui sotto per tornare alla dashboard di monitoraggio.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Torna al monitoraggio", callback_data="health_refresh")]]),
            parse_mode='HTML'
        )

# Funzione per mostrare le statistiche
async def mostra_statistiche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra le statistiche delle partite."""
    query = update.callback_query
    
    # Carica i risultati
    risultati = carica_risultati()
    
    if not risultati:
        await query.edit_message_text(
            "Non ci sono ancora risultati inseriti per generare statistiche.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]])
        )
        return
    
    # Calcola le statistiche
    totale_partite = len(risultati)
    totale_punti = sum(int(r.get('punteggio1', 0)) + int(r.get('punteggio2', 0)) for r in risultati)
    totale_mete = sum(int(r.get('mete1', 0)) + int(r.get('mete2', 0)) for r in risultati)
    
    # Media punti e mete per partita
    media_punti = totale_punti / totale_partite if totale_partite > 0 else 0
    media_mete = totale_mete / totale_partite if totale_partite > 0 else 0
    
    # Trova la partita con più punti
    partita_max_punti = max(risultati, key=lambda r: int(r.get('punteggio1', 0)) + int(r.get('punteggio2', 0)), default=None)
    
    # Trova la partita con più mete
    partita_max_mete = max(risultati, key=lambda r: int(r.get('mete1', 0)) + int(r.get('mete2', 0)), default=None)
    
    # Conta le partite per categoria
    categorie = {}
    for r in risultati:
        categoria = r.get('categoria', 'N/D')
        genere = r.get('genere', '')
        key = f"{categoria} {genere}".strip()
        categorie[key] = categorie.get(key, 0) + 1
    
    # Squadre con più partite
    squadre_count = {}
    for r in risultati:
        squadra1 = r.get('squadra1', 'N/D')
        squadra2 = r.get('squadra2', 'N/D')
        squadre_count[squadra1] = squadre_count.get(squadra1, 0) + 1
        squadre_count[squadra2] = squadre_count.get(squadra2, 0) + 1
    
    # Trova le 3 squadre con più partite
    top_squadre = sorted(squadre_count.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Crea il messaggio con le statistiche
    messaggio = "<b>📊 STATISTICHE PARTITE</b>\n\n"
    
    messaggio += f"<b>Totale partite:</b> {totale_partite}\n"
    messaggio += f"<b>Totale punti:</b> {totale_punti}\n"
    messaggio += f"<b>Totale mete:</b> {totale_mete}\n"
    messaggio += f"<b>Media punti per partita:</b> {media_punti:.1f}\n"
    messaggio += f"<b>Media mete per partita:</b> {media_mete:.1f}\n\n"
    
    if partita_max_punti:
        punti_max = int(partita_max_punti.get('punteggio1', 0)) + int(partita_max_punti.get('punteggio2', 0))
        messaggio += f"<b>Partita con più punti:</b>\n"
        messaggio += f"  {partita_max_punti.get('squadra1')} {partita_max_punti.get('punteggio1')} - {partita_max_punti.get('punteggio2')} {partita_max_punti.get('squadra2')}\n"
        messaggio += f"  Totale: {punti_max} punti\n\n"
    
    if partita_max_mete:
        mete_max = int(partita_max_mete.get('mete1', 0)) + int(partita_max_mete.get('mete2', 0))
        messaggio += f"<b>Partita con più mete:</b>\n"
        messaggio += f"  {partita_max_mete.get('squadra1')} {partita_max_mete.get('mete1')} - {partita_max_mete.get('mete2')} {partita_max_mete.get('squadra2')}\n"
        messaggio += f"  Totale: {mete_max} mete\n\n"
    
    messaggio += "<b>Partite per categoria:</b>\n"
    for cat, count in sorted(categorie.items(), key=lambda x: x[1], reverse=True):
        messaggio += f"  {cat}: {count}\n"
    
    messaggio += "\n<b>Squadre con più partite:</b>\n"
    for squadra, count in top_squadre:
        messaggio += f"  {squadra}: {count}\n"
    
    # Aggiungi un pulsante per tornare alla dashboard
    keyboard = [[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        messaggio,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# Callback per le azioni della dashboard
async def dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce i callback della dashboard personalizzata."""
    query = update.callback_query
    await query.answer()
    
    azione = query.data.replace("dashboard_", "")
    
    if azione == "nuova":
        # Avvia il processo di inserimento di una nuova partita
        # Questo caso dovrebbe essere gestito dal ConversationHandler, ma aggiungiamo
        # un reindirizzamento esplicito per sicurezza
        await nuova_partita(update, context)
    
    elif azione == "risultati":
        # Mostra gli ultimi risultati
        risultati = carica_risultati()
        
        if not risultati:
            await query.edit_message_text(
                "Non ci sono ancora risultati inseriti.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]])
            )
            return
        
        # Mostra gli ultimi 5 risultati
        messaggio = "<b>📋 ULTIMI RISULTATI</b>\n\n"
        
        # Ordina i risultati per data (dal più recente)
        def get_date_key(x):
            data_partita = x.get('data_partita')
            if data_partita is None or data_partita == '':
                return datetime.strptime('01/01/2000', '%d/%m/%Y')
            try:
                return datetime.strptime(data_partita, '%d/%m/%Y')
            except ValueError:
                # In caso di formato data non valido, usa una data predefinita
                return datetime.strptime('01/01/2000', '%d/%m/%Y')
        
        risultati_ordinati = sorted(
            risultati, 
            key=get_date_key,
            reverse=True
        )
        
        # Prendi gli ultimi 5 risultati
        ultimi_risultati = risultati_ordinati[:5]
        
        for i, risultato in enumerate(ultimi_risultati, 1):
            categoria = risultato.get('categoria', 'N/D')
            genere = risultato.get('genere', '')
            info_categoria = f"{categoria} {genere}".strip()
            
            messaggio += f"{i}. <b>{info_categoria}</b> - {risultato.get('data_partita', 'N/D')}\n"
            messaggio += f"   <b>{risultato['squadra1']}</b> {risultato['punteggio1']} - {risultato['punteggio2']} <b>{risultato['squadra2']}</b>\n"
            messaggio += f"   Mete: {risultato['mete1']} - {risultato['mete2']}\n\n"
        
        # Aggiungi un pulsante per tornare alla dashboard
        keyboard = [[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif azione == "statistiche":
        # Mostra le statistiche
        await mostra_statistiche(update, context)
    
    elif azione == "menu":
        # Mostra il menu principale
        # Crea i pulsanti per le funzioni standard
        keyboard = [
            [InlineKeyboardButton("📝 Inserisci nuova partita", callback_data="menu_nuova")],
            [InlineKeyboardButton("🏁 Ultimi risultati", callback_data="menu_risultati")],
            [InlineKeyboardButton("📊 Statistiche", callback_data="menu_statistiche")]
        ]
        
        # Aggiungi il pulsante per il riepilogo weekend solo per gli admin
        if is_admin(query.from_user.id):
            keyboard.append([InlineKeyboardButton("🗓️ Riepilogo weekend", callback_data="menu_riepilogo_weekend")])
        
        # Aggiungi pulsanti per le funzioni amministrative se l'utente è un admin
        if is_admin(query.from_user.id):
            keyboard.extend([
                [InlineKeyboardButton("👥 Gestione utenti", callback_data="menu_utenti")],
                [InlineKeyboardButton("🔄 Test canale", callback_data="menu_test_canale")]
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "<b>🏉 MENU PRINCIPALE</b>\n\n"
            "Seleziona una funzione:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif azione == "excel":
        # Verifica che l'utente sia un amministratore
        if not is_admin(query.from_user.id):
            await query.edit_message_text(
                "⚠️ Solo gli amministratori possono esportare i dati in Excel.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]])
            )
            return
        
        # Genera il riepilogo direttamente qui invece di reindirizzare
        inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
        
        if not messaggio or not risultati_weekend:
            await query.edit_message_text(
                "⚠️ Nessun risultato trovato per il weekend corrente o precedente.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]])
            )
            return
        
        # Genera il file Excel
        try:
            # Mostra messaggio di attesa
            await query.edit_message_text(
                "⏳ Generazione del file Excel in corso...",
                parse_mode='HTML'
            )
            
            # Genera il file Excel
            excel_buffer = genera_excel_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
            
            # Crea un nome per il file Excel
            inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
            fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
            excel_filename = f"Riepilogo_Rugby_{inizio_weekend.strftime('%d-%m-%Y')}_{fine_weekend.strftime('%d-%m-%Y')}.xlsx"
            
            # Assicurati che il puntatore sia all'inizio del buffer
            excel_buffer.seek(0)
            
            # Crea un file temporaneo per salvare il contenuto del buffer
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
                temp_file.write(excel_buffer.getvalue())
                temp_path = temp_file.name
            
            # Invia il file Excel all'utente
            try:
                await context.bot.send_document(
                    chat_id=query.from_user.id,
                    document=open(temp_path, 'rb'),
                    filename=excel_filename,
                    caption=f"📊 Riepilogo weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')} in formato Excel"
                )
                # Elimina il file temporaneo dopo l'invio
                os.unlink(temp_path)
            except Exception as e:
                logger.error(f"Errore nell'invio del file Excel: {e}")
                # Assicurati di eliminare il file temporaneo anche in caso di errore
                os.unlink(temp_path)
                raise
            
            # Aggiorna il messaggio
            await query.edit_message_text(
                "✅ File Excel generato e inviato con successo!",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]])
            )
        except Exception as e:
            logger.error(f"Errore durante la generazione del file Excel: {e}")
            await query.edit_message_text(
                f"❌ Errore durante la generazione del file Excel: {e}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]])
            )
    
    elif azione == "pdf":
        # Verifica che l'utente sia un amministratore
        if not is_admin(query.from_user.id):
            await query.edit_message_text(
                "⚠️ Solo gli amministratori possono esportare i dati in PDF.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]])
            )
            return
        
        # Genera il riepilogo direttamente qui invece di reindirizzare
        inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
        
        if not messaggio or not risultati_weekend:
            await query.edit_message_text(
                "⚠️ Nessun risultato trovato per il weekend corrente o precedente.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]])
            )
            return
        
        # Genera il file PDF
        try:
            # Mostra messaggio di attesa
            await query.edit_message_text(
                "⏳ Generazione del file PDF in corso...",
                parse_mode='HTML'
            )
            
            # Genera il file PDF
            pdf_buffer = genera_pdf_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
            
            # Crea un nome per il file PDF
            inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
            fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
            pdf_filename = f"Riepilogo_Rugby_{inizio_weekend.strftime('%d-%m-%Y')}_{fine_weekend.strftime('%d-%m-%Y')}.pdf"
            
            # Assicurati che il puntatore sia all'inizio del buffer
            pdf_buffer.seek(0)
            
            # Crea un file temporaneo per salvare il contenuto del buffer
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(pdf_buffer.getvalue())
                temp_path = temp_file.name
            
            # Invia il file PDF all'utente
            try:
                await context.bot.send_document(
                    chat_id=query.from_user.id,
                    document=open(temp_path, 'rb'),
                    filename=pdf_filename,
                    caption=f"📄 Riepilogo weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')} in formato PDF"
                )
                # Elimina il file temporaneo dopo l'invio
                os.unlink(temp_path)
            except Exception as e:
                logger.error(f"Errore nell'invio del file PDF: {e}")
                # Assicurati di eliminare il file temporaneo anche in caso di errore
                os.unlink(temp_path)
                raise
            
            # Aggiorna il messaggio
            await query.edit_message_text(
                "✅ File PDF generato e inviato con successo!",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]])
            )
        except Exception as e:
            logger.error(f"Errore durante la generazione del file PDF: {e}")
            await query.edit_message_text(
                f"❌ Errore durante la generazione del file PDF: {e}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna alla dashboard", callback_data="dashboard_torna")]])
            )
    
    elif azione == "torna":
        # Torna alla dashboard
        user_id = query.from_user.id
        user_name = query.from_user.full_name
        
        # Carica i risultati
        risultati = carica_risultati()
        
        # Filtra i risultati inseriti dall'utente
        risultati_utente = [r for r in risultati if r.get('inserito_da') == user_name]
        
        # Ordina i risultati per data (più recenti prima)
        risultati_utente.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Prendi solo gli ultimi 5 risultati
        ultimi_risultati = risultati_utente[:5]
        
        # Calcola statistiche dell'utente
        num_partite_inserite = len(risultati_utente)
        
        # Trova le squadre più inserite dall'utente
        squadre_count = {}
        for r in risultati_utente:
            squadra1 = r.get('squadra1', 'N/D')
            squadra2 = r.get('squadra2', 'N/D')
            squadre_count[squadra1] = squadre_count.get(squadra1, 0) + 1
            squadre_count[squadra2] = squadre_count.get(squadra2, 0) + 1
        
        # Trova le 3 squadre più inserite
        top_squadre = sorted(squadre_count.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Calcola la percentuale di contributo dell'utente
        percentuale_contributo = (num_partite_inserite / len(risultati) * 100) if risultati else 0
        
        # Crea il messaggio della dashboard
        messaggio = f"🏉 <b>DASHBOARD PERSONALE</b> 🏉\n\n"
        messaggio += f"👋 Ciao <b>{user_name}</b>!\n\n"
        
        messaggio += f"📊 <b>LE TUE STATISTICHE</b>\n"
        messaggio += f"• Partite inserite: <b>{num_partite_inserite}</b>\n"
        messaggio += f"• Contributo totale: <b>{percentuale_contributo:.1f}%</b>\n\n"
        
        if top_squadre:
            messaggio += "<b>LE TUE SQUADRE PIÙ INSERITE</b>\n"
            for squadra, count in top_squadre:
                messaggio += f"• {squadra}: <b>{count}</b> partite\n"
            messaggio += "\n"
        
        if ultimi_risultati:
            messaggio += "<b>LE TUE ULTIME PARTITE INSERITE</b>\n"
            for i, r in enumerate(ultimi_risultati, 1):
                data = r.get('data_partita', 'N/D')
                if r.get('tipo_partita') == 'triangolare':
                    messaggio += f"{i}. <b>{data}</b> - Triangolare {r.get('categoria')} {r.get('genere')}\n"
                    messaggio += f"   {r.get('squadra1')}, {r.get('squadra2')}, {r.get('squadra3')}\n"
                else:
                    messaggio += f"{i}. <b>{data}</b> - {r.get('categoria')} {r.get('genere')}\n"
                    messaggio += f"   {r.get('squadra1')} {r.get('punteggio1', 0)}-{r.get('punteggio2', 0)} {r.get('squadra2')}\n"
        else:
            messaggio += "<i>Non hai ancora inserito partite.</i>\n\n"
        
        # Crea i pulsanti per le azioni rapide
        keyboard = [
            [
                InlineKeyboardButton("🆕 Nuova Partita", callback_data="dashboard_nuova"),
                InlineKeyboardButton("📋 Risultati", callback_data="dashboard_risultati")
            ],
            [
                InlineKeyboardButton("📊 Statistiche", callback_data="dashboard_statistiche"),
                InlineKeyboardButton("⚙️ Menu Principale", callback_data="dashboard_menu")
            ]
        ]
        
        # Aggiungi pulsanti per esportazione solo per gli admin
        if is_admin(user_id):
            keyboard.append([
                InlineKeyboardButton("📊 Esporta Excel", callback_data="dashboard_excel"),
                InlineKeyboardButton("📄 Esporta PDF", callback_data="dashboard_pdf")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

# Callback per gestire le azioni del menu principale
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce le azioni del menu principale."""
    query = update.callback_query
    await query.answer()
    
    # Estrai l'azione dal callback data
    azione = query.data.replace("menu_", "")
    
    if azione == "nuova":
        # Questo caso è ora gestito direttamente dal ConversationHandler
        # Il codice qui è mantenuto solo per compatibilità con versioni precedenti
        await query.edit_message_text(
            "Per inserire una nuova partita, usa il comando /nuova",
            parse_mode='HTML'
        )
    
    elif azione == "risultati":
        # Mostra gli ultimi risultati
        risultati = carica_risultati()
        
        if not risultati:
            await query.edit_message_text(
                "Non ci sono ancora risultati inseriti.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
            return
        
        # Mostra gli ultimi 5 risultati
        messaggio = "<b>📋 ULTIMI RISULTATI</b>\n\n"
        
        # Ordina i risultati per data (dal più recente)
        def get_date_key(x):
            data_partita = x.get('data_partita')
            if data_partita is None or data_partita == '':
                return datetime.strptime('01/01/2000', '%d/%m/%Y')
            try:
                return datetime.strptime(data_partita, '%d/%m/%Y')
            except ValueError:
                # In caso di formato data non valido, usa una data predefinita
                return datetime.strptime('01/01/2000', '%d/%m/%Y')
        
        risultati_ordinati = sorted(
            risultati, 
            key=get_date_key,
            reverse=True
        )
        
        # Prendi gli ultimi 5 risultati
        ultimi_risultati = risultati_ordinati[:5]
        
        for i, risultato in enumerate(ultimi_risultati, 1):
            categoria = risultato.get('categoria', 'N/D')
            genere = risultato.get('genere', '')
            info_categoria = f"{categoria} {genere}".strip()
            
            messaggio += f"{i}. <b>{info_categoria}</b> - {risultato.get('data_partita', 'N/D')}\n"
            messaggio += f"   <b>{risultato['squadra1']}</b> {risultato['punteggio1']} - {risultato['punteggio2']} <b>{risultato['squadra2']}</b>\n"
            messaggio += f"   Mete: {risultato['mete1']} - {risultato['mete2']}\n\n"
        
        # Aggiungi un pulsante per tornare al menu principale
        keyboard = [[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif azione == "squadre":
        # Verifica che l'utente sia un amministratore
        if not is_admin(query.from_user.id):
            await query.edit_message_text(
                "⚠️ Solo gli amministratori possono gestire le squadre.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
            return
        
        # Carica le squadre
        squadre = get_squadre_list()
        
        # Crea il messaggio
        messaggio = "<b>🏉 GESTIONE SQUADRE</b>\n\n"
        
        if squadre:
            messaggio += "Squadre attualmente registrate:\n\n"
            # Mostra solo le prime 20 squadre per non rendere il messaggio troppo lungo
            for i, squadra in enumerate(squadre[:20], 1):
                messaggio += f"{i}. {squadra}\n"
            
            if len(squadre) > 20:
                messaggio += f"\n<i>... e altre {len(squadre) - 20} squadre. Usa /squadre per vedere l'elenco completo.</i>"
        else:
            messaggio += "Non ci sono squadre registrate."
        
        messaggio += "\n\n<i>Per aggiungere una nuova squadra, usa il comando /aggiungi_squadra seguito dal nome della squadra.</i>"
        
        # Crea i pulsanti per tornare al menu
        keyboard = [
            [InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif azione == "utenti":
        # Verifica che l'utente sia un amministratore
        if not is_admin(query.from_user.id):
            await query.edit_message_text(
                "⚠️ Solo gli amministratori possono gestire gli utenti.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
            return
        
        # Mostra il menu di gestione utenti
        keyboard = [
            [InlineKeyboardButton("👥 Mostra utenti autorizzati", callback_data="mostra_autorizzati:1")],
            [InlineKeyboardButton("👥 Mostra utenti in attesa", callback_data="mostra_in_attesa:1")],
            [InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "<b>👥 GESTIONE UTENTI</b>\n\n"
            "Seleziona un'opzione:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif azione == "test_canale":
        # Verifica che l'utente sia un amministratore
        if not is_admin(query.from_user.id):
            await query.edit_message_text(
                "⚠️ Solo gli amministratori possono eseguire il test del canale.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
            return
        
        # Esegui il test del canale
        try:
            # Prova a ottenere informazioni sul canale
            chat = await context.bot.get_chat(CHANNEL_ID)
            
            # Invia un messaggio di test
            messaggio_test = (
                "🏉 <b>TEST CONNESSIONE AL CANALE</b> 🏉\n\n"
                "Questo è un messaggio di test per verificare la connessione al canale.\n"
                "Se stai leggendo questo messaggio, la connessione è stata stabilita con successo!"
            )
            
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=messaggio_test,
                parse_mode='HTML'
            )
            
            # Notifica l'utente
            await query.edit_message_text(
                f"✅ <b>Test completato con successo!</b>\n\n"
                f"<b>Canale:</b> {chat.title}\n"
                f"<b>ID:</b> {CHANNEL_ID}\n\n"
                f"Un messaggio di test è stato inviato al canale.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
        except Exception as e:
            # Notifica l'errore
            await query.edit_message_text(
                f"❌ <b>Errore durante il test</b>\n\n"
                f"<b>Errore:</b> <code>{str(e)}</code>\n\n"
                f"Assicurati che:\n"
                f"1. L'ID del canale sia corretto: {CHANNEL_ID}\n"
                f"2. Il bot sia stato aggiunto al canale\n"
                f"3. Il bot sia stato promosso ad amministratore del canale\n"
                f"4. Il bot abbia i permessi per inviare messaggi",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
    
    elif azione == "dashboard":
        # Reindirizza alla dashboard personale
        return await dashboard_command(update, context)
    
    elif azione == "statistiche":
        # Mostra le statistiche delle partite
        risultati = carica_risultati()
        
        if not risultati:
            await query.edit_message_text(
                "Non ci sono ancora risultati inseriti per generare statistiche.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
            return
        
        # Calcola le statistiche
        totale_partite = len(risultati)
        totale_punti = sum(int(r.get('punteggio1', 0)) + int(r.get('punteggio2', 0)) for r in risultati)
        totale_mete = sum(int(r.get('mete1', 0)) + int(r.get('mete2', 0)) for r in risultati)
        
        # Media punti e mete per partita
        media_punti = totale_punti / totale_partite if totale_partite > 0 else 0
        media_mete = totale_mete / totale_partite if totale_partite > 0 else 0
        
        # Trova la partita con più punti
        partita_max_punti = max(risultati, key=lambda r: int(r.get('punteggio1', 0)) + int(r.get('punteggio2', 0)), default=None)
        
        # Trova la partita con più mete
        partita_max_mete = max(risultati, key=lambda r: int(r.get('mete1', 0)) + int(r.get('mete2', 0)), default=None)
        
        # Conta le partite per categoria
        categorie = {}
        for r in risultati:
            categoria = r.get('categoria', 'N/D')
            genere = r.get('genere', '')
            key = f"{categoria} {genere}".strip()
            categorie[key] = categorie.get(key, 0) + 1
        
        # Squadre con più partite
        squadre_count = {}
        for r in risultati:
            squadra1 = r.get('squadra1', 'N/D')
            squadra2 = r.get('squadra2', 'N/D')
            squadre_count[squadra1] = squadre_count.get(squadra1, 0) + 1
            squadre_count[squadra2] = squadre_count.get(squadra2, 0) + 1
        
        # Trova le 3 squadre con più partite
        top_squadre = sorted(squadre_count.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Crea il messaggio con le statistiche
        messaggio = "<b>📊 STATISTICHE PARTITE</b>\n\n"
        
        messaggio += f"<b>Totale partite:</b> {totale_partite}\n"
        messaggio += f"<b>Totale punti:</b> {totale_punti}\n"
        messaggio += f"<b>Totale mete:</b> {totale_mete}\n"
        messaggio += f"<b>Media punti per partita:</b> {media_punti:.1f}\n"
        messaggio += f"<b>Media mete per partita:</b> {media_mete:.1f}\n\n"
        
        if partita_max_punti:
            punti_max = int(partita_max_punti.get('punteggio1', 0)) + int(partita_max_punti.get('punteggio2', 0))
            messaggio += f"<b>Partita con più punti:</b>\n"
            messaggio += f"  {partita_max_punti.get('squadra1')} {partita_max_punti.get('punteggio1')} - {partita_max_punti.get('punteggio2')} {partita_max_punti.get('squadra2')}\n"
            messaggio += f"  Totale: {punti_max} punti\n\n"
        
        if partita_max_mete:
            mete_max = int(partita_max_mete.get('mete1', 0)) + int(partita_max_mete.get('mete2', 0))
            messaggio += f"<b>Partita con più mete:</b>\n"
            messaggio += f"  {partita_max_mete.get('squadra1')} {partita_max_mete.get('mete1')} - {partita_max_mete.get('mete2')} {partita_max_mete.get('squadra2')}\n"
            messaggio += f"  Totale: {mete_max} mete\n\n"
        
        messaggio += "<b>Partite per categoria:</b>\n"
        for cat, count in sorted(categorie.items(), key=lambda x: x[1], reverse=True):
            messaggio += f"  {cat}: {count}\n"
        
        messaggio += "\n<b>Squadre con più partite:</b>\n"
        for squadra, count in top_squadre:
            messaggio += f"  {squadra}: {count}\n"
        
        # Aggiungi un pulsante per tornare al menu principale
        keyboard = [[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif azione == "riepilogo_weekend":
        # Verifica che l'utente sia un amministratore
        if not is_admin(query.from_user.id):
            await query.edit_message_text(
                "⚠️ Solo gli amministratori possono visualizzare il riepilogo del weekend.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
            return
            
        # Genera il riepilogo
        inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
        
        if not messaggio:
            await query.edit_message_text(
                f"Non ci sono risultati per il weekend {inizio_weekend_str} - {fine_weekend_str}.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
            )
            return
            
        # Crea i pulsanti per pubblicare il riepilogo e per esportarlo
        keyboard = [
            [InlineKeyboardButton("📢 Pubblica sul canale", callback_data="pubblica_riepilogo")],
            [
                InlineKeyboardButton("📊 Esporta Excel", callback_data="esporta_excel_riepilogo"),
                InlineKeyboardButton("📄 Esporta PDF", callback_data="esporta_pdf_riepilogo")
            ],
            [InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Mostra il riepilogo
        await query.edit_message_text(
            messaggio,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    elif azione == "torna":
        # Torna al menu principale
        # Crea i pulsanti per le funzioni standard
        keyboard = [
            [InlineKeyboardButton("📝 Inserisci nuova partita", callback_data="menu_nuova")],
            [InlineKeyboardButton("🏁 Ultimi risultati", callback_data="menu_risultati")],
            [InlineKeyboardButton("📊 Statistiche", callback_data="menu_statistiche")]
        ]
        
        # Aggiungi il pulsante per il riepilogo weekend solo per gli admin
        if is_admin(query.from_user.id):
            keyboard.append([InlineKeyboardButton("🗓️ Riepilogo weekend", callback_data="menu_riepilogo_weekend")])
        
        # Aggiungi pulsanti per le funzioni amministrative se l'utente è un admin
        if is_admin(query.from_user.id):
            keyboard.extend([
                [InlineKeyboardButton("👥 Gestione utenti", callback_data="menu_utenti")],
                [InlineKeyboardButton("🏉 Gestione squadre", callback_data="menu_squadre")],
                [InlineKeyboardButton("🔄 Test canale", callback_data="menu_test_canale")]
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "<b>🏉 MENU PRINCIPALE</b>\n\n"
            "Seleziona una funzione:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        # Azione non riconosciuta
        await query.edit_message_text(
            f"⚠️ Azione non riconosciuta: {azione}", 
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )

# Callback per approvare un utente
async def approva_utente_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approva un utente per l'utilizzo del bot."""
    query = update.callback_query
    await query.answer()
    
    # Verifica che l'utente sia un amministratore
    if not is_admin(query.from_user.id):
        await query.edit_message_text(
            "⚠️ Solo gli amministratori possono approvare gli utenti.",
            parse_mode='HTML'
        )
        return
    
    # Estrai l'ID utente dal callback data
    user_id_str = query.data.replace("approva_", "")
    try:
        user_id = int(user_id_str)
    except ValueError:
        await query.edit_message_text(
            "⚠️ ID utente non valido.",
            parse_mode='HTML'
        )
        return
    
    # Carica gli utenti
    utenti = carica_utenti()
    
    # Cerca l'utente nella lista di attesa
    utente_da_approvare = None
    for i, utente in enumerate(utenti["in_attesa"]):
        if isinstance(utente, dict) and utente.get("id") == user_id:
            utente_da_approvare = utente
            utenti["in_attesa"].pop(i)
            break
        elif not isinstance(utente, dict) and utente == user_id:
            utente_da_approvare = {"id": user_id, "nome": "Utente", "username": None, "data_registrazione": None}
            utenti["in_attesa"].pop(i)
            break
    
    # Verifica se l'utente è già autorizzato
    for utente in utenti["autorizzati"]:
        if isinstance(utente, dict) and utente.get("id") == user_id:
            await query.edit_message_text(
                f"⚠️ L'utente {user_id} è già autorizzato.",
                parse_mode='HTML'
            )
            return
        elif not isinstance(utente, dict) and utente == user_id:
            await query.edit_message_text(
                f"⚠️ L'utente {user_id} è già autorizzato.",
                parse_mode='HTML'
            )
            return
    
    # Verifica se l'utente è stato trovato nella lista di attesa
    if not utente_da_approvare:
        await query.edit_message_text(
            f"⚠️ L'utente {user_id} non è in attesa di approvazione o l'ID non è valido.",
            parse_mode='HTML'
        )
        return
    
    # Aggiungi l'utente alla lista degli autorizzati
    utenti["autorizzati"].append(utente_da_approvare)
    salva_utenti(utenti)
    
    # Aggiorna il messaggio
    await query.edit_message_text(
        f"✅ <b>Utente approvato</b>\n\n"
        f"L'utente con ID {user_id} è stato autorizzato con successo.\n"
        f"L'utente è stato notificato dell'approvazione.",
        parse_mode='HTML'
    )
    
    # Notifica l'utente
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ <b>Accesso approvato!</b>\n\n"
                 "La tua richiesta di accesso al bot CRV Rugby è stata approvata.\n"
                 "Ora puoi utilizzare tutte le funzionalità del bot.\n\n"
                 "Usa /start per iniziare.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Impossibile inviare notifica all'utente {user_id}: {e}")

# Callback per rifiutare un utente
async def rifiuta_utente_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rifiuta un utente per l'utilizzo del bot."""
    query = update.callback_query
    await query.answer()
    
    # Verifica che l'utente sia un amministratore
    if not is_admin(query.from_user.id):
        await query.edit_message_text(
            "⚠️ Solo gli amministratori possono rifiutare gli utenti.",
            parse_mode='HTML'
        )
        return
    
    # Estrai l'ID utente dal callback data
    user_id_str = query.data.replace("rifiuta_", "")
    try:
        user_id = int(user_id_str)
    except ValueError:
        await query.edit_message_text(
            "⚠️ ID utente non valido.",
            parse_mode='HTML'
        )
        return
    
    # Carica gli utenti
    utenti = carica_utenti()
    
    # Cerca l'utente nella lista di attesa
    utente_trovato = False
    for i, utente in enumerate(utenti["in_attesa"]):
        if isinstance(utente, dict) and utente.get("id") == user_id:
            utenti["in_attesa"].pop(i)
            utente_trovato = True
            break
        elif not isinstance(utente, dict) and utente == user_id:
            utenti["in_attesa"].pop(i)
            utente_trovato = True
            break
    
    # Verifica se l'utente è stato trovato
    if not utente_trovato:
        await query.edit_message_text(
            f"⚠️ L'utente {user_id} non è in attesa di approvazione o l'ID non è valido.",
            parse_mode='HTML'
        )
        return
    
    # Salva le modifiche
    salva_utenti(utenti)
    
    # Aggiorna il messaggio
    await query.edit_message_text(
        f"❌ <b>Richiesta rifiutata</b>\n\n"
        f"La richiesta di accesso dell'utente con ID {user_id} è stata rifiutata.\n"
        f"L'utente è stato notificato del rifiuto.",
        parse_mode='HTML'
    )
    
    # Notifica l'utente
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ <b>Accesso rifiutato</b>\n\n"
                 "La tua richiesta di accesso al bot CRV Rugby è stata rifiutata.\n"
                 "Se ritieni che ci sia stato un errore, contatta un amministratore.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Impossibile inviare notifica all'utente {user_id}: {e}")

# Callback per promuovere un utente a admin
async def promuovi_utente_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Promuove un utente a amministratore."""
    query = update.callback_query
    await query.answer()
    
    # Verifica che l'utente sia un amministratore
    if not is_admin(query.from_user.id):
        await query.edit_message_text(
            "⚠️ Solo gli amministratori possono promuovere altri utenti.",
            parse_mode='HTML'
        )
        return
    
    # Estrai l'ID utente dal callback data
    user_id_str = query.data.replace("promuovi_", "")
    try:
        user_id = int(user_id_str)
    except ValueError:
        await query.edit_message_text(
            "⚠️ ID utente non valido.",
            parse_mode='HTML'
        )
        return
    
    # Usa la funzione di utilità per promuovere l'utente
    from modules.user_manager import promuovi_utente_admin
    success, message = promuovi_utente_admin(user_id)
    
    if success:
        # Aggiorna il messaggio
        await query.edit_message_text(
            f"✅ <b>Utente promosso</b>\n\n"
            f"L'utente con ID {user_id} è stato promosso ad amministratore.\n"
            f"Ora ha accesso a tutte le funzionalità di amministrazione.",
            parse_mode='HTML'
        )
        
        # Notifica l'utente
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🔑 <b>Promozione a Amministratore</b>\n\n"
                     "Sei stato promosso ad amministratore del bot CRV Rugby.\n"
                     "Ora hai accesso a tutte le funzionalità di amministrazione.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Impossibile inviare notifica all'utente {user_id}: {e}")
    else:
        # Notifica l'errore
        await query.edit_message_text(
            f"⚠️ <b>Errore</b>\n\n"
            f"{message}",
            parse_mode='HTML'
        )

# Callback per declassare un utente da admin
async def declassa_utente_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Declassa un utente da amministratore a utente normale."""
    query = update.callback_query
    await query.answer()
    
    # Verifica che l'utente sia un amministratore
    if not is_admin(query.from_user.id):
        await query.edit_message_text(
            "⚠️ Solo gli amministratori possono declassare altri utenti.",
            parse_mode='HTML'
        )
        return
    
    # Estrai l'ID utente dal callback data
    user_id_str = query.data.replace("declassa_", "")
    try:
        user_id = int(user_id_str)
    except ValueError:
        await query.edit_message_text(
            "⚠️ ID utente non valido.",
            parse_mode='HTML'
        )
        return
    
    # Usa la funzione di utilità per declassare l'utente
    from modules.user_manager import declassa_utente_admin
    success, message = declassa_utente_admin(user_id)
    
    if success:
        # Aggiorna il messaggio
        await query.edit_message_text(
            f"✅ <b>Utente declassato</b>\n\n"
            f"L'utente con ID {user_id} è stato declassato a utente normale.\n"
            f"Non ha più accesso alle funzionalità di amministrazione.",
            parse_mode='HTML'
        )
        
        # Notifica l'utente
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="ℹ️ <b>Cambio di ruolo</b>\n\n"
                     "Il tuo ruolo è stato modificato da amministratore a utente normale.\n"
                     "Non hai più accesso alle funzionalità di amministrazione.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Impossibile inviare notifica all'utente {user_id}: {e}")
    else:
        # Notifica l'errore
        await query.edit_message_text(
            f"⚠️ <b>Errore</b>\n\n"
            f"{message}",
            parse_mode='HTML'
        )

# Funzione per gestire gli errori
async def error(update, context):
    """Gestisce gli errori del bot."""
    logger.warning(f'Update {update} ha causato l\'errore {context.error}')
    
    # Invia un messaggio all'utente
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Si è verificato un errore durante l'elaborazione della richiesta. Riprova più tardi."
        )

# Callback per gestire la visualizzazione e gestione degli utenti
async def gestione_utenti_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce la visualizzazione e la gestione degli utenti autorizzati e in attesa."""
    query = update.callback_query
    await query.answer()
    
    # Verifica che l'utente sia un amministratore
    if not is_admin(query.from_user.id):
        await query.edit_message_text(
            "⚠️ Solo gli amministratori possono gestire gli utenti.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]])
        )
        return
    
    # Gestione del pulsante "mostra_in_attesa"
    if query.data.startswith("mostra_in_attesa"):
        # Carica gli utenti
        utenti = carica_utenti()
        
        # Estrai il parametro di pagina se presente
        parts = query.data.split(":")
        page = 1
        if len(parts) > 1:
            try:
                page = int(parts[1])
            except ValueError:
                page = 1
        
        # Numero di utenti per pagina
        per_page = 5
        
        # Crea il messaggio
        messaggio = "<b>📋 UTENTI IN ATTESA</b>\n\n"
        
        if utenti["in_attesa"]:
            # Calcola il numero totale di pagine
            total_users = len(utenti["in_attesa"])
            total_pages = (total_users + per_page - 1) // per_page
            
            # Assicurati che la pagina sia valida
            if page < 1:
                page = 1
            if page > total_pages:
                page = total_pages
            
            # Calcola l'indice di inizio e fine per questa pagina
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, total_users)
            
            # Mostra gli utenti per questa pagina
            for i, utente in enumerate(utenti["in_attesa"][start_idx:end_idx], start_idx + 1):
                if isinstance(utente, dict):
                    uid = utente.get("id")
                    nome = utente.get("nome", "Utente")
                    username = utente.get("username", "Non disponibile")
                    data = utente.get("data_registrazione", "N/D")
                    messaggio += f"{i}. <b>{nome}</b>\n"
                    messaggio += f"   ID: {uid}\n"
                    messaggio += f"   Username: @{username}\n"
                    messaggio += f"   Registrato il: {data}\n\n"
                else:
                    # Compatibilità con il vecchio formato
                    uid = utente
                    messaggio += f"{i}. ID: {uid}\n\n"
            
            messaggio += f"<i>Pagina {page} di {total_pages}</i>"
            
            # Crea pulsanti per ogni utente in attesa
            keyboard = []
            for utente in utenti["in_attesa"][start_idx:end_idx]:
                if isinstance(utente, dict):
                    uid = utente.get("id")
                    nome = utente.get("nome", "Utente")
                    # Non includere il nome nel callback_data, solo nell'etichetta del pulsante
                    # Limita il nome a 15 caratteri per i pulsanti
                    nome_breve = nome[:15] + "..." if len(nome) > 15 else nome
                    keyboard.append([
                        InlineKeyboardButton(f"✅ {nome_breve}", callback_data=f"approva_{uid}"),
                        InlineKeyboardButton(f"❌ {nome_breve}", callback_data=f"rifiuta_{uid}")
                    ])
                else:
                    # Compatibilità con il vecchio formato
                    uid = utente
                    keyboard.append([
                        InlineKeyboardButton(f"✅ Approva {uid}", callback_data=f"approva_{uid}"),
                        InlineKeyboardButton(f"❌ Rifiuta {uid}", callback_data=f"rifiuta_{uid}")
                    ])
            
            # Aggiungi pulsanti di navigazione
            nav_buttons = []
            
            # Pulsante pagina precedente
            if page > 1:
                nav_buttons.append(
                    InlineKeyboardButton("⬅️ Precedente", callback_data=f"mostra_in_attesa:{page-1}")
                )
            
            # Pulsante pagina successiva
            if page < total_pages:
                nav_buttons.append(
                    InlineKeyboardButton("➡️ Successiva", callback_data=f"mostra_in_attesa:{page+1}")
                )
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Aggiungi pulsanti per filtrare e cercare
            keyboard.append([
                InlineKeyboardButton("🔍 Cerca utente", callback_data="cerca_utente")
            ])
            
            # Aggiungi un pulsante per tornare agli utenti autorizzati
            keyboard.append([
                InlineKeyboardButton("👥 Mostra utenti autorizzati", callback_data="mostra_autorizzati:1")
            ])
            
            # Aggiungi un pulsante per tornare al menu principale
            keyboard.append([
                InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                messaggio,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            # Aggiungi un pulsante per tornare agli utenti autorizzati
            keyboard = [
                [InlineKeyboardButton("👥 Mostra utenti autorizzati", callback_data="mostra_autorizzati:1")],
                [InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"{messaggio}Nessun utente in attesa.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        
        return
    
    # Gestione del pulsante "mostra_autorizzati"
    if query.data.startswith("mostra_autorizzati"):
        # Carica gli utenti
        utenti = carica_utenti()
        
        # Estrai il parametro di pagina se presente
        parts = query.data.split(":")
        page = 1
        if len(parts) > 1:
            try:
                page = int(parts[1])
            except ValueError:
                page = 1
        
        # Numero di utenti per pagina
        per_page = 5
        
        # Crea il messaggio
        messaggio = "<b>📋 UTENTI AUTORIZZATI</b>\n\n"
        
        if utenti["autorizzati"]:
            # Calcola il numero totale di pagine
            total_users = len(utenti["autorizzati"])
            total_pages = (total_users + per_page - 1) // per_page
            
            # Assicurati che la pagina sia valida
            if page < 1:
                page = 1
            if page > total_pages:
                page = total_pages
            
            # Calcola l'indice di inizio e fine per questa pagina
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, total_users)
            
            # Mostra gli utenti per questa pagina
            for i, utente in enumerate(utenti["autorizzati"][start_idx:end_idx], start_idx + 1):
                if isinstance(utente, dict):
                    uid = utente.get("id")
                    nome = utente.get("nome", "Utente")
                    username = utente.get("username", "Non disponibile")
                    data = utente.get("data_registrazione", "N/D")
                    ruolo = utente.get("ruolo", "utente")
                    messaggio += f"{i}. <b>{nome}</b> {'(Admin)' if ruolo == 'admin' else ''}\n"
                    messaggio += f"   ID: {uid}\n"
                    messaggio += f"   Username: @{username}\n"
                    messaggio += f"   Registrato il: {data}\n\n"
                else:
                    # Compatibilità con il vecchio formato
                    uid = utente
                    messaggio += f"{i}. ID: {uid}\n\n"
            
            messaggio += f"<i>Pagina {page} di {total_pages}</i>"
            
            # Crea pulsanti per gestire gli utenti autorizzati
            keyboard = []
            for utente in utenti["autorizzati"][start_idx:end_idx]:
                if isinstance(utente, dict):
                    uid = utente.get("id")
                    nome = utente.get("nome", "Utente")
                    ruolo = utente.get("ruolo", "utente")
                    # Non includere il nome nel callback_data, solo nell'etichetta del pulsante
                    # Limita il nome a 15 caratteri per i pulsanti
                    nome_breve = nome[:15] + "..." if len(nome) > 15 else nome
                    
                    # Pulsanti diversi in base al ruolo
                    if ruolo == "admin":
                        keyboard.append([
                            InlineKeyboardButton(f"⬇️ {nome_breve}", callback_data=f"declassa_{uid}"),
                            InlineKeyboardButton(f"❌ {nome_breve}", callback_data=f"rimuovi_{uid}")
                        ])
                    else:
                        keyboard.append([
                            InlineKeyboardButton(f"⬆️ {nome_breve}", callback_data=f"promuovi_{uid}"),
                            InlineKeyboardButton(f"❌ {nome_breve}", callback_data=f"rimuovi_{uid}")
                        ])
                else:
                    # Compatibilità con il vecchio formato
                    uid = utente
                    keyboard.append([
                        InlineKeyboardButton(f"⬆️ Promuovi {uid}", callback_data=f"promuovi_{uid}"),
                        InlineKeyboardButton(f"❌ Rimuovi {uid}", callback_data=f"rimuovi_{uid}")
                    ])
            
            # Aggiungi pulsanti di navigazione
            nav_buttons = []
            
            # Pulsante pagina precedente
            if page > 1:
                nav_buttons.append(
                    InlineKeyboardButton("⬅️ Precedente", callback_data=f"mostra_autorizzati:{page-1}")
                )
            
            # Pulsante pagina successiva
            if page < total_pages:
                nav_buttons.append(
                    InlineKeyboardButton("➡️ Successiva", callback_data=f"mostra_autorizzati:{page+1}")
                )
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Aggiungi pulsanti per filtrare e cercare
            keyboard.append([
                InlineKeyboardButton("🔍 Cerca utente", callback_data="cerca_utente")
            ])
            
            # Aggiungi un pulsante per mostrare gli utenti in attesa
            keyboard.append([
                InlineKeyboardButton("👥 Mostra utenti in attesa", callback_data="mostra_in_attesa:1")
            ])
            
            # Aggiungi un pulsante per tornare al menu principale
            keyboard.append([
                InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                messaggio,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            # Aggiungi un pulsante per mostrare gli utenti in attesa
            keyboard = [
                [InlineKeyboardButton("👥 Mostra utenti in attesa", callback_data="mostra_in_attesa:1")],
                [InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"{messaggio}Nessun utente autorizzato.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        
        return
    
    # Gestione del pulsante "cerca_utente"
    if query.data == "cerca_utente":
        # Informa l'utente di inviare l'ID da cercare
        await query.edit_message_text(
            "<b>🔍 CERCA UTENTE</b>\n\n"
            "Per cercare un utente specifico, invia un messaggio con l'ID dell'utente.\n\n"
            "<i>Nota: Questa funzionalità richiede che tu invii un nuovo messaggio. "
            "Dopo aver trovato l'utente, potrai gestirlo.</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Torna agli utenti", callback_data="mostra_autorizzati:1")]
            ])
        )
        
        # Salva lo stato per gestire la risposta
        context.user_data['attesa_ricerca_utente'] = True
        
        return
    
    # Gestione del pulsante "rimuovi"
    if query.data.startswith("rimuovi_"):
        # Estrai l'ID utente dal callback data
        user_id_str = query.data.replace("rimuovi_", "")
        try:
            user_id = int(user_id_str)
        except ValueError:
            await query.edit_message_text(
                "⚠️ ID utente non valido.",
                parse_mode='HTML'
            )
            return
        
        # Carica gli utenti
        utenti = carica_utenti()
        
        # Cerca l'utente nella lista degli autorizzati
        trovato = False
        for i, utente in enumerate(utenti["autorizzati"]):
            if isinstance(utente, dict) and utente.get("id") == user_id:
                utenti["autorizzati"].pop(i)
                trovato = True
                break
            elif not isinstance(utente, dict) and utente == user_id:
                utenti["autorizzati"].pop(i)
                trovato = True
                break
        
        if trovato:
            # Salva le modifiche
            salva_utenti(utenti)
            
            # Aggiorna il messaggio
            await query.edit_message_text(
                f"✅ <b>Utente rimosso</b>\n\n"
                f"L'utente con ID {user_id} è stato rimosso dalla lista degli autorizzati.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Torna agli utenti", callback_data="mostra_autorizzati:1")]
                ])
            )
            
            # Notifica l'utente
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ <b>Accesso revocato</b>\n\n"
                         "Il tuo accesso al bot CRV Rugby è stato revocato.\n"
                         "Se ritieni che ci sia stato un errore, contatta un amministratore.",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Impossibile inviare notifica all'utente {user_id}: {e}")
        else:
            await query.edit_message_text(
                f"⚠️ L'utente {user_id} non è autorizzato o l'ID non è valido.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Torna agli utenti", callback_data="mostra_autorizzati:1")]
                ])
            )
        
        return

# Comando /nuova
async def nuova_partita(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Avvia il processo di inserimento di una nuova partita con modalità wizard."""
    user_id = update.effective_user.id
    
    # Pulisci i dati utente precedenti
    context.user_data.clear()
    
    # Verifica che l'utente sia autorizzato
    if not is_utente_autorizzato(user_id):
        # Verifica se è un callback o un comando
        if update.callback_query:
            await update.callback_query.answer("Non sei autorizzato a utilizzare questa funzione.")
            await update.callback_query.edit_message_text(
                "⚠️ <b>Accesso non autorizzato</b>\n\n"
                "Non sei autorizzato a utilizzare questa funzione.\n"
                "Usa /start per richiedere l'accesso.",
                parse_mode='HTML'
            )
        else:
            # Handle the case where update.callback_query does not exist
            await update.message.reply_html(
                "⚠️ <b>Accesso non autorizzato</b>\n\n"
                "Non sei autorizzato a utilizzare questo comando.\n"
                "Usa /start per richiedere l'accesso."
            )
        return ConversationHandler.END
    
    # Carica le squadre
    context.user_data['squadre_disponibili'] = carica_squadre()
    
    # Imposta lo stato corrente
    context.user_data['stato_corrente'] = CATEGORIA
    
    # Genera la barra di avanzamento
    barra_avanzamento = genera_barra_avanzamento(CATEGORIA)
    
    # Crea una tastiera con le categorie
    keyboard = []
    for i in range(0, len(CATEGORIE), 2):
        row = []
        row.append(InlineKeyboardButton(CATEGORIE[i], callback_data=CATEGORIE[i]))
        if i + 1 < len(CATEGORIE):
            row.append(InlineKeyboardButton(CATEGORIE[i + 1], callback_data=CATEGORIE[i + 1]))
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Prepara il messaggio con barra di avanzamento
        messaggio = f"{barra_avanzamento}\n\n"
        messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
        messaggio += "<b>Seleziona la categoria della partita:</b>\n\n"
        messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
        # Verifica se è un callback o un comando
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(
                messaggio,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_html(
                messaggio,
                reply_markup=reply_markup
            )
        
        
        # Imposta un timeout di 10 minuti per l'inserimento utilizzando il JobManager alternativo
        try:
            from modules.job_manager import job_manager
            
            # Cancella eventuali job di timeout precedenti per questo utente
            for job in job_manager.get_jobs_by_name(f"timeout_{user_id}"):
                job_manager.remove_job(job)
            
            # Wrapper per adattare la funzione al formato richiesto dal JobManager
            async def timeout_wrapper(user_id_data):
                # Crea un contesto fittizio con il job
                class FakeJob:
                    def __init__(self, data):
                        self.data = data
            
            class FakeContext:
                def __init__(self, bot, job):
                    self.bot = bot
                    self.job = job
                    self.user_data = {}
                    self.chat_data = {}
                    self.bot_data = {}
            
            # Define the FakeJob class
            class FakeJob:
                def __init__(self, data):
                    self.data = data

            fake_job = FakeJob(user_id)
            fake_context = FakeContext(context.bot, fake_job)
            await timeout_callback(update, fake_context)
                
               # Crea un nuovo job di timeout
            job_manager.run_once(
                timeout_wrapper,
                600,  # 10 minuti in secondi
                data=user_id,
                name=f"timeout_{user_id}"
            )
            logger.info(f"Impostato timeout di 10 minuti per l'utente {user_id} (JobManager alternativo)")
        except Exception as e:
            logger.error(f"Errore nell'impostazione del timeout con JobManager alternativo: {e}")
        
        return CATEGORIA
    except Exception as e:
        logger.error(f"Errore in nuova_partita: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"Si è verificato un errore: {e}\nRiprova più tardi.",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "Si è verificato un errore nell'inserimento della sezione arbitrale. Riprova con /nuova.",
                parse_mode='HTML'
            )
        return ConversationHandler.END

# Funzione per generare la barra di avanzamento del wizard
def genera_barra_avanzamento(stato_corrente, tipo_partita='normale'):
    """
    Genera una barra di avanzamento visiva per il wizard di inserimento.
    
    Args:
        stato_corrente: Lo stato corrente della conversazione
        tipo_partita: 'normale' o 'triangolare'
        
    Returns:
        Una stringa con la barra di avanzamento
    """
    # Definisci gli stati per ciascun tipo di partita
    if tipo_partita == 'triangolare':
        stati = [
            (CATEGORIA, "Categoria"),
            (GENERE, "Genere"),
            (TIPO_PARTITA, "Tipo"),
            (SQUADRA1, "Squadra 1"),
            (SQUADRA2, "Squadra 2"),
            (SQUADRA3, "Squadra 3"),
            (DATA_PARTITA, "Data"),
            (PUNTEGGIO1, "Punti 1"),
            (PUNTEGGIO2, "Punti 2"),
            (PUNTEGGIO3, "Punti 3"),
            (METE1, "Mete 1"),
            (METE2, "Mete 2"),
            (METE3, "Mete 3"),
            (ARBITRO, "Arbitro"),
            (CONFERMA, "Conferma")
        ]
    else:
        stati = [
            (CATEGORIA, "Categoria"),
            (GENERE, "Genere"),
            (TIPO_PARTITA, "Tipo"),
            (SQUADRA1, "Squadra 1"),
            (SQUADRA2, "Squadra 2"),
            (DATA_PARTITA, "Data"),
            (PUNTEGGIO1, "Punti 1"),
            (PUNTEGGIO2, "Punti 2"),
            (METE1, "Mete 1"),
            (METE2, "Mete 2"),
            (ARBITRO, "Arbitro"),
            (CONFERMA, "Conferma")
        ]
    
    # Trova l'indice dello stato corrente
    indice_corrente = next((i for i, (stato, _) in enumerate(stati) if stato == stato_corrente), 0)
    
    # Calcola la percentuale di completamento
    percentuale = int((indice_corrente / (len(stati) - 1)) * 100)
    
    # Genera la barra grafica
    barra = "🏉 "
    barra_lunghezza = 10
    blocchi_pieni = int((percentuale / 100) * barra_lunghezza)
    
    for i in range(barra_lunghezza):
        if i < blocchi_pieni:
            barra += "■"  # Blocco pieno
        else:
            barra += "□"  # Blocco vuoto
    
    barra += f" {percentuale}%"
    
    # Aggiungi il nome dello stato corrente
    nome_stato = next((nome for stato, nome in stati if stato == stato_corrente), "")
    if nome_stato:
        barra += f" | {nome_stato}"
    
    return barra

# Funzione per generare il riepilogo dei dati inseriti
def genera_riepilogo_dati(context, completo=False):
    """
    Genera un riepilogo dei dati inseriti finora.
    
    Args:
        context: Il contesto della conversazione
        completo: Se True, mostra tutti i campi anche se vuoti
        
    Returns:
        Una stringa con il riepilogo
    """
    dati = context.user_data
    riepilogo = ""
    
    # Campi da mostrare in ordine
    campi = [
        ("categoria", "Categoria"),
        ("genere", "Genere"),
        ("tipo_partita", "Tipo partita"),
        ("squadra1", "Prima squadra"),
        ("squadra2", "Seconda squadra")
    ]
    
    # Aggiungi squadra3 solo per triangolari
    if dati.get('tipo_partita') == 'triangolare':
        campi.append(("squadra3", "Terza squadra"))
    
    # Aggiungi altri campi
    campi.extend([
        ("data_partita", "Data"),
        ("punteggio1", "Punteggio 1"),
        ("punteggio2", "Punteggio 2"),
        ("mete1", "Mete 1"),
        ("mete2", "Mete 2"),
        ("arbitro", "Arbitro")
    ])
    
    # Aggiungi punteggio3 e mete3 solo per triangolari
    if dati.get('tipo_partita') == 'triangolare':
        # Inserisci dopo punteggio2 e mete2
        indice_punteggio = next((i for i, (campo, _) in enumerate(campi) if campo == "punteggio2"), -1)
        indice_mete = next((i for i, (campo, _) in enumerate(campi) if campo == "mete2"), -1)
        
        if indice_punteggio != -1:
            campi.insert(indice_punteggio + 1, ("punteggio3", "Punteggio 3"))
        
        if indice_mete != -1:
            campi.insert(indice_mete + 1, ("mete3", "Mete 3"))
    
    # Genera il riepilogo
    for campo, etichetta in campi:
        valore = dati.get(campo)
        if valore or completo:
            riepilogo += f"<b>{etichetta}:</b> {valore or 'Non inserito'}\n"
    
    return riepilogo

# Funzione per annullare la conversazione
async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Annulla la conversazione corrente."""
    user_id = update.effective_user.id
    
    # Cancella eventuali job di timeout con JobManager alternativo
    try:
        from modules.job_manager import job_manager
        for job in job_manager.get_jobs_by_name(f"timeout_{user_id}"):
            job_manager.remove_job(job)
    except Exception as e:
        logger.error(f"Errore nella cancellazione dei job di timeout con JobManager alternativo: {e}")
    
    # Pulisci i dati utente
    context.user_data.clear()
    
    await update.message.reply_text(
        "❌ Operazione annullata.\n\n"
        "Usa /menu per tornare al menu principale.",
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

# Funzione di callback per il timeout
async def timeout_callback(update: Update, context) -> None:
    """Gestisce il timeout dell'inserimento."""
    try:
        # Ottieni l'ID utente dai dati del job
        user_id = context.job.data
        
        # Verifica se l'utente è ancora in una conversazione
        if context.user_data.get('stato_corrente'):
            # Invia un messaggio all'utente
            await context.bot.send_message(
                chat_id=user_id,
                text="⏱️ <b>Tempo scaduto</b>\n\n"
                     "Il tempo per l'inserimento della partita è scaduto.\n"
                     "Usa /nuova per iniziare di nuovo.",
                parse_mode='HTML'
            )
            
            # Pulisci i dati utente
            context.user_data.clear()
            
            logger.info(f"Timeout per l'utente {user_id}")
    except Exception as e:
        logger.error(f"Errore nel callback di timeout: {e}")

# Callback per la selezione della categoria
async def categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione della categoria."""
    query = update.callback_query
    await query.answer()
    
    try:
        categoria = query.data
        context.user_data['categoria'] = categoria
        
        # Aggiorna lo stato corrente
        context.user_data['stato_corrente'] = GENERE
        
        # Genera la barra di avanzamento
        barra_avanzamento = genera_barra_avanzamento(GENERE)
        
        # Genera il riepilogo dei dati inseriti finora
        riepilogo = genera_riepilogo_dati(context)
        
        # Crea una tastiera per la selezione del genere
        keyboard = [
            [
                InlineKeyboardButton("Maschile", callback_data="Maschile"),
                InlineKeyboardButton("Femminile", callback_data="Femminile")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Prepara il messaggio con barra di avanzamento e riepilogo
        messaggio = f"{barra_avanzamento}\n\n"
        messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
        
        if riepilogo:
            messaggio += f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
        
        messaggio += "<b>Seleziona il genere:</b>\n\n"
        messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        return GENERE
    except Exception as e:
        logger.error(f"Errore nella selezione della categoria: {e}")
        await query.edit_message_text(
            "Si è verificato un errore nella selezione della categoria. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per la selezione del genere
async def genere_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione del genere."""
    query = update.callback_query
    await query.answer()
    
    try:
        genere = query.data
        context.user_data['genere'] = genere
        
        # Verifica se è una categoria U14, in tal caso chiedi il tipo di partita
        if context.user_data['categoria'] == "U14":
            # Aggiorna lo stato corrente
            context.user_data['stato_corrente'] = TIPO_PARTITA
            
            # Genera la barra di avanzamento
            barra_avanzamento = genera_barra_avanzamento(TIPO_PARTITA)
            
            # Genera il riepilogo dei dati inseriti finora
            riepilogo = genera_riepilogo_dati(context)
            
            # Crea una tastiera per la selezione del tipo di partita
            keyboard = [
                [
                    InlineKeyboardButton("Partita normale", callback_data="normale"),
                    InlineKeyboardButton("Triangolare", callback_data="triangolare")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Prepara il messaggio con barra di avanzamento e riepilogo
            messaggio = f"{barra_avanzamento}\n\n"
            messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
            
            if riepilogo:
                messaggio += f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
            
            messaggio += "<b>Seleziona il tipo di partita:</b>\n\n"
            messaggio += "• <b>Partita normale:</b> Due squadre\n"
            messaggio += "• <b>Triangolare:</b> Tre squadre che si affrontano a rotazione\n\n"
            messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
            
            await query.edit_message_text(
                messaggio,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            return TIPO_PARTITA
        else:
            # Per le altre categorie, procedi direttamente alla selezione della squadra
            context.user_data['tipo_partita'] = 'normale'  # Imposta il tipo di partita come normale per default
            
            # Aggiorna lo stato corrente
            context.user_data['stato_corrente'] = SQUADRA1
            
            # Genera la barra di avanzamento
            barra_avanzamento = genera_barra_avanzamento(SQUADRA1)
            
            # Genera il riepilogo dei dati inseriti finora
            riepilogo = genera_riepilogo_dati(context)
            
            # Carica le squadre disponibili
            squadre = get_squadre_list()
            
            # Crea una tastiera con le squadre (2 per riga)
            keyboard = []
            for i in range(0, len(squadre), 2):
                row = []
                # Aggiungi la prima squadra della riga
                row.append(InlineKeyboardButton(squadre[i], callback_data=squadre[i]))
                if i + 1 < len(squadre):
                    row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))
                keyboard.append(row)
            
            # Aggiungi un pulsante per inserire manualmente una squadra
            keyboard.append([InlineKeyboardButton("Altra squadra", callback_data="altra_squadra")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Prepara il messaggio con barra di avanzamento e riepilogo
            messaggio = f"{barra_avanzamento}\n\n"
            messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
            
            if riepilogo:
                messaggio += f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
            
            messaggio += "<b>Seleziona la prima squadra:</b>\n\n"
            messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
            
            await query.edit_message_text(
                messaggio,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            return SQUADRA1
    except Exception as e:
        logger.error(f"Errore nella selezione del genere: {e}")
        await query.edit_message_text(
            "Si è verificato un errore nella selezione del genere. Riprova con /nuova."
        )
        return ConversationHandler.END

# Funzione per creare la tastiera delle squadre con paginazione
def create_teams_keyboard(squadre, page=1, teams_per_page=10, search_query=None, exclude_team=None, filter_letter=None):
    """
    Crea una tastiera con paginazione per la selezione delle squadre.
    
    Args:
        squadre: Lista di tutte le squadre disponibili
        page: Numero di pagina corrente (inizia da 1)
        teams_per_page: Numero di squadre per pagina
        search_query: Query di ricerca per filtrare le squadre
        exclude_team: Squadra da escludere dalla lista (es. prima squadra già selezionata)
        filter_letter: Lettera iniziale per filtrare le squadre (A-Z)
    
    Returns:
        InlineKeyboardMarkup con le squadre paginate e i controlli di navigazione
    """
    # Filtra le squadre in base alla query di ricerca o alla lettera iniziale
    if search_query:
        search_query = search_query.lower()
        filtered_squadre = [s for s in squadre if search_query in s.lower()]
    elif filter_letter and isinstance(filter_letter, str) and filter_letter.upper() in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        filter_letter = filter_letter.upper()
        filtered_squadre = [s for s in squadre if isinstance(s, str) and s.upper().startswith(filter_letter)]
    else:
        filtered_squadre = squadre.copy()
    
    # Rimuovi la squadra o le squadre da escludere se specificate
    if exclude_team:
        if isinstance(exclude_team, list):
            # Se è una lista, rimuovi tutte le squadre nella lista
            for team in exclude_team:
                if team in filtered_squadre:
                    filtered_squadre.remove(team)
        elif exclude_team in filtered_squadre:
            # Se è una singola squadra, rimuovila
            filtered_squadre.remove(exclude_team)
    
    # Ordina le squadre alfabeticamente
    filtered_squadre.sort()
    
    # Calcola il numero totale di pagine
    total_pages = max(1, (len(filtered_squadre) + teams_per_page - 1) // teams_per_page)
    
    # Assicurati che la pagina sia valida
    page = max(1, min(page, total_pages))
    
    # Calcola l'indice di inizio e fine per la pagina corrente
    start_idx = (page - 1) * teams_per_page
    end_idx = min(start_idx + teams_per_page, len(filtered_squadre))
    
    # Seleziona le squadre per la pagina corrente
    current_page_teams = filtered_squadre[start_idx:end_idx]
    
    # Crea la tastiera con le squadre (1 per riga per maggiore leggibilità)
    keyboard = []
    for team in current_page_teams:
        keyboard.append([InlineKeyboardButton(team, callback_data=team)])
    
    # Aggiungi i controlli di navigazione
    nav_row = []
    
    # Pulsante pagina precedente
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prec", callback_data=f"page:{page-1}"))
    
    # Indicatore di pagina
    nav_row.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    
    # Pulsante pagina successiva
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Succ ➡️", callback_data=f"page:{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Aggiungi pulsanti per la ricerca alfabetica
    alphabet_row1 = []
    alphabet_row2 = []
    alphabet_row3 = []
    
    # Prima riga: A-H
    for letter in "ABCDEFGH":
        alphabet_row1.append(InlineKeyboardButton(letter, callback_data=f"filter:{letter}"))
    
    # Seconda riga: I-P
    for letter in "IJKLMNOP":
        alphabet_row2.append(InlineKeyboardButton(letter, callback_data=f"filter:{letter}"))
    
    # Terza riga: Q-Z
    for letter in "QRSTUVWXYZ":
        alphabet_row3.append(InlineKeyboardButton(letter, callback_data=f"filter:{letter}"))
    
    # Aggiungi le righe dell'alfabeto alla tastiera
    keyboard.append(alphabet_row1)
    keyboard.append(alphabet_row2)
    keyboard.append(alphabet_row3)
    
    # Aggiungi pulsante per mostrare tutte le squadre
    keyboard.append([InlineKeyboardButton("🔄 Tutte le squadre", callback_data="filter:all")])
    
    # Aggiungi pulsanti per la ricerca e l'inserimento manuale
    keyboard.append([InlineKeyboardButton("🔍 Cerca squadra", callback_data="search_team")])
    keyboard.append([InlineKeyboardButton("➕ Altra squadra", callback_data="altra_squadra")])
    
    return InlineKeyboardMarkup(keyboard)

# Callback per la selezione del tipo di partita
async def tipo_partita_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione del tipo di partita."""
    query = update.callback_query
    await query.answer()
    
    try:
        tipo_partita = query.data
        context.user_data['tipo_partita'] = tipo_partita
        
        # Inizializza o resetta le variabili di paginazione e ricerca
        context.user_data['team_page'] = 1
        context.user_data['team_search'] = None
        
        # Aggiorna lo stato corrente
        context.user_data['stato_corrente'] = SQUADRA1
        
        # Genera la barra di avanzamento
        barra_avanzamento = genera_barra_avanzamento(SQUADRA1, tipo_partita)
        
        # Genera il riepilogo dei dati inseriti finora
        riepilogo = genera_riepilogo_dati(context)
        
        # Carica le squadre disponibili
        squadre = get_squadre_list()
        
        # Crea la tastiera con paginazione
        reply_markup = create_teams_keyboard(squadre, page=1, filter_letter=None)
        
        # Prepara il messaggio con barra di avanzamento e riepilogo
        messaggio = f"{barra_avanzamento}\n\n"
        messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
        
        if riepilogo:
            messaggio += f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
        
        messaggio += "<b>Seleziona la prima squadra:</b>\n\n"
        messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        return SQUADRA1
    except Exception as e:
        logger.error(f"Errore nella selezione del tipo di partita: {e}")
        await query.edit_message_text(
            "Si è verificato un errore nella selezione del tipo di partita. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per la selezione della prima squadra
async def squadra1_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione della prima squadra."""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            callback_data = query.data
            
            # Gestione della paginazione
            if callback_data.startswith("page:"):
                # Estrai il numero di pagina
                page = int(callback_data.split(":")[1])
                context.user_data['team_page'] = page
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=page,
                    search_query=context.user_data.get('team_search'),
                    filter_letter=context.user_data.get('filter_letter')
                )
            
            # Gestione del filtro alfabetico
            elif callback_data.startswith("filter:"):
                # Estrai la lettera di filtro
                filter_value = callback_data.split(":")[1]
                
                # Se è "all", rimuovi il filtro
                if filter_value == "all":
                    context.user_data.pop('filter_letter', None)
                else:
                    context.user_data['filter_letter'] = filter_value
                
                # Resetta la pagina a 1
                context.user_data['team_page'] = 1
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione e filtro
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=1,
                    search_query=context.user_data.get('team_search'),
                    filter_letter=context.user_data.get('filter_letter')
                )
                
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA1, context.user_data.get('tipo_partita', 'normale'))
                
                # Genera il riepilogo dei dati inseriti finora
                riepilogo = genera_riepilogo_dati(context)
                
                # Prepara il messaggio con barra di avanzamento e riepilogo
                messaggio = f"{barra_avanzamento}\n\n"
                messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                
                if riepilogo:
                    messaggio += f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                
                # Aggiungi informazioni sulla ricerca o filtro se presente
                if context.user_data.get('team_search'):
                    messaggio += f"<b>Ricerca:</b> \"{context.user_data['team_search']}\"\n\n"
                elif context.user_data.get('filter_letter'):
                    messaggio += f"<b>Filtro:</b> Squadre che iniziano con '{context.user_data['filter_letter']}'\n\n"
                
                messaggio += "<b>Seleziona la prima squadra:</b>\n\n"
                messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
                
                await query.edit_message_text(
                    messaggio,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return SQUADRA1
                
            # Gestione della ricerca
            elif callback_data == "search_team":
                await query.edit_message_text(
                    "🔍 <b>RICERCA SQUADRA</b>\n\n"
                    "Inserisci il nome o parte del nome della squadra che stai cercando:\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                # Imposta un flag per indicare che siamo in modalità ricerca
                context.user_data['team_search_mode'] = 'squadra1'
                return SQUADRA1
                
            # Se l'utente ha selezionato "Altra squadra", chiedi di inserire manualmente
            elif callback_data == "altra_squadra":
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n\n"
                    "<b>Inserisci manualmente il nome della prima squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                return SQUADRA1
                
            # Ignora il click sul pulsante di pagina corrente
            elif callback_data == "noop":
                return SQUADRA1
                
            # Altrimenti, l'utente ha selezionato una squadra
            else:
                squadra = callback_data
                context.user_data['squadra1'] = squadra
                
                # Resetta le variabili di paginazione e ricerca per la seconda squadra
                context.user_data['team_page'] = 1
                context.user_data['team_search'] = None
                
                # Carica le squadre disponibili per la seconda squadra
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione, escludendo la prima squadra
                reply_markup = create_teams_keyboard(squadre, page=1, exclude_team=squadra)
                
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA2, context.user_data.get('tipo_partita', 'normale'))
                
                # Genera il riepilogo dei dati inseriti finora
                context.user_data['stato_corrente'] = SQUADRA2
                riepilogo = genera_riepilogo_dati(context)
                
                await query.edit_message_text(
                    f"{barra_avanzamento}\n\n"
                    "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                    f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                    "<b>Seleziona la seconda squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                return SQUADRA2
        else:
            # L'utente ha inviato un messaggio di testo
            text = update.message.text
            
            # Se siamo in modalità ricerca, usa il testo come query di ricerca
            if context.user_data.get('team_search_mode') == 'squadra1':
                context.user_data['team_search'] = text
                context.user_data['team_page'] = 1
                context.user_data.pop('team_search_mode', None)
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione e ricerca
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=1,
                    search_query=text
                )
                
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA1, context.user_data.get('tipo_partita', 'normale'))
                
                # Genera il riepilogo dei dati inseriti finora
                riepilogo = genera_riepilogo_dati(context)
                
                # Prepara il messaggio con barra di avanzamento e riepilogo
                messaggio = f"{barra_avanzamento}\n\n"
                messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                
                if riepilogo:
                    messaggio += f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                
                messaggio += f"<b>Risultati per:</b> \"{text}\"\n\n"
                messaggio += "<b>Seleziona la prima squadra:</b>\n\n"
                messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
                
                await update.message.reply_text(
                    messaggio,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return SQUADRA1
            else:
                # Altrimenti, l'utente sta inserendo manualmente una squadra
                squadra = text
                context.user_data['squadra1'] = squadra
                
                # Aggiungi la squadra al database solo se l'utente è un amministratore
                from modules.db_manager import aggiungi_squadra
                user_id = update.effective_user.id
                
                # Informa l'utente se non è un amministratore
                if not is_admin(user_id):
                    await update.message.reply_text(
                        "ℹ️ Nota: Solo gli amministratori possono aggiungere nuove squadre al database. "
                        "La squadra inserita sarà utilizzata solo per questa partita."
                    )
                
                aggiungi_squadra(squadra, user_id)
                
                # Carica le squadre disponibili per la seconda squadra
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione, escludendo la prima squadra
                reply_markup = create_teams_keyboard(squadre, page=1, exclude_team=squadra)
                
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA2, context.user_data.get('tipo_partita', 'normale'))
                
                # Genera il riepilogo dei dati inseriti finora
                context.user_data['stato_corrente'] = SQUADRA2
                riepilogo = genera_riepilogo_dati(context)
                
                await update.message.reply_text(
                    f"{barra_avanzamento}\n\n"
                    "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                    f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                    "<b>Seleziona la seconda squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                return SQUADRA2
    except Exception as e:
        logger.error(f"Errore nella selezione della prima squadra: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "Si è verificato un errore nella selezione della prima squadra. Riprova con /nuova."
            )
        else:
            await update.message.reply_text(
                "Si è verificato un errore nella selezione della prima squadra. Riprova con /nuova."
            )
        return ConversationHandler.END

# Callback per la selezione della seconda squadra
async def squadra2_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione della seconda squadra."""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            callback_data = query.data
            
            # Gestione della paginazione
            if callback_data.startswith("page:"):
                # Estrai il numero di pagina
                page = int(callback_data.split(":")[1])
                context.user_data['team_page'] = page
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione, escludendo la prima squadra
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=page,
                    search_query=context.user_data.get('team_search'),
                    exclude_team=context.user_data.get('squadra1'),
                    filter_letter=context.user_data.get('filter_letter')
                )
            
            # Gestione del filtro alfabetico
            elif callback_data.startswith("filter:"):
                # Estrai la lettera di filtro
                filter_value = callback_data.split(":")[1]
                
                # Se è "all", rimuovi il filtro
                if filter_value == "all":
                    context.user_data.pop('filter_letter', None)
                else:
                    context.user_data['filter_letter'] = filter_value
                
                # Resetta la pagina a 1
                context.user_data['team_page'] = 1
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione e filtro
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=1,
                    search_query=context.user_data.get('team_search'),
                    exclude_team=context.user_data.get('squadra1'),
                    filter_letter=context.user_data.get('filter_letter')
                )
                
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA2, context.user_data.get('tipo_partita', 'normale'))
                
                # Genera il riepilogo dei dati inseriti finora
                riepilogo = genera_riepilogo_dati(context)
                
                # Prepara il messaggio con barra di avanzamento e riepilogo
                messaggio = f"{barra_avanzamento}\n\n"
                messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                
                if riepilogo:
                    messaggio += f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                
                # Aggiungi informazioni sulla ricerca o filtro se presente
                if context.user_data.get('team_search'):
                    messaggio += f"<b>Ricerca:</b> \"{context.user_data['team_search']}\"\n\n"
                elif context.user_data.get('filter_letter'):
                    messaggio += f"<b>Filtro:</b> Squadre che iniziano con '{context.user_data['filter_letter']}'\n\n"
                
                messaggio += "<b>Seleziona la seconda squadra:</b>\n\n"
                messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
                
                await query.edit_message_text(
                    messaggio,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return SQUADRA2
                
            # Gestione della ricerca
            elif callback_data == "search_team":
                await query.edit_message_text(
                    "🔍 <b>RICERCA SQUADRA</b>\n\n"
                    "Inserisci il nome o parte del nome della squadra che stai cercando:\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                # Imposta un flag per indicare che siamo in modalità ricerca
                context.user_data['team_search_mode'] = 'squadra2'
                return SQUADRA2
                
            # Se l'utente ha selezionato "Altra squadra", chiedi di inserire manualmente
            elif callback_data == "altra_squadra":
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                    f"<b>Prima squadra:</b> {context.user_data['squadra1']}\n\n"
                    "<b>Inserisci manualmente il nome della seconda squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                return SQUADRA2
                
            # Ignora il click sul pulsante di pagina corrente
            elif callback_data == "noop":
                return SQUADRA2
                
            # Se l'utente ha confermato una nuova squadra
            elif callback_data.startswith("conferma_"):
                # Estrai il nome della squadra dalla stringa "conferma_NOME_SQUADRA"
                squadra = callback_data[9:]  # Rimuovi "conferma_" dal callback_data
                
                # Aggiungi la nuova squadra alla lista delle squadre
                squadre_list = get_squadre_list()
                if squadra not in squadre_list:
                    squadre_list.append(squadra)
                    salva_squadre(squadre_list)
                    logger.info(f"Aggiunta nuova squadra: {squadra}")
                    
                    # Aggiorna la cache delle squadre
                    global _squadre_cache, _squadre_last_load
                    _squadre_cache = squadre_list
                    _squadre_last_load = time.time()
                    
                # Continua con la selezione della squadra
                callback_data = squadra
            
            # Altrimenti, l'utente ha selezionato una squadra
            squadra = callback_data
            
            # Verifica che la seconda squadra sia diversa dalla prima
            if squadra == context.user_data.get('squadra1'):
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA2, context.user_data.get('tipo_partita', 'normale'))
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione, escludendo la prima squadra
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=context.user_data.get('team_page', 1),
                    search_query=context.user_data.get('team_search'),
                    exclude_team=context.user_data.get('squadra1'),
                    filter_letter=context.user_data.get('filter_letter')
                )
                
                await query.edit_message_text(
                    f"{barra_avanzamento}\n\n"
                    "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                    f"<b>DATI INSERITI:</b>\n{genera_riepilogo_dati(context)}\n"
                    "⚠️ <b>La seconda squadra deve essere diversa dalla prima.</b>\n"
                    "<b>Seleziona un'altra squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                return SQUADRA2
                
            # Verifica se ci sono squadre con nomi simili
            from modules.string_utils import find_similar_teams
            squadre_list = get_squadre_list()
            squadre_simili = find_similar_teams(squadra, squadre_list, threshold=0.85)
            
            # Se ci sono squadre simili, chiedi conferma
            if squadre_simili and squadra not in squadre_list:
                # Crea una tastiera con le squadre simili
                keyboard = []
                for team, similarity in squadre_simili[:5]:  # Mostra max 5 squadre simili
                    keyboard.append([InlineKeyboardButton(team, callback_data=team)])
                
                # Aggiungi un pulsante per confermare la squadra inserita
                keyboard.append([InlineKeyboardButton(f"Conferma '{squadra}'", callback_data=f"conferma_{squadra}")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n\n"
                    f"⚠️ Hai inserito '{squadra}', ma ci sono squadre simili nel database.\n\n"
                    "Seleziona una delle squadre esistenti o conferma il nuovo nome:\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                return SQUADRA2
            
            # Salva la seconda squadra
            context.user_data['squadra2'] = squadra
            
            # Se è un triangolare, prepara la selezione della terza squadra
            if context.user_data.get('tipo_partita') == 'triangolare':
                # Resetta le variabili di paginazione e ricerca per la terza squadra
                context.user_data['team_page'] = 1
                context.user_data['team_search'] = None
                
                # Carica le squadre disponibili per la terza squadra
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione, escludendo la prima e la seconda squadra
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=1, 
                    exclude_team=[context.user_data['squadra1'], squadra],
                    filter_letter=context.user_data.get('filter_letter')
                )
                
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA3, context.user_data.get('tipo_partita', 'triangolare'))
                
                # Genera il riepilogo dei dati inseriti finora
                context.user_data['stato_corrente'] = SQUADRA3
                riepilogo = genera_riepilogo_dati(context)
                
                await query.edit_message_text(
                    f"{barra_avanzamento}\n\n"
                    "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                    f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                    "<b>Seleziona la terza squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            else:
                # Per le partite normali, chiedi la data
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                    f"<b>Prima squadra:</b> {context.user_data['squadra1']}\n"
                    f"<b>Seconda squadra:</b> {squadra}\n\n"
                    "<b>Inserisci la data della partita (formato: GG/MM/AAAA):</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
        else:
            # L'utente ha inviato un messaggio di testo
            text = update.message.text
            
            # Se siamo in modalità ricerca, usa il testo come query di ricerca
            if context.user_data.get('team_search_mode') == 'squadra2':
                context.user_data['team_search'] = text
                context.user_data['team_page'] = 1
                context.user_data.pop('team_search_mode', None)
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione e ricerca, escludendo la prima squadra
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=1,
                    search_query=text,
                    exclude_team=context.user_data.get('squadra1'),
                    filter_letter=context.user_data.get('filter_letter')
                )
                
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA2, context.user_data.get('tipo_partita', 'normale'))
                
                # Genera il riepilogo dei dati inseriti finora
                riepilogo = genera_riepilogo_dati(context)
                
                # Prepara il messaggio con barra di avanzamento e riepilogo
                messaggio = f"{barra_avanzamento}\n\n"
                messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                
                if riepilogo:
                    messaggio += f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                
                messaggio += f"<b>Risultati per:</b> \"{text}\"\n\n"
                messaggio += "<b>Seleziona la seconda squadra:</b>\n\n"
                messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
                
                await update.message.reply_text(
                    messaggio,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return SQUADRA2
            else:
                # Altrimenti, l'utente sta inserendo manualmente una squadra
                squadra = text
                
                # Verifica che la seconda squadra sia diversa dalla prima
                if squadra == context.user_data.get('squadra1'):
                    await update.message.reply_text(
                        "⚠️ La seconda squadra deve essere diversa dalla prima. Inserisci un'altra squadra."
                    )
                    return SQUADRA2
                
                # Aggiungi la squadra al database solo se l'utente è un amministratore
                from modules.db_manager import aggiungi_squadra
                user_id = update.effective_user.id
                
                # Informa l'utente se non è un amministratore
                if not is_admin(user_id):
                    await update.message.reply_text(
                        "ℹ️ Nota: Solo gli amministratori possono aggiungere nuove squadre al database. "
                        "La squadra inserita sarà utilizzata solo per questa partita."
                    )
                
                aggiungi_squadra(squadra, user_id)
                
                # Salva la seconda squadra
                context.user_data['squadra2'] = squadra
                
                # Se è un triangolare, prepara la selezione della terza squadra
                if context.user_data.get('tipo_partita') == 'triangolare':
                    # Carica le squadre disponibili per la terza squadra
                    squadre = get_squadre_list()
                    
                    # Crea la tastiera con paginazione, escludendo la prima e la seconda squadra
                    reply_markup = create_teams_keyboard(
                        squadre, 
                        page=1, 
                        exclude_team=[context.user_data['squadra1'], squadra],
                        filter_letter=context.user_data.get('filter_letter')
                    )
                    
                    # Genera la barra di avanzamento
                    barra_avanzamento = genera_barra_avanzamento(SQUADRA3, context.user_data.get('tipo_partita', 'triangolare'))
                    
                    # Genera il riepilogo dei dati inseriti finora
                    context.user_data['stato_corrente'] = SQUADRA3
                    riepilogo = genera_riepilogo_dati(context)
                    
                    await update.message.reply_text(
                        f"{barra_avanzamento}\n\n"
                        "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                        f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                        "<b>Seleziona la terza squadra:</b>\n\n"
                        "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                    return SQUADRA3
                else:
                    # Per le partite normali, chiedi la data
                    # Genera la barra di avanzamento
                    barra_avanzamento = genera_barra_avanzamento(DATA_PARTITA, context.user_data.get('tipo_partita', 'normale'))
                    
                    # Genera il riepilogo dei dati inseriti finora
                    context.user_data['stato_corrente'] = DATA_PARTITA
                    riepilogo = genera_riepilogo_dati(context)
                    
                    await update.message.reply_text(
                        f"{barra_avanzamento}\n\n"
                        "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                        f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                        "<b>Inserisci la data della partita (formato: GG/MM/AAAA):</b>\n\n"
                        "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
        
        context.user_data['squadra2'] = squadra
        
        # Se è un triangolare, chiedi la terza squadra
        if context.user_data.get('tipo_partita') == 'triangolare':
            context.user_data['stato_corrente'] = SQUADRA3
            return SQUADRA3
        else:
            context.user_data['stato_corrente'] = DATA_PARTITA
            return DATA_PARTITA
    except Exception as e:
        logger.error(f"Errore nella selezione della seconda squadra: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "Si è verificato un errore nella selezione della seconda squadra. Riprova con /nuova."
            )
        else:
            await update.message.reply_text(
                "Si è verificato un errore nella selezione della seconda squadra. Riprova con /nuova."
            )
        return ConversationHandler.END

# Callback per la selezione della terza squadra (solo per triangolari)
async def squadra3_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione della terza squadra per i triangolari."""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            callback_data = query.data
            
            # Gestione della paginazione
            if callback_data.startswith("page:"):
                # Estrai il numero di pagina
                page = int(callback_data.split(":")[1])
                context.user_data['team_page'] = page
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione, escludendo la prima e la seconda squadra
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=page,
                    search_query=context.user_data.get('team_search'),
                    exclude_team=[context.user_data.get('squadra1'), context.user_data.get('squadra2')],
                    filter_letter=context.user_data.get('filter_letter')
                )
            
            # Gestione del filtro alfabetico
            elif callback_data.startswith("filter:"):
                # Estrai la lettera di filtro
                filter_value = callback_data.split(":")[1]
                
                # Se è "all", rimuovi il filtro
                if filter_value == "all":
                    context.user_data.pop('filter_letter', None)
                else:
                    context.user_data['filter_letter'] = filter_value
                
                # Resetta la pagina a 1
                context.user_data['team_page'] = 1
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione e filtro
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=1,
                    search_query=context.user_data.get('team_search'),
                    exclude_team=[context.user_data.get('squadra1'), context.user_data.get('squadra2')],
                    filter_letter=context.user_data.get('filter_letter')
                )
                
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA3, context.user_data.get('tipo_partita', 'triangolare'))
                
                # Genera il riepilogo dei dati inseriti finora
                riepilogo = genera_riepilogo_dati(context)
                
                # Prepara il messaggio con barra di avanzamento e riepilogo
                messaggio = f"{barra_avanzamento}\n\n"
                messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                
                if riepilogo:
                    messaggio += f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                
                # Aggiungi informazioni sulla ricerca o filtro se presente
                if context.user_data.get('team_search'):
                    messaggio += f"<b>Ricerca:</b> \"{context.user_data['team_search']}\"\n\n"
                elif context.user_data.get('filter_letter'):
                    messaggio += f"<b>Filtro:</b> Squadre che iniziano con '{context.user_data['filter_letter']}'\n\n"
                
                messaggio += "<b>Seleziona la terza squadra:</b>\n\n"
                messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
                
                await query.edit_message_text(
                    messaggio,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return SQUADRA3
                
            # Gestione della ricerca
            elif callback_data == "search_team":
                await query.edit_message_text(
                    "🔍 <b>RICERCA SQUADRA</b>\n\n"
                    "Inserisci il nome o parte del nome della squadra che stai cercando:\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                # Imposta un flag per indicare che siamo in modalità ricerca
                context.user_data['team_search_mode'] = 'squadra3'
                return SQUADRA3
                
            # Se l'utente ha selezionato "Altra squadra", chiedi di inserire manualmente
            elif callback_data == "altra_squadra":
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                    f"<b>Prima squadra:</b> {context.user_data['squadra1']}\n"
                    f"<b>Seconda squadra:</b> {context.user_data['squadra2']}\n\n"
                    "<b>Inserisci manualmente il nome della terza squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                return SQUADRA3
                
            # Ignora il click sul pulsante di pagina corrente
            elif callback_data == "noop":
                return SQUADRA3
                
            # Altrimenti, l'utente ha selezionato una squadra
            squadra = callback_data
            
            # Verifica che la terza squadra sia diversa dalle altre
            if squadra == context.user_data.get('squadra1') or squadra == context.user_data.get('squadra2'):
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA3, context.user_data.get('tipo_partita', 'triangolare'))
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione, escludendo la prima e la seconda squadra
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=context.user_data.get('team_page', 1),
                    search_query=context.user_data.get('team_search'),
                    exclude_team=[context.user_data.get('squadra1'), context.user_data.get('squadra2')]
                )
                
                await query.edit_message_text(
                    f"{barra_avanzamento}\n\n"
                    "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                    f"<b>DATI INSERITI:</b>\n{genera_riepilogo_dati(context)}\n"
                    "⚠️ <b>La terza squadra deve essere diversa dalle altre.</b>\n"
                    "<b>Seleziona un'altra squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                return SQUADRA3
            
            # Salva la terza squadra
            context.user_data['squadra3'] = squadra
            
            # Genera la barra di avanzamento
            barra_avanzamento = genera_barra_avanzamento(DATA_PARTITA, context.user_data.get('tipo_partita', 'triangolare'))
            
            # Genera il riepilogo dei dati inseriti finora
            context.user_data['stato_corrente'] = DATA_PARTITA
            riepilogo = genera_riepilogo_dati(context)
            
            await query.edit_message_text(
                f"{barra_avanzamento}\n\n"
                "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                "<b>Inserisci la data della partita (formato: GG/MM/AAAA):</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
        else:
            # L'utente ha inviato un messaggio di testo
            text = update.message.text
            
            # Se siamo in modalità ricerca, usa il testo come query di ricerca
            if context.user_data.get('team_search_mode') == 'squadra3':
                context.user_data['team_search'] = text
                context.user_data['team_page'] = 1
                context.user_data.pop('team_search_mode', None)
                
                # Carica le squadre disponibili
                squadre = get_squadre_list()
                
                # Crea la tastiera con paginazione e ricerca, escludendo la prima e la seconda squadra
                reply_markup = create_teams_keyboard(
                    squadre, 
                    page=1,
                    search_query=text,
                    exclude_team=[context.user_data.get('squadra1'), context.user_data.get('squadra2')]
                )
                
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(SQUADRA3, context.user_data.get('tipo_partita', 'triangolare'))
                
                # Genera il riepilogo dei dati inseriti finora
                riepilogo = genera_riepilogo_dati(context)
                
                # Prepara il messaggio con barra di avanzamento e riepilogo
                messaggio = f"{barra_avanzamento}\n\n"
                messaggio += "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                
                if riepilogo:
                    messaggio += f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                
                messaggio += f"<b>Risultati per:</b> \"{text}\"\n\n"
                messaggio += "<b>Seleziona la terza squadra:</b>\n\n"
                messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
                
                await update.message.reply_text(
                    messaggio,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return SQUADRA3
            else:
                # Altrimenti, l'utente sta inserendo manualmente una squadra
                squadra = text
                
                # Verifica che la terza squadra sia diversa dalle altre
                if squadra == context.user_data.get('squadra1') or squadra == context.user_data.get('squadra2'):
                    await update.message.reply_text(
                        "⚠️ La terza squadra deve essere diversa dalle altre. Inserisci un'altra squadra."
                    )
                    return SQUADRA3
                
                # Aggiungi la squadra al database solo se l'utente è un amministratore
                from modules.db_manager import aggiungi_squadra
                user_id = update.effective_user.id
                
                # Informa l'utente se non è un amministratore
                if not is_admin(user_id):
                    await update.message.reply_text(
                        "ℹ️ Nota: Solo gli amministratori possono aggiungere nuove squadre al database. "
                        "La squadra inserita sarà utilizzata solo per questa partita."
                    )
                
                aggiungi_squadra(squadra, user_id)
                
                # Salva la terza squadra
                context.user_data['squadra3'] = squadra
                
                # Genera la barra di avanzamento
                barra_avanzamento = genera_barra_avanzamento(DATA_PARTITA, context.user_data.get('tipo_partita', 'triangolare'))
                
                # Genera il riepilogo dei dati inseriti finora
                context.user_data['stato_corrente'] = DATA_PARTITA
                riepilogo = genera_riepilogo_dati(context)
                
                await update.message.reply_text(
                    f"{barra_avanzamento}\n\n"
                    "🏉 <b>NUOVA PARTITA</b> 🏉\n\n"
                    f"<b>DATI INSERITI:</b>\n{riepilogo}\n"
                    "<b>Inserisci la data della partita (formato: GG/MM/AAAA):</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                return DATA_PARTITA
            
        return DATA_PARTITA
    except Exception as e:
        logger.error(f"Errore nella selezione della terza squadra: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "Si è verificato un errore nella selezione della terza squadra. Riprova con /nuova."
            )
        else:
            await update.message.reply_text(
                "Si è verificato un errore nella selezione della terza squadra. Riprova con /nuova."
            )
        return ConversationHandler.END

# Callback per l'inserimento della data della partita
async def data_partita_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento della data della partita."""
    try:
        data = update.message.text
        
        # Verifica che la data sia nel formato corretto
        try:
            data_partita = datetime.strptime(data, '%d/%m/%Y')
            
            # Verifica che la data non sia nel futuro
            oggi = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if data_partita > oggi:
                await update.message.reply_text(
                    "⚠️ Non è possibile inserire partite con date future. Inserisci una data valida."
                )
                return DATA_PARTITA
                
            # Verifica che la data non sia troppo nel passato (es. più di 1 anno fa)
            un_anno_fa = oggi - timedelta(days=365)
            if data_partita < un_anno_fa:
                await update.message.reply_text(
                    "⚠️ La data inserita è troppo lontana nel passato (più di un anno fa). "
                    "Se stai inserendo una partita storica, contatta un amministratore."
                )
                return DATA_PARTITA
        except ValueError:
            await update.message.reply_text(
                "⚠️ Formato data non valido. Inserisci la data nel formato GG/MM/AAAA (es. 01/01/2023)."
            )
            return DATA_PARTITA
        
        context.user_data['data_partita'] = data
        
        # Se è un triangolare, chiedi i punteggi della prima partita
        if context.user_data.get('tipo_partita') == 'triangolare':
            await update.message.reply_text(
                f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {data}\n\n"
                f"<b>Prima partita:</b> {context.user_data['squadra1']} vs {context.user_data['squadra2']}\n\n"
                f"<b>Inserisci il punteggio di {context.user_data['squadra1']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = PUNTEGGIO1
            return PUNTEGGIO1
        else:
            # Per le partite normali, chiedi direttamente i punteggi
            await update.message.reply_text(
                f"🏉 <b>Partita:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {data}\n"
                f"<b>{context.user_data['squadra1']} vs {context.user_data['squadra2']}</b>\n\n"
                f"<b>Inserisci il punteggio di {context.user_data['squadra1']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = PUNTEGGIO1
            return PUNTEGGIO1
    except Exception as e:
        logger.error(f"Errore nell'inserimento della data: {e}")
        await update.message.reply_text(
            "Si è verificato un errore nell'inserimento della data. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per l'inserimento del punteggio della prima squadra
async def punteggio1_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento del punteggio della prima squadra."""
    try:
        punteggio = update.message.text
        
        # Verifica che il punteggio sia un numero intero
        try:
            punteggio = int(punteggio)
            if punteggio < 0:
                raise ValueError("Il punteggio non può essere negativo")
        except ValueError:
            await update.message.reply_text(
                "⚠️ Il punteggio deve essere un numero intero non negativo. Inserisci nuovamente il punteggio."
            )
            return PUNTEGGIO1
        
        # Verifica se stiamo inserendo la terza partita di un triangolare
        if context.user_data.get('inserendo_terza_partita'):
            # Stiamo inserendo la terza partita (squadra2 vs squadra3)
            context.user_data['punteggio2_vs_3'] = punteggio
            
            # Chiedi il punteggio della terza squadra contro la seconda
            await update.message.reply_text(
                f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
                f"<b>Prima partita:</b> {context.user_data['squadra1']} {context.user_data['punteggio1']} - {context.user_data['punteggio2']} {context.user_data['squadra2']}\n"
                f"<b>Mete:</b> {context.user_data['mete1']} - {context.user_data['mete2']}\n\n"
                f"<b>Seconda partita:</b> {context.user_data['squadra1']} {context.user_data['punteggio1_vs_3']} - {context.user_data['punteggio3_vs_1']} {context.user_data['squadra3']}\n"
                f"<b>Mete:</b> {context.user_data['mete1_vs_3']} - {context.user_data['mete3_vs_1']}\n\n"
                f"<b>Terza partita:</b> {context.user_data['squadra2']} {punteggio} - ? {context.user_data['squadra3']}\n\n"
                f"<b>Inserisci il punteggio di {context.user_data['squadra3']} contro {context.user_data['squadra2']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = PUNTEGGIO2
            return PUNTEGGIO2
        # Verifica se stiamo inserendo la seconda partita di un triangolare
        elif context.user_data.get('tipo_partita') == 'triangolare' and 'punteggio1_vs_2' in context.user_data:
            # Stiamo inserendo la seconda partita (squadra1 vs squadra3)
            context.user_data['punteggio1_vs_3'] = punteggio
            
            # Chiedi il punteggio della terza squadra contro la prima
            await update.message.reply_text(
                f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
                f"<b>Seconda partita:</b> {context.user_data['squadra1']} {punteggio} - ? {context.user_data['squadra3']}\n\n"
                f"<b>Inserisci il punteggio di {context.user_data['squadra3']} contro {context.user_data['squadra1']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = PUNTEGGIO2
            return PUNTEGGIO2
        else:
            # Prima partita normale o prima partita di un triangolare
            context.user_data['punteggio1'] = punteggio
            
            # Chiedi il punteggio della seconda squadra
            await update.message.reply_text(
                f"🏉 <b>Partita:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n"
                f"<b>{context.user_data['squadra1']} {punteggio} - ? {context.user_data['squadra2']}</b>\n\n"
                f"<b>Inserisci il punteggio di {context.user_data['squadra2']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = PUNTEGGIO2
            return PUNTEGGIO2
    except Exception as e:
        logger.error(f"Errore nell'inserimento del punteggio: {e}")
        await update.message.reply_text(
            "Si è verificato un errore nell'inserimento del punteggio. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per l'inserimento del punteggio della seconda squadra
async def punteggio2_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento del punteggio della seconda squadra."""
    try:
        punteggio = update.message.text
        
        # Verifica che il punteggio sia un numero intero
        try:
            punteggio = int(punteggio)
            if punteggio < 0:
                raise ValueError("Il punteggio non può essere negativo")
        except ValueError:
            await update.message.reply_text(
                "⚠️ Il punteggio deve essere un numero intero non negativo. Inserisci nuovamente il punteggio."
            )
            return PUNTEGGIO2
        
        # Verifica se stiamo inserendo la terza partita di un triangolare
        if context.user_data.get('inserendo_terza_partita'):
            # Stiamo inserendo la terza partita (squadra2 vs squadra3)
            context.user_data['punteggio3_vs_2'] = punteggio
            
            # Chiedi le mete della seconda squadra contro la terza
            await update.message.reply_text(
                f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
                f"<b>Terza partita:</b> {context.user_data['squadra2']} {context.user_data['punteggio2_vs_3']} - {punteggio} {context.user_data['squadra3']}\n\n"
                f"<b>Inserisci il numero di mete di {context.user_data['squadra2']} contro {context.user_data['squadra3']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = METE1
            return METE1
        # Verifica se stiamo inserendo la seconda partita di un triangolare
        elif context.user_data.get('tipo_partita') == 'triangolare' and 'punteggio1_vs_2' in context.user_data:
            # Stiamo inserendo la seconda partita (squadra1 vs squadra3)
            context.user_data['punteggio3_vs_1'] = punteggio
            
            # Chiedi le mete della prima squadra contro la terza
            await update.message.reply_text(
                f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
                f"<b>Seconda partita:</b> {context.user_data['squadra1']} {context.user_data['punteggio1_vs_3']} - {punteggio} {context.user_data['squadra3']}\n\n"
                f"<b>Inserisci il numero di mete di {context.user_data['squadra1']} contro {context.user_data['squadra3']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = METE1
            return METE1
        else:
            # Prima partita normale o prima partita di un triangolare
            context.user_data['punteggio2'] = punteggio
            
            # Chiedi le mete della prima squadra
            await update.message.reply_text(
                f"🏉 <b>Partita:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n"
                f"<b>{context.user_data['squadra1']} {context.user_data['punteggio1']} - {punteggio} {context.user_data['squadra2']}</b>\n\n"
                f"<b>Inserisci il numero di mete di {context.user_data['squadra1']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = METE1
            return METE1
    except Exception as e:
        logger.error(f"Errore nell'inserimento del punteggio: {e}")
        await update.message.reply_text(
            "Si è verificato un errore nell'inserimento del punteggio. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per l'inserimento delle mete della prima squadra
async def mete1_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento delle mete della prima squadra."""
    try:
        mete = update.message.text
        
        # Verifica che il numero di mete sia un numero intero
        try:
            mete = int(mete)
            if mete < 0:
                raise ValueError("Il numero di mete non può essere negativo")
                
            # Verifica la congruenza tra punteggio e mete per la prima squadra
            punteggio = context.user_data.get('punteggio1', 0)
            if context.user_data.get('inserendo_terza_partita'):
                punteggio = context.user_data.get('punteggio2_vs_3', 0)
            elif context.user_data.get('tipo_partita') == 'triangolare' and 'mete1_vs_2' in context.user_data:
                punteggio = context.user_data.get('punteggio1_vs_3', 0)
                
            # Verifica che il punteggio sia congruente con le mete
            congruente, messaggio = verifica_congruenza_punteggio_mete(punteggio, mete)
            if not congruente:
                await update.message.reply_text(
                    f"⚠️ {messaggio}\n\nInserisci nuovamente il numero di mete."
                )
                return METE1
        except ValueError:
            await update.message.reply_text(
                "⚠️ Il numero di mete deve essere un numero intero non negativo. Inserisci nuovamente il numero di mete."
            )
            return METE1
        
        # Verifica se stiamo inserendo la terza partita di un triangolare
        if context.user_data.get('inserendo_terza_partita'):
            # Stiamo inserendo la terza partita (squadra2 vs squadra3)
            context.user_data['mete2_vs_3'] = mete
            
            # Chiedi le mete della terza squadra contro la seconda
            await update.message.reply_text(
                f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
                f"<b>Terza partita:</b> {context.user_data['squadra2']} {context.user_data['punteggio2_vs_3']} - {context.user_data['punteggio3_vs_2']} {context.user_data['squadra3']}\n"
                f"<b>Mete:</b> {mete} - ?\n\n"
                f"<b>Inserisci il numero di mete di {context.user_data['squadra3']} contro {context.user_data['squadra2']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = METE2
            return METE2
        # Verifica se stiamo inserendo la seconda partita di un triangolare
        elif context.user_data.get('tipo_partita') == 'triangolare' and 'mete1_vs_2' in context.user_data:
            # Stiamo inserendo la seconda partita (squadra1 vs squadra3)
            context.user_data['mete1_vs_3'] = mete
            
            # Chiedi le mete della terza squadra contro la prima
            await update.message.reply_text(
                f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
                f"<b>Seconda partita:</b> {context.user_data['squadra1']} {context.user_data['punteggio1_vs_3']} - {context.user_data['punteggio3_vs_1']} {context.user_data['squadra3']}\n"
                f"<b>Mete:</b> {mete} - ?\n\n"
                f"<b>Inserisci il numero di mete di {context.user_data['squadra3']} contro {context.user_data['squadra1']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = METE2
            return METE2
        else:
            # Prima partita normale o prima partita di un triangolare
            context.user_data['mete1'] = mete
            
            # Chiedi le mete della seconda squadra
            await update.message.reply_text(
                f"🏉 <b>Partita:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n"
                f"<b>{context.user_data['squadra1']} {context.user_data['punteggio1']} - {context.user_data['punteggio2']} {context.user_data['squadra2']}</b>\n"
                f"<b>Mete:</b> {mete} - ?\n\n"
                f"<b>Inserisci il numero di mete di {context.user_data['squadra2']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = METE2
            return METE2
    except Exception as e:
        logger.error(f"Errore nell'inserimento delle mete: {e}")
        await update.message.reply_text(
            "Si è verificato un errore nell'inserimento delle mete. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per l'inserimento delle mete della seconda squadra
async def mete2_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento delle mete della seconda squadra."""
    try:
        mete = update.message.text
        
        # Verifica che il numero di mete sia un numero intero
        try:
            mete = int(mete)
            if mete < 0:
                raise ValueError("Il numero di mete non può essere negativo")
                
            # Verifica la congruenza tra punteggio e mete per la seconda squadra
            punteggio = context.user_data.get('punteggio2', 0)
            if context.user_data.get('inserendo_terza_partita'):
                punteggio = context.user_data.get('punteggio3_vs_2', 0)
            elif context.user_data.get('tipo_partita') == 'triangolare' and 'mete1_vs_3' in context.user_data:
                punteggio = context.user_data.get('punteggio3_vs_1', 0)
                
            # Verifica che il punteggio sia congruente con le mete
            congruente, messaggio = verifica_congruenza_punteggio_mete(punteggio, mete)
            if not congruente:
                await update.message.reply_text(
                    f"⚠️ {messaggio}\n\nInserisci nuovamente il numero di mete."
                )
                return METE2
        except ValueError:
            await update.message.reply_text(
                "⚠️ Il numero di mete deve essere un numero intero non negativo. Inserisci nuovamente il numero di mete."
            )
            return METE2
        
        # Verifica se stiamo inserendo la terza partita di un triangolare
        if context.user_data.get('inserendo_terza_partita'):
            # Stiamo inserendo la terza partita (squadra2 vs squadra3)
            context.user_data['mete3_vs_2'] = mete
            
            # Chiedi il nome dell'arbitro
            await update.message.reply_text(
                f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
                f"<b>Prima partita:</b> {context.user_data['squadra1']} {context.user_data['punteggio1']} - {context.user_data['punteggio2']} {context.user_data['squadra2']}\n"
                f"<b>Mete:</b> {context.user_data['mete1']} - {context.user_data['mete2']}\n\n"
                f"<b>Seconda partita:</b> {context.user_data['squadra1']} {context.user_data['punteggio1_vs_3']} - {context.user_data['punteggio3_vs_1']} {context.user_data['squadra3']}\n"
                f"<b>Mete:</b> {context.user_data['mete1_vs_3']} - {context.user_data['mete3_vs_1']}\n\n"
                f"<b>Terza partita:</b> {context.user_data['squadra2']} {context.user_data['punteggio2_vs_3']} - {context.user_data['punteggio3_vs_2']} {context.user_data['squadra3']}\n"
                f"<b>Mete:</b> {context.user_data['mete2_vs_3']} - {mete}\n\n"
                "<b>Inserisci il nome dell'arbitro:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = ARBITRO
            return ARBITRO
        # Verifica se stiamo inserendo la seconda partita di un triangolare
        elif context.user_data.get('tipo_partita') == 'triangolare' and 'mete1_vs_3' in context.user_data:
            # Stiamo inserendo la seconda partita (squadra1 vs squadra3)
            context.user_data['mete3_vs_1'] = mete
            
            # Chiedi i punteggi della terza partita (squadra2 vs squadra3)
            await update.message.reply_text(
                f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
                f"<b>Prima partita:</b> {context.user_data['squadra1']} {context.user_data['punteggio1']} - {context.user_data['punteggio2']} {context.user_data['squadra2']}\n"
                f"<b>Mete:</b> {context.user_data['mete1']} - {context.user_data['mete2']}\n\n"
                f"<b>Seconda partita:</b> {context.user_data['squadra1']} {context.user_data['punteggio1_vs_3']} - {context.user_data['punteggio3_vs_1']} {context.user_data['squadra3']}\n"
                f"<b>Mete:</b> {context.user_data['mete1_vs_3']} - {mete}\n\n"
                f"<b>Terza partita:</b> {context.user_data['squadra2']} vs {context.user_data['squadra3']}\n\n"
                f"<b>Inserisci il punteggio di {context.user_data['squadra2']} contro {context.user_data['squadra3']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            # Salviamo un flag per indicare che stiamo inserendo la terza partita
            context.user_data['inserendo_terza_partita'] = True
            
            # Chiedi il punteggio della squadra2 contro squadra3
            context.user_data['stato_corrente'] = PUNTEGGIO1
            return PUNTEGGIO1
        elif context.user_data.get('tipo_partita') == 'triangolare':
            # Stiamo inserendo la prima partita di un triangolare
            context.user_data['mete2'] = mete
            
            # Salva i punteggi della prima partita con nomi specifici
            context.user_data['punteggio1_vs_2'] = context.user_data['punteggio1']
            context.user_data['punteggio2_vs_1'] = context.user_data['punteggio2']
            context.user_data['mete1_vs_2'] = context.user_data['mete1']
            context.user_data['mete2_vs_1'] = context.user_data['mete2']
            
            # Chiedi i punteggi della seconda partita (squadra1 vs squadra3)
            await update.message.reply_text(
                f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
                f"<b>Prima partita:</b> {context.user_data['squadra1']} {context.user_data['punteggio1']} - {context.user_data['punteggio2']} {context.user_data['squadra2']}\n"
                f"<b>Mete:</b> {context.user_data['mete1']} - {mete}\n\n"
                f"<b>Seconda partita:</b> {context.user_data['squadra1']} vs {context.user_data['squadra3']}\n\n"
                f"<b>Inserisci il punteggio di {context.user_data['squadra1']} contro {context.user_data['squadra3']}:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            # Chiedi il punteggio della squadra1 contro squadra3
            context.user_data['stato_corrente'] = PUNTEGGIO1
            return PUNTEGGIO1
        else:
            # Partita normale
            context.user_data['mete2'] = mete
            
            # Chiedi l'arbitro
            await update.message.reply_text(
                f"🏉 <b>Partita:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Data:</b> {context.user_data['data_partita']}\n"
                f"<b>{context.user_data['squadra1']} {context.user_data['punteggio1']} - {context.user_data['punteggio2']} {context.user_data['squadra2']}</b>\n"
                f"<b>Mete:</b> {context.user_data['mete1']} - {mete}\n\n"
                "<b>Inserisci il nome dell'arbitro:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = ARBITRO
            return ARBITRO
    except Exception as e:
        logger.error(f"Errore nell'inserimento delle mete: {e}")
        await update.message.reply_text(
            "Si è verificato un errore nell'inserimento delle mete. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per l'inserimento del nome dell'arbitro
async def arbitro_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento del nome dell'arbitro."""
    try:
        arbitro = update.message.text
        
        # Verifica che il nome dell'arbitro sia in un formato valido
        if len(arbitro) < 3 or len(arbitro) > 50 or not any(c.isalpha() for c in arbitro):
            await update.message.reply_text(
                "⚠️ Il nome dell'arbitro non sembra valido. Inserisci un nome completo (min 3 caratteri, max 50)."
            )
            return ARBITRO
            
        context.user_data['arbitro'] = arbitro
        
        # Crea i pulsanti per la selezione della sezione arbitrale
        keyboard = []
        row = []
        
        for i, sezione in enumerate(SEZIONI_ARBITRALI):
            row.append(InlineKeyboardButton(sezione, callback_data=sezione))
            
            # Crea una nuova riga ogni 2 elementi
            if (i + 1) % 2 == 0 or i == len(SEZIONI_ARBITRALI) - 1:
                keyboard.append(row)
                row = []
        
        # Aggiungi un pulsante per "Altra sezione"
        keyboard.append([InlineKeyboardButton("Altra sezione", callback_data="altra_sezione")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Chiedi la sezione arbitrale
        if context.user_data.get('tipo_partita') == 'triangolare':
            messaggio = f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
        else:
            messaggio = f"🏉 <b>Partita:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
            
        messaggio += f"<b>Data:</b> {context.user_data['data_partita']}\n"
        messaggio += f"<b>Arbitro:</b> {arbitro}\n\n"
        messaggio += "<b>Seleziona la sezione arbitrale di appartenenza:</b>\n\n"
        messaggio += "<i>Puoi annullare in qualsiasi momento con /annulla</i>"
        
        await update.message.reply_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        context.user_data['stato_corrente'] = SEZIONE_ARBITRALE
        return SEZIONE_ARBITRALE
    except Exception as e:
        logger.error(f"Errore nell'inserimento dell'arbitro: {e}")
        await update.message.reply_text(
            "Si è verificato un errore nell'inserimento dell'arbitro. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per la selezione della sezione arbitrale
async def sezione_arbitrale_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione della sezione arbitrale."""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            sezione = query.data
            
            # Se l'utente ha selezionato "Altra sezione", chiedi di inserire manualmente
            if sezione == "altra_sezione":
                await query.edit_message_text(
                    f"🏉 <b>Arbitro:</b> {context.user_data['arbitro']} 🏉\n\n"
                    "<b>Inserisci manualmente la sezione arbitrale:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                return SEZIONE_ARBITRALE
            
            context.user_data['sezione_arbitrale'] = sezione
        else:
            sezione = update.message.text
            
            # Verifica che la sezione arbitrale sia in un formato valido
            if len(sezione) < 2 or len(sezione) > 30 or not any(c.isalpha() for c in sezione):
                await update.message.reply_text(
                    "⚠️ La sezione arbitrale non sembra valida. Inserisci un nome valido (min 2 caratteri, max 30)."
                )
                return SEZIONE_ARBITRALE
                
            context.user_data['sezione_arbitrale'] = sezione
            
        # Mostra il riepilogo e chiedi conferma
        messaggio = f"🏉 <b>RIEPILOGO PARTITA</b> 🏉\n\n"
        
        # Gestione diversa per partite normali e triangolari
        if context.user_data.get('tipo_partita') == 'triangolare':
            messaggio += f"<b>TRIANGOLARE</b>\n\n"
            messaggio += f"<b>Squadre partecipanti:</b>\n"
            messaggio += f"• {context.user_data['squadra1']}\n"
            messaggio += f"• {context.user_data['squadra2']}\n"
            messaggio += f"• {context.user_data['squadra3']}\n\n"
            
            messaggio += f"<b>Risultati:</b>\n"
            
            # Partita 1: Squadra1 vs Squadra2
            punteggio1 = int(context.user_data.get('punteggio1_vs_2', 0))
            punteggio2 = int(context.user_data.get('punteggio2_vs_1', 0))
            mete1 = int(context.user_data.get('mete1_vs_2', 0))
            mete2 = int(context.user_data.get('mete2_vs_1', 0))
            
            if punteggio1 > punteggio2:
                messaggio += f"• <b>{context.user_data['squadra1']}</b> <code>{punteggio1}:{punteggio2}</code> {context.user_data['squadra2']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"• {context.user_data['squadra1']} <code>{punteggio1}:{punteggio2}</code> <b>{context.user_data['squadra2']}</b> 🏆\n"
            else:
                messaggio += f"• {context.user_data['squadra1']} <code>{punteggio1}:{punteggio2}</code> {context.user_data['squadra2']} 🤝\n"
            
            # Partita 2: Squadra1 vs Squadra3
            punteggio1 = int(context.user_data.get('punteggio1_vs_3', 0))
            punteggio2 = int(context.user_data.get('punteggio3_vs_1', 0))
            mete1 = int(context.user_data.get('mete1_vs_3', 0))
            mete2 = int(context.user_data.get('mete3_vs_1', 0))
            
            if punteggio1 > punteggio2:
                messaggio += f"• <b>{context.user_data['squadra1']}</b> <code>{punteggio1}:{punteggio2}</code> {context.user_data['squadra3']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"• {context.user_data['squadra1']} <code>{punteggio1}:{punteggio2}</code> <b>{context.user_data['squadra3']}</b> 🏆\n"
            else:
                messaggio += f"• {context.user_data['squadra1']} <code>{punteggio1}:{punteggio2}</code> {context.user_data['squadra3']} 🤝\n"
            
            # Partita 3: Squadra2 vs Squadra3
            punteggio1 = int(context.user_data.get('punteggio2_vs_3', 0))
            punteggio2 = int(context.user_data.get('punteggio3_vs_2', 0))
            mete1 = int(context.user_data.get('mete2_vs_3', 0))
            mete2 = int(context.user_data.get('mete3_vs_2', 0))
            
            if punteggio1 > punteggio2:
                messaggio += f"• <b>{context.user_data['squadra2']}</b> <code>{punteggio1}:{punteggio2}</code> {context.user_data['squadra3']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"• {context.user_data['squadra2']} <code>{punteggio1}:{punteggio2}</code> <b>{context.user_data['squadra3']}</b> 🏆\n"
            else:
                messaggio += f"• {context.user_data['squadra2']} <code>{punteggio1}:{punteggio2}</code> {context.user_data['squadra3']} 🤝\n"
        else:
            # Partita normale
            messaggio += f"<b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']}\n"
            messaggio += f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
            messaggio += f"<b>{context.user_data['squadra1']} {context.user_data['punteggio1']} - {context.user_data['punteggio2']} {context.user_data['squadra2']}</b>\n"
            messaggio += f"<b>Mete:</b> {context.user_data['mete1']} - {context.user_data['mete2']}\n"
        
        messaggio += f"\n<b>Arbitro:</b> {context.user_data['arbitro']} ({context.user_data['sezione_arbitrale']})\n\n"
        messaggio += "Confermi l'inserimento di questa partita?"
        
        # Crea i pulsanti per la conferma
        keyboard = [
            [
                InlineKeyboardButton("✅ Conferma", callback_data="conferma"),
                InlineKeyboardButton("❌ Annulla", callback_data="annulla")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Gestisci diversamente a seconda che l'aggiornamento provenga da un messaggio o da un callback query
        if update.callback_query:
            await update.callback_query.edit_message_text(
                messaggio,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        else:
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(
                messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        context.user_data['stato_corrente'] = CONFERMA
        return CONFERMA
    except Exception as e:
        logger.error(f"Errore nella gestione della sezione arbitrale: {e}")
        
        error_message = "Si è verificato un errore nell'inserimento della sezione arbitrale. Riprova con /nuova."
        
        # Gestisci diversamente a seconda che l'aggiornamento provenga da un messaggio o da un callback query
        if update.callback_query:
            await update.callback_query.edit_message_text(
                error_message,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                error_message,
                parse_mode='HTML'
            )
        
        return ConversationHandler.END

# Callback per la conferma dell'inserimento
async def punteggio3_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento del punteggio della terza squadra in un triangolare."""
    try:
        punteggio = update.message.text
        
        # Verifica che il punteggio sia un numero intero
        try:
            punteggio = int(punteggio)
            if punteggio < 0:
                raise ValueError("Il punteggio non può essere negativo")
        except ValueError:
            await update.message.reply_text(
                "⚠️ Il punteggio deve essere un numero intero non negativo. Inserisci nuovamente il punteggio."
            )
            return PUNTEGGIO3
        
        context.user_data['punteggio3'] = punteggio
        
        # Chiedi le mete della terza squadra
        await update.message.reply_text(
            f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
            f"<b>Data:</b> {context.user_data['data_partita']}\n"
            f"<b>Squadre:</b> {context.user_data['squadra1']}, {context.user_data['squadra2']}, {context.user_data['squadra3']}\n\n"
            f"<b>Inserisci il numero di mete di {context.user_data['squadra3']}:</b>\n\n"
            "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
            parse_mode='HTML'
        )
        
        context.user_data['stato_corrente'] = METE3
        return METE3
    except Exception as e:
        logger.error(f"Errore nell'inserimento del punteggio: {e}")
        await update.message.reply_text(
            "Si è verificato un errore nell'inserimento del punteggio. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per l'inserimento delle mete della terza squadra (triangolare)
async def mete3_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento delle mete della terza squadra in un triangolare."""
    try:
        mete = update.message.text
        
        # Verifica che il numero di mete sia un numero intero
        try:
            mete = int(mete)
            if mete < 0:
                raise ValueError("Il numero di mete non può essere negativo")
        except ValueError:
            await update.message.reply_text(
                "⚠️ Il numero di mete deve essere un numero intero non negativo. Inserisci nuovamente il numero di mete."
            )
            return METE3
        
        context.user_data['mete3'] = mete
        
        # Chiedi il nome dell'arbitro
        await update.message.reply_text(
            f"🏉 <b>Triangolare:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
            f"<b>Data:</b> {context.user_data['data_partita']}\n"
            f"<b>Squadre:</b> {context.user_data['squadra1']}, {context.user_data['squadra2']}, {context.user_data['squadra3']}\n\n"
            "<b>Inserisci il nome dell'arbitro:</b>\n\n"
            "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
            parse_mode='HTML'
        )
        
        context.user_data['stato_corrente'] = ARBITRO
        return ARBITRO
    except Exception as e:
        logger.error(f"Errore nell'inserimento delle mete: {e}")
        await update.message.reply_text(
            "Si è verificato un errore nell'inserimento delle mete. Riprova con /nuova."
        )
        return ConversationHandler.END



# Comando /risultati
async def risultati_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra gli ultimi risultati inseriti."""
    user_id = update.effective_user.id
    
    # Verifica che l'utente sia autorizzato
    if not is_utente_autorizzato(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Non sei autorizzato a utilizzare questo comando.\n"
            "Usa /start per richiedere l'accesso."
        )
        return
    
    # Carica i risultati
    risultati = carica_risultati()
    
    if not risultati:
        await update.message.reply_html(
            "Non ci sono ancora risultati inseriti."
        )
        return
    
    # Mostra gli ultimi 5 risultati
    messaggio = "<b>📋 ULTIMI RISULTATI</b>\n\n"
    
    # Ordina i risultati per data (dal più recente)
    def get_date_key(x):
        data_partita = x.get('data_partita')
        if data_partita is None or data_partita == '':
            return datetime.strptime('01/01/2000', '%d/%m/%Y')
        try:
            return datetime.strptime(data_partita, '%d/%m/%Y')
        except ValueError:
            # In caso di formato data non valido, usa una data predefinita
            return datetime.strptime('01/01/2000', '%d/%m/%Y')
    
    risultati_ordinati = sorted(
        risultati, 
        key=get_date_key,
        reverse=True
    )
    
    # Prendi gli ultimi 5 risultati
    ultimi_risultati = risultati_ordinati[:5]
    
    for i, risultato in enumerate(ultimi_risultati, 1):
        categoria = risultato.get('categoria', 'N/D')
        genere = risultato.get('genere', '')
        info_categoria = f"{categoria} {genere}".strip()
        tipo_partita = risultato.get('tipo_partita', 'normale')
        
        messaggio += f"{i}. <b>{info_categoria}</b> - {risultato.get('data_partita', 'N/D')}\n"
        
        if tipo_partita == 'triangolare':
            # Mostra i risultati del triangolare
            messaggio += f"   <b>TRIANGOLARE</b>\n"
            
            # Partita 1: Squadra1 vs Squadra2
            punteggio1 = int(risultato.get('partita1_punteggio1', 0))
            punteggio2 = int(risultato.get('partita1_punteggio2', 0))
            mete1 = int(risultato.get('partita1_mete1', 0))
            mete2 = int(risultato.get('partita1_mete2', 0))
            
            messaggio += f"   • <b>{risultato['squadra1']}</b> {punteggio1} - {punteggio2} <b>{risultato['squadra2']}</b>\n"
            messaggio += f"     Mete: {mete1} - {mete2}\n"
            
            # Partita 2: Squadra1 vs Squadra3
            punteggio1 = int(risultato.get('partita2_punteggio1', 0))
            punteggio2 = int(risultato.get('partita2_punteggio2', 0))
            mete1 = int(risultato.get('partita2_mete1', 0))
            mete2 = int(risultato.get('partita2_mete2', 0))
            
            messaggio += f"   • <b>{risultato['squadra1']}</b> {punteggio1} - {punteggio2} <b>{risultato['squadra3']}</b>\n"
            messaggio += f"     Mete: {mete1} - {mete2}\n"
            
            # Partita 3: Squadra2 vs Squadra3
            punteggio1 = int(risultato.get('partita3_punteggio1', 0))
            punteggio2 = int(risultato.get('partita3_punteggio2', 0))
            mete1 = int(risultato.get('partita3_mete1', 0))
            mete2 = int(risultato.get('partita3_mete2', 0))
            
            messaggio += f"   • <b>{risultato['squadra2']}</b> {punteggio1} - {punteggio2} <b>{risultato['squadra3']}</b>\n"
            messaggio += f"     Mete: {mete1} - {mete2}\n"
        else:
            # Mostra i risultati della partita normale
            messaggio += f"   <b>{risultato['squadra1']}</b> {risultato['punteggio1']} - {risultato['punteggio2']} <b>{risultato['squadra2']}</b>\n"
            messaggio += f"   Mete: {risultato['mete1']} - {risultato['mete2']}\n"
        
        messaggio += "\n"
    
    await update.message.reply_html(messaggio)

# Funzione per gestire la ricerca degli utenti
async def cerca_utente_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce la ricerca degli utenti tramite ID."""
    # Verifica che l'utente sia un amministratore
    if not is_admin(update.effective_user.id):
        await update.message.reply_html(
            "⚠️ Solo gli amministratori possono cercare gli utenti."
        )
        return
    
    # Verifica che l'utente stia aspettando di cercare un utente
    if not context.user_data.get('attesa_ricerca_utente', False):
        return
    
    # Estrai l'ID utente dal messaggio
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_html(
            "⚠️ L'ID utente deve essere un numero intero. Riprova."
        )
        return
    
    # Carica gli utenti
    utenti = carica_utenti()
    
    # Cerca l'utente tra gli autorizzati
    utente_trovato = None
    stato = None
    
    for utente in utenti["autorizzati"]:
        if isinstance(utente, dict) and utente.get("id") == user_id:
            utente_trovato = utente
            stato = "autorizzato"
            break
        elif not isinstance(utente, dict) and utente == user_id:
            utente_trovato = {"id": user_id, "nome": f"Utente {user_id}", "username": None, "data_registrazione": None}
            stato = "autorizzato"
            break
    
    # Se non trovato tra gli autorizzati, cerca tra quelli in attesa
    if not utente_trovato:
        for utente in utenti["in_attesa"]:
            if isinstance(utente, dict) and utente.get("id") == user_id:
                utente_trovato = utente
                stato = "in_attesa"
                break
            elif not isinstance(utente, dict) and utente == user_id:
                utente_trovato = {"id": user_id, "nome": f"Utente {user_id}", "username": None, "data_registrazione": None}
                stato = "in_attesa"
                break
    
    # Resetta lo stato di attesa
    context.user_data['attesa_ricerca_utente'] = False
    
    # Se l'utente è stato trovato, mostra le informazioni
    if utente_trovato:
        messaggio = f"<b>🔍 UTENTE TROVATO</b>\n\n"
        messaggio += f"<b>ID:</b> {utente_trovato.get('id')}\n"
        messaggio += f"<b>Nome:</b> {utente_trovato.get('nome', 'N/D')}\n"
        messaggio += f"<b>Username:</b> @{utente_trovato.get('username', 'N/D')}\n"
        messaggio += f"<b>Data registrazione:</b> {utente_trovato.get('data_registrazione', 'N/D')}\n"
        messaggio += f"<b>Stato:</b> {'Autorizzato' if stato == 'autorizzato' else 'In attesa di approvazione'}\n"
        
        # Crea i pulsanti in base allo stato dell'utente
        keyboard = []
        
        if stato == "autorizzato":
            # Verifica se l'utente è admin
            ruolo = utente_trovato.get("ruolo", "utente")
            if ruolo == "admin":
                keyboard.append([
                    InlineKeyboardButton("⬇️ Declassa", callback_data=f"declassa_{user_id}"),
                    InlineKeyboardButton("❌ Rimuovi", callback_data=f"rimuovi_{user_id}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton("⬆️ Promuovi", callback_data=f"promuovi_{user_id}"),
                    InlineKeyboardButton("❌ Rimuovi", callback_data=f"rimuovi_{user_id}")
                ])
        else:  # in_attesa
            keyboard.append([
                InlineKeyboardButton("✅ Approva", callback_data=f"approva_{user_id}"),
                InlineKeyboardButton("❌ Rifiuta", callback_data=f"rifiuta_{user_id}")
            ])
        
        # Aggiungi pulsanti per tornare alle liste
        keyboard.append([
            InlineKeyboardButton("👥 Utenti autorizzati", callback_data="mostra_autorizzati:1"),
            InlineKeyboardButton("👥 Utenti in attesa", callback_data="mostra_in_attesa:1")
        ])
        
        # Aggiungi pulsante per tornare al menu
        keyboard.append([
            InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            messaggio,
            reply_markup=reply_markup
        )
    else:
        # Se l'utente non è stato trovato
        keyboard = [
            [InlineKeyboardButton("👥 Utenti autorizzati", callback_data="mostra_autorizzati:1")],
            [InlineKeyboardButton("👥 Utenti in attesa", callback_data="mostra_in_attesa:1")],
            [InlineKeyboardButton("◀️ Torna al menu", callback_data="menu_torna")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            f"⚠️ <b>Utente non trovato</b>\n\n"
            f"Nessun utente trovato con ID {user_id}.",
            reply_markup=reply_markup
        )

# Comando /squadre per gestire le squadre
async def squadre_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce le squadre (solo per amministratori)."""
    user_id = update.effective_user.id
    
    # Verifica che l'utente sia un amministratore
    if not is_admin(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Solo gli amministratori possono gestire le squadre."
        )
        return
    
    # Carica le squadre
    squadre = get_squadre_list()
    
    # Crea il messaggio
    messaggio = "<b>🏉 GESTIONE SQUADRE</b>\n\n"
    
    if squadre:
        messaggio += "Squadre attualmente registrate:\n\n"
        for i, squadra in enumerate(squadre, 1):
            messaggio += f"{i}. {squadra}\n"
    else:
        messaggio += "Non ci sono squadre registrate."
    
    messaggio += "\n<i>Per aggiungere una nuova squadra, usa il comando /aggiungi_squadra seguito dal nome della squadra.</i>"
    
    await update.message.reply_html(messaggio)

# Comando /aggiungi_squadra per aggiungere una nuova squadra
async def aggiungi_squadra_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Aggiunge una nuova squadra (solo per amministratori)."""
    user_id = update.effective_user.id
    
    # Verifica che l'utente sia un amministratore
    if not is_admin(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Solo gli amministratori possono aggiungere squadre."
        )
        return
    
    # Verifica che sia stato fornito un nome per la squadra
    if not context.args:
        await update.message.reply_html(
            "⚠️ <b>Nome squadra mancante</b>\n\n"
            "Devi specificare il nome della squadra da aggiungere.\n"
            "Esempio: /aggiungi_squadra \"Nome Squadra\""
        )
        return
    
    # Estrai il nome della squadra
    nome_squadra = " ".join(context.args)
    
    # Aggiungi la squadra
    from modules.db_manager import aggiungi_squadra
    if aggiungi_squadra(nome_squadra, user_id):
        await update.message.reply_html(
            f"✅ <b>Squadra aggiunta</b>\n\n"
            f"La squadra <b>{nome_squadra}</b> è stata aggiunta con successo."
        )
    else:
        await update.message.reply_html(
            f"❌ <b>Errore</b>\n\n"
            f"Si è verificato un errore durante l'aggiunta della squadra <b>{nome_squadra}</b>."
        )

# Funzione per verificare se un'altra istanza del bot è in esecuzione
def check_single_instance():
    """
    Verifica che solo un'istanza del bot sia in esecuzione.
    Utilizza un file di lock per maggiore affidabilità in ambienti cloud.
    """
    # Verifica se siamo su Render
    is_render = os.environ.get('RENDER') is not None
    
    # Se siamo su Render, ignora il controllo delle istanze multiple
    # Render gestisce già i processi e garantisce che ci sia solo un'istanza
    if is_render:
        logger.info("Ambiente Render rilevato. Ignorando il controllo delle istanze multiple.")
        return True
    
    # Percorso del file di lock
    lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot.lock')
    
    try:
        # Verifica se il file di lock esiste
        if os.path.exists(lock_file):
            # Controlla se il processo è ancora attivo
            with open(lock_file, 'r') as f:
                try:
                    pid = int(f.read().strip())
                    # Verifica se il processo è ancora in esecuzione
                    try:
                        # In Unix/Linux
                        os.kill(pid, 0)
                        # Se arriviamo qui, il processo esiste ancora
                        logger.error(f"Un'altra istanza del bot è già in esecuzione (PID: {pid}). Uscita in corso...")
                        return False
                    except OSError:
                        # Il processo non esiste più, possiamo sovrascrivere il file di lock
                        logger.warning(f"File di lock trovato, ma il processo {pid} non esiste più. Sovrascrittura...")
                except (ValueError, TypeError):
                    # Il file di lock è corrotto, possiamo sovrascriverlo
                    logger.warning("File di lock corrotto. Sovrascrittura...")
        
        # Crea o sovrascrive il file di lock con il PID corrente
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        # Registra una funzione per rimuovere il file di lock all'uscita
        def cleanup():
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except Exception as e:
                logger.error(f"Errore nella rimozione del file di lock: {e}")
        
        atexit.register(cleanup)
        
        logger.info(f"Nessun'altra istanza del bot in esecuzione. Lock creato (PID: {os.getpid()}).")
        return True
    except Exception as e:
        logger.error(f"Errore nel controllo/creazione del file di lock: {e}")
        # In caso di errore, permettiamo comunque l'avvio del bot
        logger.warning("Ignorando l'errore e continuando con l'avvio del bot...")
        return True

# Funzione principale per avviare il bot
def main() -> None:
    """Avvia il bot."""
    # Verifica che solo un'istanza sia in esecuzione
    # Su Render, questa verifica viene ignorata
    if not check_single_instance():
        # Se non siamo su Render, esci
        if not os.environ.get('RENDER'):
            sys.exit(1)
        else:
            # Su Render, continuiamo comunque
            logger.warning("Continuando con l'avvio del bot nonostante il rilevamento di un'altra istanza...")
    
    # Crea l'applicazione con configurazioni ottimizzate
    try:
        # Crea l'applicazione
        application = Application.builder().token(TOKEN).build()
        
        # Importa il JobManager alternativo
        try:
            from modules.job_manager import job_manager
            logger.info("JobManager alternativo importato con successo.")
        except Exception as job_error:
            logger.error(f"Errore nell'importazione del JobManager alternativo: {job_error}")
            
    except Exception as e:
        logger.error(f"Errore nella creazione dell'applicazione: {e}")
        # Fallback: crea l'applicazione senza opzioni aggiuntive
        application = Application.builder().token(TOKEN).build()

    # Precarica i dati in cache all'avvio
    logger.info("Precaricamento dati in cache...")
    carica_risultati()
    carica_utenti()
    carica_reazioni()
    carica_squadre()
    logger.info("Precaricamento completato")

    # Aggiungi i gestori dei comandi
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("dashboard", dashboard_command))
    application.add_handler(CommandHandler("squadre", squadre_command))
    application.add_handler(CommandHandler("aggiungi_squadra", aggiungi_squadra_command))
    application.add_handler(CommandHandler("health", health_command))
    
    # Aggiungi il gestore per i callback delle query inline
    application.add_handler(CallbackQueryHandler(reaction_callback, pattern=r"^(reaction:|view_reactions:)"))
    application.add_handler(CallbackQueryHandler(dashboard_callback, pattern=r"^dashboard_"))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu_"))
    application.add_handler(CallbackQueryHandler(pubblica_riepilogo_callback, pattern=r"^pubblica_riepilogo$"))
    application.add_handler(CallbackQueryHandler(esporta_excel_riepilogo_callback, pattern=r"^esporta_excel_riepilogo$"))
    application.add_handler(CallbackQueryHandler(esporta_pdf_riepilogo_callback, pattern=r"^esporta_pdf_riepilogo$"))
    application.add_handler(CallbackQueryHandler(approva_utente_callback, pattern=r"^approva_"))
    application.add_handler(CallbackQueryHandler(rifiuta_utente_callback, pattern=r"^rifiuta_"))
    application.add_handler(CallbackQueryHandler(promuovi_utente_callback, pattern=r"^promuovi_"))
    application.add_handler(CallbackQueryHandler(declassa_utente_callback, pattern=r"^declassa_"))
    application.add_handler(CallbackQueryHandler(gestione_utenti_callback, pattern=r"^(mostra_autorizzati|mostra_in_attesa|cerca_utente|rimuovi_)"))
    application.add_handler(CallbackQueryHandler(health_callback, pattern=r"^health_"))
    
    # Aggiungi il gestore per la conversazione di inserimento nuova partita
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("nuova", nuova_partita),
            CallbackQueryHandler(nuova_partita, pattern="^menu_nuova$"),
            CallbackQueryHandler(nuova_partita, pattern="^dashboard_nuova$")
        ],
        states={
            CATEGORIA: [
                CallbackQueryHandler(categoria_callback)
            ],
            GENERE: [
                CallbackQueryHandler(genere_callback)
            ],
            TIPO_PARTITA: [
                CallbackQueryHandler(tipo_partita_callback)
            ],
            SQUADRA1: [
                CallbackQueryHandler(squadra1_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, squadra1_callback)
            ],
            SQUADRA2: [
                CallbackQueryHandler(squadra2_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, squadra2_callback)
            ],
            SQUADRA3: [
                CallbackQueryHandler(squadra3_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, squadra3_callback)
            ],
            DATA_PARTITA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, data_partita_callback)
            ],
            PUNTEGGIO1: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, punteggio1_callback)
            ],
            PUNTEGGIO2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, punteggio2_callback)
            ],
            PUNTEGGIO3: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, punteggio3_callback)
            ],
            METE1: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mete1_callback)
            ],
            METE2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mete2_callback)
            ],
            SEZIONE_ARBITRALE: [
                CallbackQueryHandler(sezione_arbitrale_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sezione_arbitrale_callback)
            ],
            METE3: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mete3_callback)
            ],
            ARBITRO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, arbitro_callback)
            ],
            CONFERMA: [
                CallbackQueryHandler(conferma_callback)
            ],
        },
        fallbacks=[CommandHandler("annulla", annulla)],
    )
    application.add_handler(conv_handler)
    
    # Aggiungi il gestore per il comando risultati
    application.add_handler(CommandHandler("risultati", risultati_command))
    
    # Aggiungi il gestore per la ricerca degli utenti
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        cerca_utente_handler
    ))
    
    # Aggiungi il gestore degli errori
    application.add_error_handler(error)
    
    # Registra i gestori per i quiz
    try:
        from modules.quiz_handlers import register_quiz_handlers
        register_quiz_handlers(application)
        
        # Configura i job per i quiz dopo aver registrato i gestori
        from modules.quiz_manager import configura_job_quiz
        configura_job_quiz(application, CHANNEL_ID)
        
        logger.info("Funzionalità quiz registrate con successo")
    except Exception as e:
        logger.error(f"Errore nella registrazione delle funzionalità quiz: {e}")
    
    # Configura il job per inviare automaticamente il riepilogo ogni domenica alle 18:00
    try:
        from datetime import time as dt_time
        job_time = dt_time(hour=18, minute=0, second=0)  # 18:00:00
        
        # Utilizza esclusivamente il JobManager alternativo
        try:
            from modules.job_manager import job_manager
            
            # Wrapper per adattare la funzione al formato richiesto dal JobManager
            async def job_wrapper(context_data):
                # Crea un contesto fittizio con il bot
                class FakeContext:
                    def __init__(self, bot):
                        self.bot = bot
                        self.user_data = {}
                        self.chat_data = {}
                        self.bot_data = {}
                
                fake_context = FakeContext(application.bot)
                await invia_riepilogo_automatico(fake_context)
                
               # Pianifica il job con il JobManager alternativo
            job_manager.run_daily(job_wrapper, job_time, days=[6], name="riepilogo_automatico")
            logger.info("Job scheduler alternativo configurato per inviare il riepilogo ogni domenica alle 18:00")
        except Exception as alt_error:
            logger.error(f"Errore nella configurazione del job scheduler alternativo: {alt_error}")
    except Exception as e:
        logger.error(f"Errore nella configurazione del job scheduler: {e}")
    
    # Configurazioni ottimizzate per il polling
    logger.info("Avvio del bot con configurazioni ottimizzate...")
    
    # Prova a cancellare eventuali webhook configurati
    try:
        from telegram.ext import Updater
        bot = application.bot
        bot.delete_webhook()
        logger.info("Webhook cancellato con successo.")
    except Exception as e:
        logger.warning(f"Errore nella cancellazione del webhook: {e}")
    
    # Avvia il polling con configurazioni ottimizzate
    try:
        # Verifica la versione della libreria python-telegram-bot
        import telegram
        version = telegram.__version__
        logger.info(f"Versione di python-telegram-bot: {version}")
        
        # Configurazioni di base supportate in tutte le versioni
        polling_config = {
            "drop_pending_updates": True,  # Ignora gli aggiornamenti in sospeso
            "allowed_updates": ["message", "callback_query", "inline_query"],  # Limita gli aggiornamenti da processare
        }
        
        # Aggiungi configurazioni specifiche per la versione 20+
        if version.startswith("20.") or version.startswith("21.") or version.startswith("22."):
            # Nella versione 20+ alcuni parametri sono stati rinominati o rimossi
            polling_config["poll_interval"] = 1.0  # Intervallo tra le richieste di polling
            
            # Nella versione 20+ i timeout sono gestiti internamente
            # Non possiamo configurarli direttamente come parametri di run_polling
            
            logger.info("Avvio del polling con configurazioni per python-telegram-bot 20+")
        else:
            # Per versioni precedenti, usa i parametri diretti
            polling_config.update({
                "timeout": 30,
                "read_timeout": 30,
                "write_timeout": 30,
                "connect_timeout": 30,
                "pool_timeout": 30,
            })
            logger.info("Avvio del polling con configurazioni per python-telegram-bot <20")
        
        # Avvia il polling con le configurazioni appropriate
        application.run_polling(**polling_config)
    except Exception as e:
        logger.error(f"Errore nell'avvio del polling: {e}")
        # Se siamo su Render, non uscire ma continua con il server HTTP
        if os.environ.get('RENDER'):
            logger.warning("Errore nell'avvio del bot, ma continuando con il server HTTP per soddisfare i requisiti di Render...")
            return
        else:
            # In ambiente di sviluppo, mostra l'errore completo
            import traceback
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            raise

# Classe per gestire le richieste HTTP
# Importa il gestore delle richieste web
from modules.web_server import WebRequestHandler

# Funzione per avviare il server HTTP
def run_http_server():
    # Ottieni la porta da Render o usa 8080 come default
    port = int(os.environ.get('PORT', 8080))
    server_address = ('', port)
    httpd = HTTPServer(server_address, WebRequestHandler)
    logger.info(f"Avvio server HTTP sulla porta {port}...")
    logger.info(f"Dashboard web disponibile su http://localhost:{port}/")
    httpd.serve_forever()

def start_keep_alive():
    """Avvia il meccanismo di keep-alive per mantenere attivo il bot su Render."""
    try:
        from keep_alive import start_ping_thread
        keep_alive_thread = start_ping_thread()
        logger.info("Meccanismo di keep-alive avviato con successo.")
        return keep_alive_thread
    except ImportError:
        logger.warning("Modulo keep_alive non trovato. Il bot potrebbe essere disattivato dopo 15 minuti di inattività.")
        return None
    except Exception as e:
        logger.error(f"Errore nell'avvio del meccanismo di keep-alive: {e}")
        return None

if __name__ == "__main__":
    # Avvia il server HTTP in un thread separato
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # Verifica se siamo su Render
    is_render = os.environ.get('RENDER') is not None
    
    # Se siamo su Render, avvia il meccanismo di keep-alive
    keep_alive_thread = None
    if is_render:
        logger.info("Ambiente Render rilevato. Avvio del meccanismo di keep-alive...")
        keep_alive_thread = start_keep_alive()
    
    # Su Render, avviamo sempre il bot
    try:
        if is_render:
            logger.info("Avvio del bot in ambiente Render...")
            main()
        else:
            # In ambiente locale, verifichiamo che non ci siano altre istanze
            can_start_bot = check_single_instance()
            if can_start_bot:
                logger.info("Avvio del bot in ambiente locale...")
                main()
            else:
                logger.warning("Non è possibile avviare il bot a causa di un'altra istanza in esecuzione.")
                sys.exit(1)
    except Exception as e:
        logger.error(f"Errore nell'avvio del bot: {e}")
        # Se non siamo su Render, esci
        if not is_render:
            sys.exit(1)
        else:
            logger.warning("Continuando con il server HTTP nonostante l'errore nell'avvio del bot...")
    
    # Se siamo su Render, mantieni comunque il processo in esecuzione per il server HTTP
    if is_render:
        logger.info("Mantenendo attivo il server HTTP...")
        # Mantieni il processo principale in esecuzione
        try:
            while True:
                time.sleep(60)  # Controlla ogni minuto
                logger.info("Server HTTP ancora attivo...")
                
                # Verifica se il meccanismo di keep-alive è attivo
                if not keep_alive_thread:
                    logger.info("Riavvio del meccanismo di keep-alive...")
                    keep_alive_thread = start_keep_alive()
        except KeyboardInterrupt:
            logger.info("Interruzione rilevata. Uscita in corso...")
            sys.exit(0)