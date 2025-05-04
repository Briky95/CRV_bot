#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Carica le variabili d'ambiente
load_dotenv()

# Importa le funzioni necessarie
from modules.db_manager import carica_risultati, salva_risultati, is_supabase_configured

print("Script di sincronizzazione dei risultati")
print("=======================================")

# Verifica che Supabase sia configurato
if not is_supabase_configured():
    print("Errore: Supabase non è configurato. Impossibile sincronizzare i risultati.")
    exit(1)

# Carica i risultati dal file JSON locale
risultati = carica_risultati()
print(f"Caricati {len(risultati)} risultati dal file JSON locale.")

# Salva i risultati in Supabase
print("Sincronizzazione dei risultati in corso...")
success = salva_risultati(risultati)

if success:
    print("Sincronizzazione completata con successo!")
else:
    print("Errore durante la sincronizzazione dei risultati.")

print("=======================================")