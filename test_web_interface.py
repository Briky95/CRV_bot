#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test per verificare che l'interfaccia web possa leggere e scrivere correttamente sul database.
Questo script simula le operazioni che verrebbero eseguite dall'interfaccia web.
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
    return random.randint(10000, 99999)

def genera_nome_casuale(prefisso="WebTest"):
    """Genera un nome casuale per i test."""
    lettere = ''.join(random.choice(string.ascii_uppercase) for _ in range(5))
    return f"{prefisso}_{lettere}"

def genera_data_casuale():
    """Genera una data casuale nel formato DD/MM/YYYY."""
    oggi = datetime.now()
    giorni_casuali = random.randint(1, 30)
    data_casuale = oggi - timedelta(days=giorni_casuali)
    return data_casuale.strftime("%d/%m/%Y")

def simula_aggiunta_partita():
    """Simula l'aggiunta di una partita tramite l'interfaccia web."""
    print("\n=== Simulazione dell'aggiunta di una partita tramite l'interfaccia web ===")
    
    # Carica i risultati esistenti
    print("Caricamento dei risultati esistenti...")
    risultati_originali = carica_risultati()
    print(f"Trovati {len(risultati_originali)} risultati esistenti.")
    
    # Crea un nuovo risultato di test
    id_test = genera_id_casuale()
    squadra1 = genera_nome_casuale("WebSquadra1")
    squadra2 = genera_nome_casuale("WebSquadra2")
    data_partita = genera_data_casuale()
    
    # Simula i dati che verrebbero inviati dal form dell'interfaccia web
    form_data = {
        'categoria': 'Serie A',
        'genere': 'Maschile',
        'data_partita': datetime.strptime(data_partita, "%d/%m/%Y").strftime("%Y-%m-%d"),  # Formato YYYY-MM-DD come nel form
        'squadra1': squadra1,
        'squadra2': squadra2,
        'punteggio1': random.randint(0, 50),
        'punteggio2': random.randint(0, 50),
        'mete1': random.randint(0, 7),
        'mete2': random.randint(0, 7),
        'arbitro': 'Web Test'
    }
    
    print(f"\nDati del form:")
    for key, value in form_data.items():
        print(f"{key}: {value}")
    
    # Simula la logica dell'endpoint /match/add
    # Converti la data nel formato DD/MM/YYYY
    data_partita_formattata = datetime.strptime(form_data['data_partita'], '%Y-%m-%d').strftime('%d/%m/%Y')
    
    # Crea il nuovo risultato
    nuovo_risultato = {
        'id': id_test,
        'categoria': form_data['categoria'],
        'genere': form_data['genere'],
        'data_partita': data_partita_formattata,
        'squadra1': form_data['squadra1'],
        'squadra2': form_data['squadra2'],
        'punteggio1': int(form_data['punteggio1']),
        'punteggio2': int(form_data['punteggio2']),
        'mete1': int(form_data['mete1']),
        'mete2': int(form_data['mete2']),
        'arbitro': form_data['arbitro'],
        'inserito_da': 'Web Test Script',
        'timestamp_inserimento': datetime.now().isoformat()
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

def simula_modifica_partita(risultato_test):
    """Simula la modifica di una partita tramite l'interfaccia web."""
    print("\n=== Simulazione della modifica di una partita tramite l'interfaccia web ===")
    
    if not risultato_test:
        print("Errore: Nessun risultato di test da modificare.")
        return False
    
    # Carica i risultati esistenti
    print("Caricamento dei risultati esistenti...")
    risultati = carica_risultati()
    
    # Trova l'indice del risultato di test
    indice_test = None
    for i, risultato in enumerate(risultati):
        if risultato.get('id') == risultato_test['id']:
            indice_test = i
            break
    
    if indice_test is None:
        print("Errore: Risultato di test non trovato.")
        return False
    
    # Simula i dati che verrebbero inviati dal form di modifica
    form_data = {
        'categoria': risultato_test['categoria'],
        'genere': risultato_test['genere'],
        'data_partita': risultato_test['data_partita'],
        'squadra1': risultato_test['squadra1'],
        'squadra2': risultato_test['squadra2'],
        'punteggio1': risultato_test['punteggio1'] + 5,  # Modifica il punteggio
        'punteggio2': risultato_test['punteggio2'] + 3,  # Modifica il punteggio
        'mete1': risultato_test['mete1'] + 1,  # Modifica le mete
        'mete2': risultato_test['mete2'],
        'arbitro': 'Web Test Modificato'
    }
    
    print(f"\nDati del form di modifica:")
    for key, value in form_data.items():
        print(f"{key}: {value}")
    
    # Simula la logica dell'endpoint /match/edit/<match_id>
    # Aggiorna i dati della partita
    risultati[indice_test]['categoria'] = form_data['categoria']
    risultati[indice_test]['genere'] = form_data['genere']
    risultati[indice_test]['data_partita'] = form_data['data_partita']
    risultati[indice_test]['squadra1'] = form_data['squadra1']
    risultati[indice_test]['squadra2'] = form_data['squadra2']
    risultati[indice_test]['punteggio1'] = int(form_data['punteggio1'])
    risultati[indice_test]['punteggio2'] = int(form_data['punteggio2'])
    risultati[indice_test]['mete1'] = int(form_data['mete1'])
    risultati[indice_test]['mete2'] = int(form_data['mete2'])
    risultati[indice_test]['arbitro'] = form_data['arbitro']
    risultati[indice_test]['modificato_da'] = 'Web Test Script'
    risultati[indice_test]['timestamp_modifica'] = datetime.now().isoformat()
    
    # Salva le modifiche
    print("\nSalvataggio delle modifiche...")
    success = salva_risultati(risultati)
    
    if not success:
        print("Errore: Impossibile salvare le modifiche.")
        return False
    
    # Verifica che le modifiche siano state salvate
    risultati_verificati = carica_risultati()
    for risultato in risultati_verificati:
        if risultato.get('id') == risultato_test['id']:
            if (risultato.get('punteggio1') == form_data['punteggio1'] and
                risultato.get('punteggio2') == form_data['punteggio2'] and
                risultato.get('mete1') == form_data['mete1'] and
                risultato.get('arbitro') == form_data['arbitro']):
                print("\nVerifica completata: Le modifiche sono state salvate correttamente!")
                return True
            else:
                print("\nErrore: Le modifiche non sono state salvate correttamente.")
                return False
    
    print("Errore: Risultato di test non trovato dopo la modifica.")
    return False

def simula_eliminazione_partita(risultato_test):
    """Simula l'eliminazione di una partita tramite l'interfaccia web."""
    print("\n=== Simulazione dell'eliminazione di una partita tramite l'interfaccia web ===")
    
    if not risultato_test:
        print("Errore: Nessun risultato di test da eliminare.")
        return False
    
    # Carica i risultati esistenti
    print("Caricamento dei risultati esistenti...")
    risultati = carica_risultati()
    
    # Simula la logica dell'endpoint /match/delete/<match_id>
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
    print("=== Test dell'interfaccia web con il database ===")
    
    # Verifica che Supabase sia configurato
    if not is_supabase_configured():
        print("Errore: Supabase non è configurato. Impossibile eseguire i test.")
        print("Assicurati che le variabili d'ambiente SUPABASE_URL e SUPABASE_KEY siano impostate.")
        sys.exit(1)
    
    # Simula l'aggiunta di una partita
    success_add, risultato_test = simula_aggiunta_partita()
    
    if not success_add:
        print("\nErrore durante la simulazione dell'aggiunta di una partita.")
        sys.exit(1)
    
    # Simula la modifica di una partita
    success_edit = simula_modifica_partita(risultato_test)
    
    if not success_edit:
        print("\nErrore durante la simulazione della modifica di una partita.")
        # Elimina comunque il risultato di test
        simula_eliminazione_partita(risultato_test)
        sys.exit(1)
    
    # Simula l'eliminazione di una partita
    success_delete = simula_eliminazione_partita(risultato_test)
    
    if not success_delete:
        print("\nErrore durante la simulazione dell'eliminazione di una partita.")
        sys.exit(1)
    
    print("\n=== Tutti i test dell'interfaccia web sono stati completati con successo! ===")
    print("L'interfaccia web può leggere e scrivere correttamente sul database.")

if __name__ == "__main__":
    main()