#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test per verificare che il bot Telegram possa leggere e scrivere correttamente sul database.
Questo script simula le operazioni che verrebbero eseguite dal bot Telegram.
"""

import os
import sys
import json
import random
import string
from datetime import datetime, timedelta
from modules.db_manager import (
    is_supabase_configured,
    carica_risultati,
    salva_risultati,
    carica_squadre,
    salva_squadre
)

def genera_id_casuale():
    """Genera un ID casuale per i test."""
    return random.randint(20000, 29999)

def genera_nome_casuale(prefisso="BotTest"):
    """Genera un nome casuale per i test."""
    lettere = ''.join(random.choice(string.ascii_uppercase) for _ in range(5))
    return f"{prefisso}_{lettere}"

def genera_data_casuale():
    """Genera una data casuale nel formato DD/MM/YYYY."""
    oggi = datetime.now()
    giorni_casuali = random.randint(1, 30)
    data_casuale = oggi - timedelta(days=giorni_casuali)
    return data_casuale.strftime("%d/%m/%Y")

def simula_inserimento_risultato_bot():
    """Simula l'inserimento di un risultato tramite il bot Telegram."""
    print("\n=== Simulazione dell'inserimento di un risultato tramite il bot Telegram ===")
    
    # Carica i risultati esistenti
    print("Caricamento dei risultati esistenti...")
    risultati_originali = carica_risultati()
    print(f"Trovati {len(risultati_originali)} risultati esistenti.")
    
    # Crea un nuovo risultato di test
    id_test = genera_id_casuale()
    squadra1 = genera_nome_casuale("BotSquadra1")
    squadra2 = genera_nome_casuale("BotSquadra2")
    data_partita = genera_data_casuale()
    
    # Simula i dati che verrebbero raccolti dal bot durante la conversazione
    bot_data = {
        'categoria': 'Serie B',
        'genere': 'Maschile',
        'data_partita': data_partita,
        'squadra1': squadra1,
        'squadra2': squadra2,
        'punteggio1': random.randint(0, 50),
        'punteggio2': random.randint(0, 50),
        'mete1': random.randint(0, 7),
        'mete2': random.randint(0, 7),
        'arbitro': 'Bot Test'
    }
    
    print(f"\nDati raccolti dal bot:")
    for key, value in bot_data.items():
        print(f"{key}: {value}")
    
    # Simula la logica del bot per salvare il risultato
    nuovo_risultato = {
        'id': id_test,
        'categoria': bot_data['categoria'],
        'genere': bot_data['genere'],
        'data_partita': bot_data['data_partita'],
        'squadra1': bot_data['squadra1'],
        'squadra2': bot_data['squadra2'],
        'punteggio1': int(bot_data['punteggio1']),
        'punteggio2': int(bot_data['punteggio2']),
        'mete1': int(bot_data['mete1']),
        'mete2': int(bot_data['mete2']),
        'arbitro': bot_data['arbitro'],
        'inserito_da': 'Bot Test Script',
        'timestamp_inserimento': datetime.now().isoformat(),
        'message_id': random.randint(1000, 9999)  # Simula un message_id di Telegram
    }
    
    # Aggiungi il nuovo risultato
    risultati_aggiornati = risultati_originali.copy()
    risultati_aggiornati.append(nuovo_risultato)
    
    # Salva i risultati
    print("\nSalvataggio del nuovo risultato...")
    success = salva_risultati(risultati_aggiornati)
    
    if not success:
        print("Errore: Impossibile salvare il nuovo risultato.")
        return False, None
    
    print("Nuovo risultato salvato con successo.")
    return True, nuovo_risultato

