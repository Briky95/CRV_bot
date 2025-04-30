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
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from modules.export_manager import genera_excel_riepilogo_weekend, genera_pdf_riepilogo_weekend
from modules.db_manager import carica_utenti, salva_utenti, carica_risultati, salva_risultati, carica_squadre, salva_squadre

# Abilita logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Stati della conversazione
CATEGORIA, GENERE, TIPO_PARTITA, SQUADRA1, SQUADRA2, SQUADRA3, DATA_PARTITA, PUNTEGGIO1, PUNTEGGIO2, PUNTEGGIO3, METE1, METE2, METE3, ARBITRO, CONFERMA = range(15)

# Categorie di rugby predefinite
CATEGORIE = ["Serie A Elite", "Serie A", "Serie B", "Serie C1", "U18 Nazionale", "U18", "U16", "U14"]

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
    squadre_dict = carica_squadre()
    # Appiattisci il dizionario in una lista di tutte le squadre
    squadre_list = []
    for categoria, squadre in squadre_dict.items():
        squadre_list.extend(squadre)
    
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

# Funzione per caricare le reazioni
def carica_reazioni(force_reload=False):
    current_time = time.time()
    
    # Usa la cache se disponibile e non scaduta
    if not force_reload and _cache['reazioni'] is not None and (current_time - _cache['last_load']['reazioni']) < CACHE_TTL:
        return _cache['reazioni']
    
    if os.path.exists(REAZIONI_FILE):
        with open(REAZIONI_FILE, 'r', encoding='utf-8') as file:
            try:
                reazioni = json.load(file)
                # Aggiorna la cache
                _cache['reazioni'] = reazioni
                _cache['last_load']['reazioni'] = current_time
                return reazioni
            except json.JSONDecodeError:
                logger.error("Errore nel parsing del file delle reazioni")
                return {}
    return {}

# Funzione per salvare le reazioni
def salva_reazioni(reazioni):
    with open(REAZIONI_FILE, 'w', encoding='utf-8') as file:
        json.dump(reazioni, file, indent=2, ensure_ascii=False)
    
    # Aggiorna la cache
    _cache['reazioni'] = reazioni
    _cache['last_load']['reazioni'] = time.time()

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

