#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# Ottieni il token del bot dal file .env
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def test():
    try:
        bot = Bot(BOT_TOKEN)
        me = await bot.get_me()
        print(f'Bot connesso: {me.first_name}')
        print(f'Username: @{me.username}')
        print(f'ID: {me.id}')
        print(f'Può unirsi a gruppi: {me.can_join_groups}')
        print(f'Può leggere tutti i messaggi: {me.can_read_all_group_messages}')
        print(f'Supporta i comandi inline: {me.supports_inline_queries}')
        return True
    except Exception as e:
        print(f'Errore nella connessione al bot: {e}')
        return False

if __name__ == "__main__":
    success = asyncio.run(test())
    if success:
        print("Test completato con successo!")
    else:
        print("Test fallito!")