def simula_lettura_risultati_bot():
    """Simula la lettura dei risultati tramite il bot Telegram."""
    print("\n=== Simulazione della lettura dei risultati tramite il bot Telegram ===")
    
    # Carica i risultati
    print("Caricamento dei risultati...")
    risultati = carica_risultati()
    print(f"Trovati {len(risultati)} risultati.")
    
    # Simula la logica del bot per ottenere i risultati del weekend
    oggi = datetime.now()
    inizio_weekend = oggi - timedelta(days=(oggi.weekday() + 3) % 7)
    fine_weekend = inizio_weekend + timedelta(days=2)
    
    inizio_weekend_str = inizio_weekend.strftime("%d/%m/%Y")
    fine_weekend_str = fine_weekend.strftime("%d/%m/%Y")
    
    print(f"\nRicerca dei risultati per il weekend {inizio_weekend_str} - {fine_weekend_str}...")
    
    # Filtra i risultati per il weekend
    risultati_weekend = []
    for risultato in risultati:
        if 'data_partita' in risultato and risultato['data_partita']:
            try:
                data_partita = datetime.strptime(risultato['data_partita'], "%d/%m/%Y")
                if inizio_weekend <= data_partita <= fine_weekend:
                    risultati_weekend.append(risultato)
            except ValueError:
                continue
    
    print(f"Trovati {len(risultati_weekend)} risultati per il weekend.")
    
    # Mostra i risultati del weekend
    if risultati_weekend:
        print("\nRisultati del weekend:")
        for i, risultato in enumerate(risultati_weekend):
            print(f"{i+1}. {risultato.get('squadra1', 'N/D')} vs {risultato.get('squadra2', 'N/D')}")
            print(f"   Punteggio: {risultato.get('punteggio1', 'N/D')} - {risultato.get('punteggio2', 'N/D')}")
            print(f"   Mete: {risultato.get('mete1', 'N/D')} - {risultato.get('mete2', 'N/D')}")
            print(f"   Categoria: {risultato.get('categoria', 'N/D')}")
            print(f"   Genere: {risultato.get('genere', 'N/D')}")
            print()
    else:
        print("Nessun risultato trovato per il weekend.")
    
    return True

def simula_eliminazione_risultato_bot(risultato_test):
    """Simula l'eliminazione di un risultato tramite il bot Telegram."""
    print("\n=== Simulazione dell'eliminazione di un risultato tramite il bot Telegram ===")
    
    if not risultato_test:
        print("Errore: Nessun risultato di test da eliminare.")
        return False
    
    # Carica i risultati esistenti
    print("Caricamento dei risultati esistenti...")
    risultati = carica_risultati()
    
    # Simula la logica del bot per eliminare un risultato
    # Rimuovi il risultato di test
    risultati_aggiornati = [r for r in risultati if r.get('id') != risultato_test['id']]
    
    # Verifica che il risultato sia stato rimosso
    if len(risultati_aggiornati) == len(risultati):
        print("Errore: Il risultato di test non è stato trovato.")
        return False
    
    # Salva i risultati aggiornati
    print("\nSalvataggio dei risultati dopo l'eliminazione...")
    success = salva_risultati(risultati_aggiornati)
    
    if not success:
        print("Errore: Impossibile salvare i risultati dopo l'eliminazione.")
        return False
    
    # Verifica che il risultato sia stato eliminato
    risultati_verificati = carica_risultati()
    for risultato in risultati_verificati:
        if risultato.get('id') == risultato_test['id']:
            print("\nErrore: Il risultato di test non è stato eliminato correttamente.")
            return False
    
    print("\nVerifica completata: Il risultato di test è stato eliminato correttamente!")
    return True

def main():
    """Funzione principale per eseguire tutti i test."""
    print("=== Test del bot Telegram con il database ===")
    
    # Verifica che Supabase sia configurato
    if not is_supabase_configured():
        print("Errore: Supabase non è configurato. Impossibile eseguire i test.")
        print("Assicurati che le variabili d'ambiente SUPABASE_URL e SUPABASE_KEY siano impostate.")
        sys.exit(1)
    
    # Simula l'inserimento di un risultato
    success_insert, risultato_test = simula_inserimento_risultato_bot()
    
    if not success_insert:
        print("\nErrore durante la simulazione dell'inserimento di un risultato.")
        sys.exit(1)
    
    # Simula la lettura dei risultati
    success_read = simula_lettura_risultati_bot()
    
    if not success_read:
        print("\nErrore durante la simulazione della lettura dei risultati.")
        # Elimina comunque il risultato di test
        simula_eliminazione_risultato_bot(risultato_test)
        sys.exit(1)
    
    # Simula l'eliminazione di un risultato
    success_delete = simula_eliminazione_risultato_bot(risultato_test)
    
    if not success_delete:
        print("\nErrore durante la simulazione dell'eliminazione di un risultato.")
        sys.exit(1)
    
    print("\n=== Tutti i test del bot Telegram sono stati completati con successo! ===")
    print("Il bot Telegram può leggere e scrivere correttamente sul database.")

if __name__ == "__main__":
    main()