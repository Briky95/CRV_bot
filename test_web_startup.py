#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv
from flask import Flask

# Carica le variabili d'ambiente
load_dotenv()

# Crea l'applicazione Flask
app = Flask(__name__)

@app.route('/')
def home():
    return 'Interfaccia web avviata correttamente! Test completato.'

@app.route('/test')
def test():
    # Test della connessione al database
    try:
        from modules.db_manager import is_supabase_configured, carica_utenti, carica_risultati, carica_squadre
        
        # Verifica la connessione a Supabase
        supabase_ok = is_supabase_configured()
        
        # Carica gli utenti
        utenti = carica_utenti()
        
        # Carica i risultati
        risultati = carica_risultati()
        
        # Carica le squadre
        squadre = carica_squadre()
        
        return f'''
        <h1>Test dell'interfaccia web</h1>
        <p>Connessione a Supabase: {"OK" if supabase_ok else "ERRORE"}</p>
        <p>Utenti autorizzati: {len(utenti["autorizzati"])}</p>
        <p>Risultati: {len(risultati)}</p>
        <p>Categorie: {len(squadre)}</p>
        <p>Test completato!</p>
        '''
    except Exception as e:
        return f'Errore durante il test del database: {e}'

if __name__ == '__main__':
    # Avvia l'applicazione Flask
    print("Interfaccia web avviata")
    app.run(debug=True, port=5000)