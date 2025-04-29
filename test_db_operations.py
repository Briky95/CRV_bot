#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime
from modules.db_manager import carica_risultati, salva_risultati

def test_db_operations():
    # Carica i risultati esistenti
    risultati = carica_risultati()
    
    print(f"Numero di partite caricate: {len(risultati)}")
    
    # Crea una nuova partita di test
    nuova_partita = {
        'id': len(risultati) + 1,
        'categoria': 'Test',
        'squadra1': 'Squadra Test 1',
        'squadra2': 'Squadra Test 2',
        'punteggio1': 25,
        'punteggio2': 18,
        'mete1': 3,
        'mete2': 2,
        'arbitro': 'Test',
        'inserito_da': 'Test Script',
        'genere': 'Test',
        'data_partita': datetime.now().strftime('%d/%m/%Y'),
        'timestamp_inserimento': datetime.now().isoformat()
    }
    
    # Aggiungi la nuova partita
    risultati.append(nuova_partita)
    
    # Salva i risultati
    salva_risultati(risultati)
    
    print(f"Partita di test aggiunta e salvata.")
    
    # Ricarica i risultati per verificare che la partita sia stata salvata correttamente
    risultati_aggiornati = carica_risultati()
    
    print(f"Numero di partite dopo l'aggiunta: {len(risultati_aggiornati)}")
    
    # Verifica che l'ultima partita sia quella appena aggiunta
    ultima_partita = risultati_aggiornati[-1]
    
    print("\nVerifica della partita aggiunta:")
    print(f"ID: {ultima_partita.get('id')}")
    print(f"Categoria: {ultima_partita.get('categoria')}")
    print(f"Squadre: {ultima_partita.get('squadra1')} vs {ultima_partita.get('squadra2')}")
    print(f"Punteggio: {ultima_partita.get('punteggio1')} - {ultima_partita.get('punteggio2')}")
    print(f"Mete: {ultima_partita.get('mete1')} - {ultima_partita.get('mete2')}")
    print(f"Data: {ultima_partita.get('data_partita')}")
    
    # Verifica che i punteggi e le mete siano numeri interi
    print("\nTipo di dati dei punteggi e delle mete:")
    print(f"punteggio1: {type(ultima_partita.get('punteggio1'))}")
    print(f"punteggio2: {type(ultima_partita.get('punteggio2'))}")
    print(f"mete1: {type(ultima_partita.get('mete1'))}")
    print(f"mete2: {type(ultima_partita.get('mete2'))}")
    
    # Salva una copia dei risultati originali
    risultati_originali = risultati.copy()
    
    # Rimuovi la partita di test
    risultati_aggiornati.pop()
    print(f"Numero di partite prima del salvataggio: {len(risultati_aggiornati)}")
    
    # Salva i risultati
    salva_risultati(risultati_aggiornati)
    
    # Ricarica i risultati per verificare che la partita sia stata rimossa correttamente
    risultati_finali = carica_risultati()
    print(f"Numero di partite dopo il caricamento: {len(risultati_finali)}")
    
    print("\nPartita di test rimossa.")
    print(f"Numero di partite dopo la rimozione: {len(risultati_finali)}")
    
    # Verifica che l'ultima partita non sia quella di test
    if risultati_finali and len(risultati_originali) > 1:
        # Verifica che l'ultima partita sia diversa dalla partita di test
        ultima_partita_originale = risultati_originali[-2]  # La penultima partita originale
        ultima_partita_finale = risultati_finali[-1]  # L'ultima partita dopo la rimozione
        
        print("\nUltima partita originale (prima della partita di test):")
        print(f"ID: {ultima_partita_originale.get('id')}")
        print(f"Categoria: {ultima_partita_originale.get('categoria')}")
        print(f"Squadre: {ultima_partita_originale.get('squadra1')} vs {ultima_partita_originale.get('squadra2')}")
        
        print("\nUltima partita dopo la rimozione:")
        print(f"ID: {ultima_partita_finale.get('id')}")
        print(f"Categoria: {ultima_partita_finale.get('categoria')}")
        print(f"Squadre: {ultima_partita_finale.get('squadra1')} vs {ultima_partita_finale.get('squadra2')}")
        
        # Verifica se le partite sono diverse
        if ultima_partita_originale.get('id') == ultima_partita_finale.get('id'):
            print("\nLa partita di test è stata rimossa correttamente.")
        else:
            print("\nATTENZIONE: La partita di test non è stata rimossa correttamente!")
    else:
        print("Nessuna partita trovata dopo la rimozione o non ci sono abbastanza partite per il confronto.")

if __name__ == "__main__":
    test_db_operations()