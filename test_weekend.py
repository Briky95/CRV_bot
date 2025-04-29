#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from modules.data_manager import ottieni_risultati_weekend
from modules.db_manager import carica_risultati

def test_weekend_matches():
    # Ottieni la data di oggi
    oggi = datetime.now().date()
    
    # Trova il venerdì precedente (inizio weekend)
    inizio_weekend = oggi - timedelta(days=(oggi.weekday() + 3) % 7)
    
    # Trova la domenica successiva (fine weekend)
    fine_weekend = inizio_weekend + timedelta(days=2)
    
    print(f"Oggi: {oggi}, Weekday: {oggi.weekday()}")
    print(f"Inizio weekend: {inizio_weekend}, Fine weekend: {fine_weekend}")
    
    # Ottieni i risultati del weekend
    risultati_weekend = ottieni_risultati_weekend()
    
    print(f"Numero di partite trovate per il weekend: {len(risultati_weekend)}")
    
    # Mostra tutte le partite
    print("\nTutte le partite:")
    risultati = carica_risultati()
    for i, risultato in enumerate(risultati):
        data_str = risultato.get('data_partita')
        if not data_str:
            print(f"{i+1}. {risultato.get('squadra1', 'N/D')} vs {risultato.get('squadra2', 'N/D')} - Data: Mancante")
            continue
            
        try:
            data_partita = datetime.strptime(data_str, '%d/%m/%Y').date()
            in_weekend = data_partita >= inizio_weekend and data_partita <= fine_weekend
            print(f"{i+1}. {risultato.get('squadra1', 'N/D')} vs {risultato.get('squadra2', 'N/D')} - Data: {data_str} - Nel weekend: {'Sì' if in_weekend else 'No'}")
        except ValueError:
            print(f"{i+1}. {risultato.get('squadra1', 'N/D')} vs {risultato.get('squadra2', 'N/D')} - Data: {data_str} - Formato data non valido")
    
    # Mostra le partite del weekend
    print("\nPartite del weekend:")
    for i, risultato in enumerate(risultati_weekend):
        print(f"{i+1}. {risultato.get('squadra1', 'N/D')} vs {risultato.get('squadra2', 'N/D')} - Data: {risultato.get('data_partita', 'N/D')}")

if __name__ == "__main__":
    test_weekend_matches()