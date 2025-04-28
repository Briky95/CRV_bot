#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot

# Carica le variabili d'ambiente
load_dotenv()

# Token dei bot Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_TOKEN_WEB = os.getenv("BOT_TOKEN_WEB")

# ID del canale Telegram
CHANNEL_ID = "@CRV_Rugby_Risultati_Partite"  # Sostituisci con l'ID del tuo canale

async def test_integration():
    try:
        # Test del bot principale
        bot = Bot(BOT_TOKEN)
        me = await bot.get_me()
        print(f'Bot principale connesso: {me.first_name} (@{me.username})')
        
        # Test del bot web
        bot_web = Bot(BOT_TOKEN_WEB)
        me_web = await bot_web.get_me()
        print(f'Bot web connesso: {me_web.first_name} (@{me_web.username})')
        
        # Test dell'invio di un messaggio al canale
        try:
            message = await bot.send_message(chat_id=CHANNEL_ID, text="Test di integrazione dal bot principale")
            print(f'Messaggio inviato al canale dal bot principale: {message.message_id}')
        except Exception as e:
            print(f'Errore nell\'invio del messaggio al canale dal bot principale: {e}')
        
        # Test dell'invio di un messaggio al canale dal bot web
        try:
            message_web = await bot_web.send_message(chat_id=CHANNEL_ID, text="Test di integrazione dal bot web")
            print(f'Messaggio inviato al canale dal bot web: {message_web.message_id}')
        except Exception as e:
            print(f'Errore nell\'invio del messaggio al canale dal bot web: {e}')
        
        return True
    except Exception as e:
        print(f'Errore durante il test di integrazione: {e}')
        return False

if __name__ == "__main__":
    success = asyncio.run(test_integration())
    if success:
        print("Test di integrazione completato con successo!")
    else:
        print("Test di integrazione fallito!")