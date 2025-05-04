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

print("Script di test per il salvataggio di una partita")
print("=======================================")

# Verifica che Supabase sia configurato
if not is_supabase_configured():
    print("Errore: Supabase non è configurato. Impossibile salvare la partita.")
    exit(1)

# Crea una nuova partita di test
nuovo_risultato = {
    "categoria": "Test Sezione Arbitrale",
    "genere": "Maschile",
    "tipo_partita": "normale",
    "data_partita": "05/05/2025",
    "squadra1": "Squadra Test A",
    "squadra2": "Squadra Test B",
    "punteggio1": 25,
    "punteggio2": 20,
    "mete1": 3,
    "mete2": 2,
    "arbitro": "Arbitro Test",
    "sezione_arbitrale": "Padova",
    "inserito_da": "Script Test",
    "id": int(datetime.now().timestamp())  # Genera un ID univoco basato sul timestamp
}

# Converti la data nel formato ISO
try:
    data = datetime.strptime(nuovo_risultato['data_partita'], '%d/%m/%Y')
    nuovo_risultato["data_partita_iso"] = data.isoformat()
except ValueError:
    nuovo_risultato["data_partita_iso"] = None

print(f"Partita di test creata: {json.dumps(nuovo_risultato, indent=2)}")

# Carica i risultati esistenti
risultati = carica_risultati()
print(f"Caricati {len(risultati)} risultati esistenti.")

# Aggiungi il nuovo risultato
risultati.append(nuovo_risultato)

# Salva i risultati aggiornati
print("Salvataggio della partita in corso...")
success = salva_risultati(risultati)

if success:
    print("Partita salvata con successo!")
else:
    print("Errore durante il salvataggio della partita.")

print("=======================================")

# Verifica che la partita sia stata salvata
print("Verifica del salvataggio...")
from modules.db_manager import supabase
response = supabase.table('risultati').select('*').eq('id', nuovo_risultato['id']).execute()
if response.data:
    print(f"Partita trovata nel database: {json.dumps(response.data, indent=2)}")
else:
    print("Partita non trovata nel database!")