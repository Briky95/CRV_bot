#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

# Configurazione del canale
CHANNEL_ID = os.environ.get('CHANNEL_ID', '-1001234567890')  # Sostituisci con l'ID del tuo canale

# Token del bot per l'interfaccia web (diverso dal token del bot principale)
TOKEN_WEB = os.environ.get('BOT_TOKEN_WEB', '')  # Imposta un token diverso per l'interfaccia web

# Se il token web non è impostato, usa un token di fallback (solo per test)
if not TOKEN_WEB:
    # Questo è solo un token di fallback per i test, non utilizzarlo in produzione
    TOKEN_WEB = os.environ.get('BOT_TOKEN', '')