#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Token del bot Telegram
TOKEN = "8108188221:AAEBSfi29p63lPbIxDooDuu9VB0iMWeYJzo"

# ID del canale Telegram dove inviare gli aggiornamenti
CHANNEL_ID = "@CRV_Rugby_Risultati_Partite"

# Non utilizziamo un canale di test separato
TEST_CHANNEL_ID = CHANNEL_ID

# ID degli amministratori del bot (possono approvare altri utenti)
ADMIN_IDS = [30658851]  # Sostituisci con il tuo ID Telegram

# Percorsi dei file
RISULTATI_FILE = "risultati.json"
UTENTI_FILE = "utenti.json"
REAZIONI_FILE = "reazioni.json"

# Categorie per i tornei
CATEGORIE = [
    "Seniores",
    "Under 18",
    "Under 16",
    "Under 14",
    "Under 12",
    "Under 10",
    "Under 8",
    "Under 6",
    "Seven",
    "Touch",
    "Beach",
    "Altro"
]