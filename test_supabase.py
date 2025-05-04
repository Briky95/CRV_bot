#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Carica le variabili d'ambiente
load_dotenv()

# Configurazione Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print(f"SUPABASE_URL: {SUPABASE_URL}")
print(f"SUPABASE_KEY: {SUPABASE_KEY[:10]}...{SUPABASE_KEY[-10:]}")

# Inizializza il client Supabase
try:
    import requests
    
    # Classe semplificata per interagire con Supabase tramite API REST
    class SupabaseClient:
        def __init__(self, url, key):
            self.url = url
            self.key = key
            self.headers = {
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
        
        def table(self, table_name):
            return SupabaseTable(self, table_name)
    
    # Classe per operazioni su tabelle Supabase
    class SupabaseTable:
        def __init__(self, client, table_name):
            self.client = client
            self.table_name = table_name
            self.base_url = f"{client.url}/rest/v1/{table_name}"
            self.filters = []
            self.select_columns = "*"
        
        def select(self, columns="*"):
            self.select_columns = columns
            return self
        
        def eq(self, column, value):
            self.filters.append(f"{column}=eq.{value}")
            return self
        
        def execute(self):
            url = f"{self.base_url}?select={self.select_columns}"
            if self.filters:
                url += "&" + "&".join(self.filters)
            
            print(f"Esecuzione richiesta GET: {url}")
            print(f"Headers: {self.client.headers}")
            
            response = requests.get(
                url,
                headers=self.client.headers
            )
            
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            
            class Response:
                def __init__(self, data):
                    self.data = data
            
            if response.status_code == 200:
                return Response(response.json())
            return Response([])
        
        def insert(self, data):
            print(f"Esecuzione richiesta POST: {self.base_url}")
            print(f"Headers: {self.client.headers}")
            print(f"Data: {json.dumps(data, indent=2)}")
            
            response = requests.post(
                self.base_url,
                headers=self.client.headers,
                json=data
            )
            
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            
            class Response:
                def __init__(self, data):
                    self.data = data
            
            if response.status_code in [200, 201]:
                return Response(response.json())
            return Response(None)
    
    # Inizializza il client Supabase
    supabase = SupabaseClient(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
    
    if supabase:
        print("Client Supabase inizializzato correttamente")
        
        # Test di lettura
        print("\n--- Test di lettura ---")
        risultati = supabase.table('risultati').select('*').execute().data
        print(f"Risultati esistenti: {json.dumps(risultati, indent=2)}")
        
        # Test di inserimento
        print("\n--- Test di inserimento ---")
        nuovo_risultato = {
            "id": int(datetime.now().timestamp()),  # ID univoco basato sul timestamp
            "categoria": "Test Script",
            "squadra1": "Squadra Test A",
            "squadra2": "Squadra Test B",
            "punteggio1": 30,
            "punteggio2": 25,
            "mete1": 4,
            "mete2": 3,
            "arbitro": "Test Script",
            "inserito_da": "Test Script",
            "genere": "Test",
            "data_partita": "03/05/2025",
            "data_partita_iso": "2025-05-03T00:00:00"
            # Rimuoviamo il campo timestamp che non esiste nella tabella
        }
        
        response = supabase.table('risultati').insert(nuovo_risultato).execute()
        print(f"Risposta inserimento: {json.dumps(response.data, indent=2) if response.data else 'Nessuna risposta'}")
        
        # Verifica inserimento
        print("\n--- Verifica inserimento ---")
        risultati_aggiornati = supabase.table('risultati').select('*').execute().data
        print(f"Risultati aggiornati: {json.dumps(risultati_aggiornati, indent=2)}")
        
    else:
        print("Errore: Client Supabase non inizializzato")
        
except Exception as e:
    print(f"Errore: {e}")