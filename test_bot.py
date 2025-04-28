#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Abilita logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token del bot - Usa un token diverso per il test
TOKEN = "YOUR_NEW_TOKEN_HERE"  # Sostituisci con un nuovo token

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Ciao! Sono un bot di test.')

# Comando /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Questo è un bot di test.')

# Funzione principale
def main() -> None:
    # Crea l'applicazione
    application = Application.builder().token(TOKEN).build()

    # Aggiungi i gestori dei comandi
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Avvia il bot
    logger.info("Avvio del bot di test...")
    application.run_polling(allowed_updates=["message"])

if __name__ == "__main__":
    main()