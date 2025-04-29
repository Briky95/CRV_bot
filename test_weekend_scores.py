#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from modules.data_manager import ottieni_risultati_weekend
from modules.db_manager import carica_risultati

def test_weekend_scores():
    # Ottieni i risultati del weekend
    risultati_weekend = ottieni_risultati_weekend()
    
    print(f"Numero di partite trovate per il weekend: {len(risultati_weekend)}")
    
    # Mostra i dettagli delle partite del weekend
    print("\nPartite del weekend con punteggi e mete:")
    for i, risultato in enumerate(risultati_weekend):
        print(f"{i+1}. {risultato.get('squadra1', 'N/D')} vs {risultato.get('squadra2', 'N/D')}")
        print(f"   Data: {risultato.get('data_partita', 'N/D')}")
        print(f"   Punteggio: {risultato.get('punteggio1', 'N/D')} - {risultato.get('punteggio2', 'N/D')}")
        print(f"   Mete: {risultato.get('mete1', 'N/D')} - {risultato.get('mete2', 'N/D')}")
        print(f"   Categoria: {risultato.get('categoria', 'N/D')}")
        print(f"   Genere: {risultato.get('genere', 'N/D')}")
        print()
    
    # Verifica se ci sono partite con punteggi o mete mancanti
    print("\nVerifica partite con punteggi o mete mancanti:")
    for i, risultato in enumerate(risultati_weekend):
        punteggio1 = risultato.get('punteggio1')
        punteggio2 = risultato.get('punteggio2')
        mete1 = risultato.get('mete1')
        mete2 = risultato.get('mete2')
        
        if punteggio1 is None or punteggio2 is None or mete1 is None or mete2 is None:
            print(f"Partita {i+1} ha punteggi o mete mancanti:")
            print(f"   {risultato.get('squadra1', 'N/D')} vs {risultato.get('squadra2', 'N/D')}")
            print(f"   Punteggio: {punteggio1} - {punteggio2}")
            print(f"   Mete: {mete1} - {mete2}")
            print()

if __name__ == "__main__":
    test_weekend_scores()#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from modules.data_manager import ottieni_risultati_weekend
from modules.db_manager import carica_risultati

def test_weekend_scores():
    # Ottieni i risultati del weekend
    risultati_weekend = ottieni_risultati_weekend()
    
    print(f"Numero di partite trovate per il weekend: {len(risultati_weekend)}")
    
    # Mostra i dettagli delle partite del weekend
    print("\nPartite del weekend con punteggi e mete:")
    for i, risultato in enumerate(risultati_weekend):
        print(f"{i+1}. {risultato.get('squadra1', 'N/D')} vs {risultato.get('squadra2', 'N/D')}")
        print(f"   Data: {risultato.get('data_partita', 'N/D')}")
        print(f"   Punteggio: {risultato.get('punteggio1', 'N/D')} - {risultato.get('punteggio2', 'N/D')}")
        print(f"   Mete: {risultato.get('mete1', 'N/D')} - {risultato.get('mete2', 'N/D')}")
        print(f"   Categoria: {risultato.get('categoria', 'N/D')}")
        print(f"   Genere: {risultato.get('genere', 'N/D')}")
        print()
    
    # Verifica se ci sono partite con punteggi o mete mancanti
    print("\nVerifica partite con punteggi o mete mancanti:")
    for i, risultato in enumerate(risultati_weekend):
        punteggio1 = risultato.get('punteggio1')
        punteggio2 = risultato.get('punteggio2')
        mete1 = risultato.get('mete1')
        mete2 = risultato.get('mete2')
        
        if punteggio1 is None or punteggio2 is None or mete1 is None or mete2 is None:
            print(f"Partita {i+1} ha punteggi o mete mancanti:")
            print(f"   {risultato.get('squadra1', 'N/D')} vs {risultato.get('squadra2', 'N/D')}")
            print(f"   Punteggio: {punteggio1} - {punteggio2}")
            print(f"   Mete: {mete1} - {mete2}")
            print()

if __name__ == "__main__":
    test_weekend_scores()