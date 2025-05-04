#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from modules.quiz_manager import invia_quiz_al_canale, inizializza_quiz

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token del bot Telegram
from dotenv import load_dotenv
load_dotenv()  # Carica le variabili d'ambiente dal file .env

# Usa il token dal file .env o dal file token.txt come fallback
TOKEN = os.getenv("BOT_TOKEN") or "inserisci_il_tuo_token_qui"

# ID del canale di test (può essere l'ID del tuo account per i test)
TEST_CHANNEL_ID = os.getenv("TEST_CHANNEL_ID") or "inserisci_id_canale_test"

# Comando /test_quiz
async def test_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un quiz di test al canale specificato."""
    user_id = update.effective_user.id
    
    # Inizializza i quiz se necessario
    inizializza_quiz()
    
    # Invia un messaggio di attesa
    message = await update.message.reply_text("Invio del quiz in corso...")
    
    # Invia il quiz al canale di test
    success = await invia_quiz_al_canale(context, TEST_CHANNEL_ID)
    
    if success:
        await message.edit_text("✅ Quiz inviato con successo al canale di test!")
    else:
        await message.edit_text("❌ Errore nell'invio del quiz. Controlla i log per maggiori dettagli.")

def main() -> None:
    """Avvia il bot di test."""
    # Crea l'applicazione
    application = Application.builder().token(TOKEN).build()

    # Aggiungi il gestore per il comando di test
    application.add_handler(CommandHandler("test_quiz", test_quiz))

    # Avvia il bot
    logger.info("Avvio del bot di test per i quiz...")
    application.run_polling(allowed_updates=["message"])

if __name__ == "__main__":
    main()