# Comando /menu
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra un menu con tutte le funzioni disponibili."""
    user_id = update.effective_user.id
    
    # Verifica che l'utente sia autorizzato
    if not is_utente_autorizzato(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Non sei autorizzato a utilizzare questo comando.\n"
            "Usa /start per richiedere l'accesso."
        )
        return
    
    # Crea i pulsanti per le funzioni standard
    keyboard = [
        [InlineKeyboardButton("📝 Inserisci nuova partita", callback_data="menu_nuova")],
        [InlineKeyboardButton("🏁 Ultimi risultati", callback_data="menu_risultati")],
        [InlineKeyboardButton("📊 Statistiche", callback_data="menu_statistiche")]
    ]
    
    # Aggiungi il pulsante per il riepilogo weekend solo per gli admin
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🗓️ Riepilogo weekend", callback_data="menu_riepilogo_weekend")])
    
    # Aggiungi pulsanti per le funzioni amministrative se l'utente è un admin
    if is_admin(user_id):
        keyboard.extend([
            [InlineKeyboardButton("👥 Gestione utenti", callback_data="menu_utenti")],
            [InlineKeyboardButton("🔄 Test canale", callback_data="menu_test_canale")]
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        "<b>🏉 MENU PRINCIPALE</b>\n\n"
        "Seleziona una funzione:",
        reply_markup=reply_markup
    )

# Funzione per creare i pulsanti di reazione per i messaggi del canale
def crea_pulsanti_reazione(message_id=None, include_export=False):
    """Crea i pulsanti di reazione per i messaggi del canale."""
    # Definisci le reazioni disponibili
    reazioni = [
        ("👍", "like"),
        ("❤️", "love"),
        ("🔥", "fire"),
        ("👏", "clap"),
        ("🏉", "rugby")
    ]
    
    # Crea i pulsanti con i callback_data che includono l'ID del messaggio
    buttons = []
    for emoji, reaction_type in reazioni:
        callback_data = f"reaction:{reaction_type}"
        if message_id:
            callback_data += f":{message_id}"
        buttons.append(InlineKeyboardButton(emoji, callback_data=callback_data))
    
    # Aggiungi un pulsante per vedere chi ha reagito
    if message_id:
        buttons.append(InlineKeyboardButton("👥 Vedi reazioni", callback_data=f"view_reactions:{message_id}"))
    
    keyboard = [buttons]
    
    # Aggiungi i pulsanti per l'esportazione se richiesto
    if include_export and message_id:
        export_buttons = [
            InlineKeyboardButton("📊 Esporta Excel", callback_data="esporta_excel_riepilogo"),
            InlineKeyboardButton("📄 Esporta PDF", callback_data="esporta_pdf_riepilogo")
        ]
        keyboard.append(export_buttons)
    
    return keyboard

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
async def invia_messaggio_canale(context, risultato):
    """Invia un messaggio con il risultato della partita al canale Telegram."""
    try:
        # Verifica che l'ID del canale sia stato configurato correttamente
        if CHANNEL_ID == "@nome_canale" or not CHANNEL_ID:
            logger.error("ID del canale Telegram non configurato correttamente. Modifica la costante CHANNEL_ID nel file bot.py.")
            return False, "ID del canale non configurato correttamente"
        
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
                    return False, f"Manca il campo {key} nei dati del triangolare"
                
                # Assicurati che i valori siano numeri interi
                if key.startswith('partita') and key.endswith(('punteggio1', 'punteggio2', 'mete1', 'mete2')):
                    try:
                        risultato[key] = int(risultato[key])
                    except (ValueError, TypeError):
                        logger.error(f"Il campo {key} non è un numero valido: {risultato[key]}")
                        return False, f"Il campo {key} non è un numero valido"
            
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
        sent_message = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=messaggio,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Salva l'ID del messaggio e aggiorna i pulsanti con l'ID
        message_id = sent_message.message_id
        keyboard = crea_pulsanti_reazione(message_id)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.edit_message_reply_markup(
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
        return True, message_id
    
    except Exception as e:
        logger.error(f"Errore nell'invio del messaggio al canale: {e}")
        return False, str(e)

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
    
    # Crea il messaggio con il riepilogo in formato più accattivante
    messaggio = f"🏆 <b>RIEPILOGO WEEKEND RUGBY</b> 🏆\n"
    messaggio += f"📅 <i>Weekend del {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')}</i>\n"
    messaggio += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
    messaggio += f"<i>Ecco tutti i risultati delle partite giocate questo weekend nel Comitato Regionale Veneto.</i>\n\n"
    
    for categoria, partite in risultati_per_categoria.items():
        # Aggiungi un'icona diversa in base alla categoria
        if "Elite" in categoria:
            icona = "🔝"
        elif "Serie A" in categoria:
            icona = "🏆"
        elif "Serie B" in categoria:
            icona = "🥈"
        elif "Serie C" in categoria:
            icona = "🥉"
        elif "U18" in categoria:
            icona = "👦"
        elif "U16" in categoria:
            icona = "👦"
        elif "U14" in categoria:
            icona = "👦"
        else:
            icona = "📋"
            
        messaggio += f"\n<b>{icona} {categoria.upper()}</b>\n"
        messaggio += "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        
        for p in partite:
            # Determina il vincitore
            punteggio1 = int(p.get('punteggio1', 0))
            punteggio2 = int(p.get('punteggio2', 0))
            
            # Abbrevia i nomi delle squadre se sono troppo lunghi
            squadra1 = p.get('squadra1', '')
            squadra2 = p.get('squadra2', '')
            
            if len(squadra1) > 20:
                squadra1 = squadra1[:17] + "..."
            if len(squadra2) > 20:
                squadra2 = squadra2[:17] + "..."
            
            # Formatta il risultato in modo più leggibile
            if punteggio1 > punteggio2:
                risultato = f"<b>{squadra1}</b> <code>{punteggio1}:{punteggio2}</code> {squadra2} 🏆"
            elif punteggio2 > punteggio1:
                risultato = f"{squadra1} <code>{punteggio1}:{punteggio2}</code> <b>{squadra2}</b> 🏆"
            else:
                risultato = f"{squadra1} <code>{punteggio1}:{punteggio2}</code> {squadra2} 🤝"
            
            # Aggiungi la data della partita se disponibile
            data_partita = p.get('data_partita', '')
            if data_partita:
                data_display = f"<i>({data_partita})</i> "
            else:
                data_display = ""
                
            messaggio += f"• {data_display}{risultato}\n"
        
        messaggio += "\n"
    
    # Aggiungi statistiche del weekend in formato più dettagliato e visivamente accattivante
    totale_partite = len(risultati_weekend)
    totale_punti = sum(int(r.get('punteggio1', 0)) + int(r.get('punteggio2', 0)) for r in risultati_weekend)
    totale_mete = sum(int(r.get('mete1', 0)) + int(r.get('mete2', 0)) for r in risultati_weekend)
    
    # Calcola la media di punti e mete per partita
    media_punti = round(totale_punti / totale_partite, 1) if totale_partite > 0 else 0
    media_mete = round(totale_mete / totale_partite, 1) if totale_partite > 0 else 0
    
    messaggio += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    messaggio += f"<b>📊 STATISTICHE WEEKEND</b>\n\n"
    messaggio += f"🏟️ <b>Partite giocate:</b> {totale_partite}\n"
    messaggio += f"🔢 <b>Punti totali:</b> {totale_punti} (media: {media_punti} per partita)\n"
    messaggio += f"🏉 <b>Mete totali:</b> {totale_mete} (media: {media_mete} per partita)\n\n"
    
    # Aggiungi il disclaimer in formato più elegante
    messaggio += "<i>⚠️ Tutti i risultati sono in attesa di omologazione ufficiale da parte del Giudice Sportivo</i>"
    
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
            f"Usa /nuova per inserire una nuova partita\n"
            f"Usa /risultati per vedere le ultime partite inserite"
        )
    else:
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
    
    # Verifica che l'utente sia autorizzato
    if not is_utente_autorizzato(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Non sei autorizzato a utilizzare questo comando.\n"
            "Usa /start per richiedere l'accesso."
        )
        return
    
    await update.message.reply_html(
        "<b>🏉 GUIDA AL BOT</b>\n\n"
        "Questo bot ti permette di inserire e visualizzare i risultati delle partite di rugby del CRV.\n\n"
        "<b>Comandi disponibili:</b>\n"
        "/start - Avvia il bot e richiedi l'accesso\n"
        "/menu - Mostra il menu principale\n"
        "/nuova - Inserisci una nuova partita\n"
        "/risultati - Visualizza gli ultimi risultati\n"
        "/help - Mostra questo messaggio di aiuto\n\n"
        "<b>Come inserire una nuova partita:</b>\n"
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
    """Avvia il processo di inserimento di una nuova partita."""
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
            await update.message.reply_html(
                "⚠️ <b>Accesso non autorizzato</b>\n\n"
                "Non sei autorizzato a utilizzare questo comando.\n"
                "Usa /start per richiedere l'accesso."
            )
        return ConversationHandler.END
    
    # Carica le squadre
    context.user_data['squadre_disponibili'] = carica_squadre()
    
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
        # Verifica se è un callback o un comando
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(
                "🏉 <b>Nuova Partita</b> 🏉\n\n"
                "Seleziona la categoria della partita:\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "🏉 <b>Nuova Partita</b> 🏉\n\n"
                "Seleziona la categoria della partita:\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        
        # Salva lo stato corrente
        context.user_data['stato_corrente'] = CATEGORIA
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
                f"Si è verificato un errore: {e}\nRiprova più tardi.",
                parse_mode='HTML'
            )
        return ConversationHandler.END

# Funzione per annullare la conversazione
async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Annulla la conversazione corrente."""
    # Pulisci i dati utente
    context.user_data.clear()
    
    await update.message.reply_text(
        "❌ Operazione annullata.\n\n"
        "Usa /menu per tornare al menu principale.",
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

# Callback per la selezione della categoria
async def categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione della categoria."""
    query = update.callback_query
    await query.answer()
    
    try:
        categoria = query.data
        context.user_data['categoria'] = categoria
        
        # Crea una tastiera per la selezione del genere
        keyboard = [
            [
                InlineKeyboardButton("Maschile", callback_data="Maschile"),
                InlineKeyboardButton("Femminile", callback_data="Femminile")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🏉 <b>Categoria selezionata:</b> {categoria} 🏉\n\n"
            "Seleziona il genere:\n\n"
            "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        context.user_data['stato_corrente'] = GENERE
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
            # Crea una tastiera per la selezione del tipo di partita
            keyboard = [
                [
                    InlineKeyboardButton("Partita normale", callback_data="normale"),
                    InlineKeyboardButton("Triangolare", callback_data="triangolare")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {genere} 🏉\n\n"
                "<b>Seleziona il tipo di partita:</b>\n\n"
                "• <b>Partita normale:</b> Due squadre\n"
                "• <b>Triangolare:</b> Tre squadre che si affrontano a rotazione\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            context.user_data['stato_corrente'] = TIPO_PARTITA
            return TIPO_PARTITA
        else:
            # Per le altre categorie, procedi direttamente alla selezione della squadra
            context.user_data['tipo_partita'] = 'normale'  # Imposta il tipo di partita come normale per default
            
            # Carica le squadre disponibili
            squadre = get_squadre_list()
            
            # Crea una tastiera con le squadre (2 per riga)
            keyboard = []
            for i in range(0, len(squadre), 2):
                row = [InlineKeyboardButton(squadre[i], callback_data=squadre[i + 1])]
                keyboard.append(row)
                if i + 1 < len(squadre):
                    row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i]))
            
            # Aggiungi un pulsante per inserire manualmente una squadra
            keyboard.append([InlineKeyboardButton("Altra squadra (inserisci manualmente)", callback_data="altra_squadra")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Crea un messaggio per la selezione della squadra
            await query.edit_message_text(
                f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {genere} 🏉\n\n"
                "<b>Seleziona la prima squadra:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
            context.user_data['stato_corrente'] = SQUADRA1
            return SQUADRA1
    except Exception as e:
        logger.error(f"Errore nella selezione del genere: {e}")
        await query.edit_message_text(
            "Si è verificato un errore nella selezione del genere. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per la selezione del tipo di partita
async def tipo_partita_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione del tipo di partita."""
    query = update.callback_query
    await query.answer()
    
    try:
        tipo_partita = query.data
        context.user_data['tipo_partita'] = tipo_partita
        
        # Carica le squadre disponibili
        squadre = get_squadre_list()
        
        # Crea una tastiera con le squadre (2 per riga)
        keyboard = []
        for i in range(0, len(squadre), 2):
            row = [InlineKeyboardButton(squadre[i], callback_data=squadre[i + 1])]
            keyboard.append(row)
            if i + 1 < len(squadre):
                row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i]))
        
        # Aggiungi un pulsante per inserire manualmente una squadra
        keyboard.append([InlineKeyboardButton("Altra squadra (inserisci manualmente)", callback_data="altra_squadra")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Crea un messaggio per la selezione della squadra
        await query.edit_message_text(
            f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
            f"<b>Tipo partita:</b> {tipo_partita}\n\n"
            "<b>Seleziona la prima squadra:</b>\n\n"
            "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        context.user_data['stato_corrente'] = SQUADRA1
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
            squadra = query.data
            
            # Se l'utente ha selezionato "Altra squadra", chiedi di inserire manualmente
            if squadra == "altra_squadra":
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n\n"
                    "<b>Inserisci manualmente il nome della prima squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                return SQUADRA1
            
            # Carica le squadre disponibili per la seconda squadra
            squadre = get_squadre_list()
            
            # Rimuovi la prima squadra dalla lista
            if squadra in squadre:
                squadre.remove(squadra)
            
            # Crea una tastiera con le squadre rimanenti (2 per riga)
            keyboard = []
            for i in range(0, len(squadre), 2):
                row = [InlineKeyboardButton(squadre[i], callback_data=squadre[i])]
                if i + 1 < len(squadre):
                    row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))
                keyboard.append(row)
            
            # Aggiungi un pulsante per inserire manualmente una squadra
            keyboard.append([InlineKeyboardButton("Altra squadra (inserisci manualmente)", callback_data="altra_squadra")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Prima squadra:</b> {squadra}\n\n"
                "<b>Seleziona la seconda squadra:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            squadra = update.message.text
            
            # Carica le squadre disponibili per la seconda squadra
            squadre = get_squadre_list()
            
            # Rimuovi la prima squadra dalla lista
            if squadra in squadre:
                squadre.remove(squadra)
            
            # Crea una tastiera con le squadre rimanenti (2 per riga)
            keyboard = []
            for i in range(0, len(squadre), 2):
                row = [InlineKeyboardButton(squadre[i], callback_data=squadre[i])]
                if i + 1 < len(squadre):
                    row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))
                keyboard.append(row)
            
            # Aggiungi un pulsante per inserire manualmente una squadra
            keyboard.append([InlineKeyboardButton("Altra squadra (inserisci manualmente)", callback_data="altra_squadra")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Prima squadra:</b> {squadra}\n\n"
                "<b>Seleziona la seconda squadra:</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        
        context.user_data['squadra1'] = squadra
        context.user_data['stato_corrente'] = SQUADRA2
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
            squadra = query.data
            # Se l'utente ha selezionato "Altra squadra", chiedi di inserire manualmente
            if squadra == "altra_squadra":
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                    f"<b>Prima squadra:</b> {context.user_data['squadra1']}\n\n"
                    "<b>Inserisci manualmente il nome della seconda squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                return SQUADRA2
            
            # Verifica che la seconda squadra sia diversa dalla prima
            if squadra == context.user_data['squadra1']:
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n\n"
                    "⚠️ La seconda squadra deve essere diversa dalla prima. Seleziona un'altra squadra.\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                return SQUADRA2
            
            # Se è un triangolare, prepara la selezione della terza squadra
            if context.user_data.get('tipo_partita') == 'triangolare':
                # Carica le squadre disponibili per la terza squadra
                squadre = get_squadre_list()
                
                # Rimuovi la prima e la seconda squadra dalla lista
                if context.user_data['squadra1'] in squadre:
                    squadre.remove(context.user_data['squadra1'])
                if squadra in squadre:
                    squadre.remove(squadra)
                
                # Crea una tastiera con le squadre rimanenti (2 per riga)
                keyboard = []
                for i in range(0, len(squadre), 2):
                    row = [InlineKeyboardButton(squadre[i], callback_data=squadre[i])]
                    if i + 1 < len(squadre):
                        row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))
                    keyboard.append(row)
                
                # Aggiungi un pulsante per inserire manualmente una squadra
                keyboard.append([InlineKeyboardButton("Altra squadra (inserisci manualmente)", callback_data="altra_squadra")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                    f"<b>Prima squadra:</b> {context.user_data['squadra1']}\n"
                    f"<b>Seconda squadra:</b> {squadra}\n\n"
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
            squadra = update.message.text
            
            # Verifica che la seconda squadra sia diversa dalla prima
            if squadra == context.user_data['squadra1']:
                await update.message.reply_text(
                    "⚠️ La seconda squadra deve essere diversa dalla prima. Inserisci un'altra squadra."
                )
                return SQUADRA2
            
            # Se è un triangolare, prepara la selezione della terza squadra
            if context.user_data.get('tipo_partita') == 'triangolare':
                # Carica le squadre disponibili per la terza squadra
                squadre = get_squadre_list()
                
                # Rimuovi la prima e la seconda squadra dalla lista
                if context.user_data['squadra1'] in squadre:
                    squadre.remove(context.user_data['squadra1'])
                if squadra in squadre:
                    squadre.remove(squadra)
                
                # Crea una tastiera con le squadre rimanenti (2 per riga)
                keyboard = []
                for i in range(0, len(squadre), 2):
                    row = [InlineKeyboardButton(squadre[i], callback_data=squadre[i])]
                    if i + 1 < len(squadre):
                        row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))
                    keyboard.append(row)
                
                # Aggiungi un pulsante per inserire manualmente una squadra
                keyboard.append([InlineKeyboardButton("Altra squadra (inserisci manualmente)", callback_data="altra_squadra")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                    f"<b>Prima squadra:</b> {context.user_data['squadra1']}\n"
                    f"<b>Seconda squadra:</b> {squadra}\n\n"
                    "<b>Seleziona la terza squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            else:
                # Per le partite normali, chiedi la data
                await update.message.reply_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                    f"<b>Prima squadra:</b> {context.user_data['squadra1']}\n"
                    f"<b>Seconda squadra:</b> {squadra}\n\n"
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
            squadra = query.data
            
            # Se l'utente ha selezionato "Altra squadra", chiedi di inserire manualmente
            if squadra == "altra_squadra":
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                    f"<b>Prima squadra:</b> {context.user_data['squadra1']}\n"
                    f"<b>Seconda squadra:</b> {context.user_data['squadra2']}\n\n"
                    "<b>Inserisci manualmente il nome della terza squadra:</b>\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                return SQUADRA3
            
            # Verifica che la terza squadra sia diversa dalle altre
            if squadra == context.user_data['squadra1'] or squadra == context.user_data['squadra2']:
                await query.edit_message_text(
                    f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n\n"
                    "⚠️ La terza squadra deve essere diversa dalle altre. Seleziona un'altra squadra.\n\n"
                    "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                    parse_mode='HTML'
                )
                return SQUADRA3
            
            
            await query.edit_message_text(
                f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Prima squadra:</b> {context.user_data['squadra1']}\n"
                f"<b>Seconda squadra:</b> {context.user_data['squadra2']}\n"
                f"<b>Terza squadra:</b> {squadra}\n\n"
                "<b>Inserisci la data della partita (formato: GG/MM/AAAA):</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
        else:
            squadra = update.message.text
            
            # Verifica che la terza squadra sia diversa dalle altre
            if squadra == context.user_data['squadra1'] or squadra == context.user_data['squadra2']:
                await update.message.reply_text(
                    "⚠️ La terza squadra deve essere diversa dalle altre. Inserisci un'altra squadra."
                )
                return SQUADRA3
            
            await update.message.reply_text(
                f"🏉 <b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']} 🏉\n"
                f"<b>Prima squadra:</b> {context.user_data['squadra1']}\n"
                f"<b>Seconda squadra:</b> {context.user_data['squadra2']}\n"
                f"<b>Terza squadra:</b> {squadra}\n\n"
                "<b>Inserisci la data della partita (formato: GG/MM/AAAA):</b>\n\n"
                "<i>Puoi annullare in qualsiasi momento con /annulla</i>",
                parse_mode='HTML'
            )
        
        context.user_data['squadra3'] = squadra
        context.user_data['stato_corrente'] = DATA_PARTITA
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
            datetime.strptime(data, '%d/%m/%Y')
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
        except ValueError:
            await update.message.reply_text(
                "⚠️ Il numero di mete deve essere un numero intero non negativo. Inserisci nuovamente il numero di mete."
            )
            return METE1
        
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
        except ValueError:
            await update.message.reply_text(
                "⚠️ Il numero di mete deve essere un numero intero non negativo. Inserisci nuovamente il numero di mete."
            )
            return METE2
        
        context.user_data['mete2'] = mete
        
        # Chiedi il nome dell'arbitro
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
        context.user_data['arbitro'] = arbitro
        
        # Mostra il riepilogo e chiedi conferma
        messaggio = f"🏉 <b>RIEPILOGO PARTITA</b> 🏉\n\n"
        messaggio += f"<b>Categoria:</b> {context.user_data['categoria']} - {context.user_data['genere']}\n"
        messaggio += f"<b>Data:</b> {context.user_data['data_partita']}\n\n"
        messaggio += f"<b>{context.user_data['squadra1']} {context.user_data['punteggio1']} - {context.user_data['punteggio2']} {context.user_data['squadra2']}</b>\n"
        messaggio += f"<b>Mete:</b> {context.user_data['mete1']} - {context.user_data['mete2']}\n"
        messaggio += f"<b>Arbitro:</b> {arbitro}\n\n"
        messaggio += "Confermi l'inserimento di questa partita?"
        
        # Crea i pulsanti per la conferma
        keyboard = [
            [
                InlineKeyboardButton("✅ Conferma", callback_data="conferma"),
                InlineKeyboardButton("❌ Annulla", callback_data="annulla")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        context.user_data['stato_corrente'] = CONFERMA
        return CONFERMA
    except Exception as e:
        logger.error(f"Errore nell'inserimento dell'arbitro: {e}")
        await update.message.reply_text(
            "Si è verificato un errore nell'inserimento dell'arbitro. Riprova con /nuova."
        )
        return ConversationHandler.END

# Callback per la conferma dell'inserimento
async def conferma_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la conferma dell'inserimento della partita."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "conferma":
        # Prepara il nuovo risultato
        nuovo_risultato = {
            "categoria": context.user_data['categoria'],
            "genere": context.user_data['genere'],
            "tipo_partita": context.user_data.get('tipo_partita', 'normale'),
            "data_partita": context.user_data['data_partita'],
            "squadra1": context.user_data['squadra1'],
            "squadra2": context.user_data['squadra2'],
            "arbitro": context.user_data['arbitro'],
            "inserito_da": update.effective_user.full_name,
            "timestamp": datetime.now().isoformat()
        }
        
        # Gestione diversa per partite normali e triangolari
        if context.user_data.get('tipo_partita') == 'triangolare':
            # Aggiungi la terza squadra
            nuovo_risultato["squadra3"] = context.user_data.get('squadra3', '')
            
            # Aggiungi i punteggi e le mete per ogni partita del triangolare
            # Partita 1: squadra1 vs squadra2
            nuovo_risultato["partita1_punteggio1"] = int(context.user_data.get('punteggio1', 0))
            nuovo_risultato["partita1_punteggio2"] = int(context.user_data.get('punteggio2', 0))
            nuovo_risultato["partita1_mete1"] = int(context.user_data.get('mete1', 0))
            nuovo_risultato["partita1_mete2"] = int(context.user_data.get('mete2', 0))
            
            # Partita 2: squadra1 vs squadra3
            nuovo_risultato["partita2_punteggio1"] = int(context.user_data.get('punteggio1_vs_3', 0))
            nuovo_risultato["partita2_punteggio2"] = int(context.user_data.get('punteggio3_vs_1', 0))
            nuovo_risultato["partita2_mete1"] = int(context.user_data.get('mete1_vs_3', 0))
            nuovo_risultato["partita2_mete2"] = int(context.user_data.get('mete3_vs_1', 0))
            
            # Partita 3: squadra2 vs squadra3
            nuovo_risultato["partita3_punteggio1"] = int(context.user_data.get('punteggio2_vs_3', 0))
            nuovo_risultato["partita3_punteggio2"] = int(context.user_data.get('punteggio3_vs_2', 0))
            nuovo_risultato["partita3_mete1"] = int(context.user_data.get('mete2_vs_3', 0))
            nuovo_risultato["partita3_mete2"] = int(context.user_data.get('mete3_vs_2', 0))
            
            # Calcola i totali per ogni squadra
            nuovo_risultato["punteggio1"] = nuovo_risultato["partita1_punteggio1"] + nuovo_risultato["partita2_punteggio1"]
            nuovo_risultato["punteggio2"] = nuovo_risultato["partita1_punteggio2"] + nuovo_risultato["partita3_punteggio1"]
            nuovo_risultato["punteggio3"] = nuovo_risultato["partita2_punteggio2"] + nuovo_risultato["partita3_punteggio2"]
            
            nuovo_risultato["mete1"] = nuovo_risultato["partita1_mete1"] + nuovo_risultato["partita2_mete1"]
            nuovo_risultato["mete2"] = nuovo_risultato["partita1_mete2"] + nuovo_risultato["partita3_mete1"]
            nuovo_risultato["mete3"] = nuovo_risultato["partita2_mete2"] + nuovo_risultato["partita3_mete2"]
        else:
            # Per le partite normali, aggiungi i punteggi e le mete standard
            nuovo_risultato["punteggio1"] = int(context.user_data['punteggio1'])
            nuovo_risultato["punteggio2"] = int(context.user_data['punteggio2'])
            nuovo_risultato["mete1"] = int(context.user_data['mete1'])
            nuovo_risultato["mete2"] = int(context.user_data['mete2'])
        
        # Carica i risultati esistenti
        risultati = carica_risultati()
        
        # Aggiungi il nuovo risultato
        risultati.append(nuovo_risultato)
        
        # Salva i risultati aggiornati
        salva_risultati(risultati)
        
        # Invia il messaggio al canale Telegram
        invio_riuscito, messaggio_errore = await invia_messaggio_canale(context, nuovo_risultato)
        
        messaggio_successo = "✅ <b>Partita registrata con successo!</b>\n\n"
        
        if invio_riuscito:
            messaggio_successo += "✅ Risultato pubblicato anche sul canale Telegram.\n\n"
        else:
            messaggio_successo += f"⚠️ Non è stato possibile pubblicare il risultato sul canale Telegram.\n"
            messaggio_successo += f"<i>Errore: {messaggio_errore}</i>\n\n"
            messaggio_successo += "Verifica che:\n"
            messaggio_successo += "1. L'ID del canale sia configurato correttamente\n"
            messaggio_successo += "2. Il bot sia stato aggiunto come amministratore del canale\n"
            messaggio_successo += "3. Il bot abbia i permessi per inviare messaggi\n\n"
        
        messaggio_successo += "Usa /nuova per inserire un'altra partita o /risultati per vedere le ultime partite."
        
        await query.edit_message_text(
            messaggio_successo,
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text(
            "❌ <b>Inserimento annullato.</b>\n\n"
            "Usa /nuova per iniziare di nuovo.",
            parse_mode='HTML'
        )
    
    # Pulisci i dati utente
    context.user_data.clear()
    
    return ConversationHandler.END

# Callback per l'inserimento del punteggio della terza squadra (triangolare)
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
        
        messaggio += f"{i}. <b>{info_categoria}</b> - {risultato.get('data_partita', 'N/D')}\n"
        messaggio += f"   <b>{risultato['squadra1']}</b> {risultato['punteggio1']} - {risultato['punteggio2']} <b>{risultato['squadra2']}</b>\n"
        messaggio += f"   Mete: {risultato['mete1']} - {risultato['mete2']}\n\n"
    
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
    
    # Aggiungi il gestore per i callback delle query inline
    application.add_handler(CallbackQueryHandler(reaction_callback, pattern=r"^(reaction:|view_reactions:)"))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu_"))
    application.add_handler(CallbackQueryHandler(pubblica_riepilogo_callback, pattern=r"^pubblica_riepilogo$"))
    application.add_handler(CallbackQueryHandler(esporta_excel_riepilogo_callback, pattern=r"^esporta_excel_riepilogo$"))
    application.add_handler(CallbackQueryHandler(esporta_pdf_riepilogo_callback, pattern=r"^esporta_pdf_riepilogo$"))
    application.add_handler(CallbackQueryHandler(approva_utente_callback, pattern=r"^approva_"))
    application.add_handler(CallbackQueryHandler(rifiuta_utente_callback, pattern=r"^rifiuta_"))
    application.add_handler(CallbackQueryHandler(promuovi_utente_callback, pattern=r"^promuovi_"))
    application.add_handler(CallbackQueryHandler(declassa_utente_callback, pattern=r"^declassa_"))
    application.add_handler(CallbackQueryHandler(gestione_utenti_callback, pattern=r"^(mostra_autorizzati|mostra_in_attesa|cerca_utente|rimuovi_)"))
    
    # Aggiungi il gestore per la conversazione di inserimento nuova partita
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("nuova", nuova_partita),
            CallbackQueryHandler(nuova_partita, pattern="^menu_nuova$")
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
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Bot Telegram CRV Rugby attivo!')
    
    def log_message(self, format, *args):
        # Disabilita i log delle richieste HTTP per evitare spam nel log
        return

# Funzione per avviare il server HTTP
def run_http_server():
    # Ottieni la porta da Render o usa 8080 come default
    port = int(os.environ.get('PORT', 8080))
    server_address = ('', port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    logger.info(f"Avvio server HTTP sulla porta {port}...")
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