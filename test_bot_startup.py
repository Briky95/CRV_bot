#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Abilita logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Carica le variabili d'ambiente
load_dotenv()

# Token del bot Telegram
TOKEN = os.getenv("BOT_TOKEN")

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un messaggio quando viene eseguito il comando /start."""
    await update.message.reply_text('Bot avviato correttamente! Test completato.')

# Comando /test
async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Esegue un test delle funzionalità di base."""
    await update.message.reply_text('Test delle funzionalità di base in corso...')
    
    # Test della connessione al database
    try:
        from modules.db_manager import is_supabase_configured, carica_utenti, carica_risultati, carica_squadre
        
        # Verifica la connessione a Supabase
        supabase_ok = is_supabase_configured()
        await update.message.reply_text(f'Connessione a Supabase: {"OK" if supabase_ok else "ERRORE"}')
        
        # Carica gli utenti
        utenti = carica_utenti()
        await update.message.reply_text(f'Utenti autorizzati: {len(utenti["autorizzati"])}')
        
        # Carica i risultati
        risultati = carica_risultati()
        await update.message.reply_text(f'Risultati: {len(risultati)}')
        
        # Carica le squadre
        squadre = carica_squadre()
        await update.message.reply_text(f'Categorie: {len(squadre)}')
        
    except Exception as e:
        await update.message.reply_text(f'Errore durante il test del database: {e}')
    
    await update.message.reply_text('Test completato!')

def main() -> None:
    """Avvia il bot."""
    # Crea l'applicazione
    application = Application.builder().token(TOKEN).build()

    # Registra i gestori dei comandi
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test_command))

    # Avvia il bot
    print(f"Bot avviato con token: {TOKEN[:5]}...{TOKEN[-5:]}")
    print("Premi Ctrl+C per terminare")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()