#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test di integrazione per verificare che le funzioni di lettura e scrittura
delle informazioni sul database funzionino correttamente sia dal bot che dall'interfaccia web.
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
    return random.randint(1000, 9999)

def genera_nome_casuale(prefisso="Test"):
    """Genera un nome casuale per i test."""
    lettere = ''.join(random.choice(string.ascii_uppercase) for _ in range(5))
    return f"{prefisso}_{lettere}"

def genera_data_casuale():
    """Genera una data casuale nel formato DD/MM/YYYY."""
    oggi = datetime.now()
    giorni_casuali = random.randint(1, 30)
    data_casuale = oggi - timedelta(days=giorni_casuali)
    return data_casuale.strftime("%d/%m/%Y")

def test_risultati():
    """Test per le funzioni di lettura e scrittura dei risultati."""
    print("\n=== Test delle funzioni per i risultati ===")
    
    # Verifica che Supabase sia configurato
    if not is_supabase_configured():
        print("Errore: Supabase non è configurato. Impossibile eseguire il test.")
        return False
    
    # Carica i risultati esistenti
    print("Caricamento dei risultati esistenti...")
    risultati_originali = carica_risultati()
    print(f"Trovati {len(risultati_originali)} risultati esistenti.")
    
    # Crea un nuovo risultato di test
    id_test = genera_id_casuale()
    squadra1 = genera_nome_casuale("SquadraTest1")
    squadra2 = genera_nome_casuale("SquadraTest2")
    data_partita = genera_data_casuale()
    
    nuovo_risultato = {
        'id': id_test,
        'categoria': 'Test',
        'squadra1': squadra1,
        'squadra2': squadra2,
        'punteggio1': random.randint(0, 50),
        'punteggio2': random.randint(0, 50),
        'mete1': random.randint(0, 7),
        'mete2': random.randint(0, 7),
        'arbitro': 'Test',
        'inserito_da': 'Test Script',
        'genere': 'Test',
        'data_partita': data_partita,
        'timestamp_inserimento': datetime.now().isoformat()
    }
    
    print(f"\nCreazione di un nuovo risultato di test:")
    print(f"ID: {id_test}")
    print(f"Partita: {squadra1} vs {squadra2}")
    print(f"Punteggio: {nuovo_risultato['punteggio1']} - {nuovo_risultato['punteggio2']}")
    print(f"Mete: {nuovo_risultato['mete1']} - {nuovo_risultato['mete2']}")
    print(f"Data: {data_partita}")
    
    # Aggiungi il nuovo risultato
    risultati_aggiornati = risultati_originali.copy()
    risultati_aggiornati.append(nuovo_risultato)
    
    # Salva i risultati
    print("\nSalvataggio dei risultati aggiornati...")
    success = salva_risultati(risultati_aggiornati)
    
    if not success:
        print("Errore: Impossibile salvare i risultati.")
        return False
    
    # Ricarica i risultati per verificare che il nuovo risultato sia stato salvato
    print("\nRicaricamento dei risultati per verifica...")
    risultati_verificati = carica_risultati()
    
    # Cerca il risultato di test
    trovato = False
    for risultato in risultati_verificati:
        if risultato.get('id') == id_test:
            trovato = True
            print("\nRisultato di test trovato nel database:")
            print(f"ID: {risultato.get('id')}")
            print(f"Partita: {risultato.get('squadra1')} vs {risultato.get('squadra2')}")
            print(f"Punteggio: {risultato.get('punteggio1')} - {risultato.get('punteggio2')}")
            print(f"Mete: {risultato.get('mete1')} - {risultato.get('mete2')}")
            print(f"Data: {risultato.get('data_partita')}")
            
            # Verifica che i dati siano corretti
            if (risultato.get('squadra1') == squadra1 and
                risultato.get('squadra2') == squadra2 and
                risultato.get('punteggio1') == nuovo_risultato['punteggio1'] and
                risultato.get('punteggio2') == nuovo_risultato['punteggio2'] and
                risultato.get('mete1') == nuovo_risultato['mete1'] and
                risultato.get('mete2') == nuovo_risultato['mete2']):
                print("\nVerifica completata: I dati sono stati salvati correttamente!")
            else:
                print("\nErrore: I dati salvati non corrispondono ai dati originali.")
                return False
            
            break
    
    if not trovato:
        print("\nErrore: Risultato di test non trovato dopo il salvataggio.")
        return False
    
    # Rimuovi il risultato di test
    print("\nRimozione del risultato di test...")
    risultati_finali = [r for r in risultati_verificati if r.get('id') != id_test]
    
    # Salva i risultati senza il risultato di test
    success = salva_risultati(risultati_finali)
    
    if not success:
        print("Errore: Impossibile rimuovere il risultato di test.")
        return False
    
    # Verifica che il risultato di test sia stato rimosso
    risultati_finali_verificati = carica_risultati()
    for risultato in risultati_finali_verificati:
        if risultato.get('id') == id_test:
            print("\nErrore: Il risultato di test non è stato rimosso correttamente.")
            return False
    
    print("\nRisultato di test rimosso correttamente.")
    print("\nTest delle funzioni per i risultati completato con successo!")
    return True

def test_squadre():
    """Test per le funzioni di lettura e scrittura delle squadre."""
    print("\n=== Test delle funzioni per le squadre ===")
    
    # Verifica che Supabase sia configurato
    if not is_supabase_configured():
        print("Errore: Supabase non è configurato. Impossibile eseguire il test.")
        return False
    
    # Carica le squadre esistenti
    print("Caricamento delle squadre esistenti...")
    squadre_originali = carica_squadre()
    num_categorie = len(squadre_originali)
    num_squadre = sum(len(squadre) for squadre in squadre_originali.values())
    print(f"Trovate {num_squadre} squadre in {num_categorie} categorie.")
    
    # Crea una nuova categoria e squadra di test
    categoria_test = "CategoriaTest"
    squadra_test = genera_nome_casuale("SquadraTest")
    
    # Aggiungi la nuova squadra
    squadre_aggiornate = squadre_originali.copy()
    if categoria_test not in squadre_aggiornate:
        squadre_aggiornate[categoria_test] = []
    squadre_aggiornate[categoria_test].append(squadra_test)
    
    print(f"\nCreazione di una nuova squadra di test:")
    print(f"Categoria: {categoria_test}")
    print(f"Squadra: {squadra_test}")
    
    # Salva le squadre
    print("\nSalvataggio delle squadre aggiornate...")
    success = salva_squadre(squadre_aggiornate)
    
    if not success:
        print("Errore: Impossibile salvare le squadre.")
        return False
    
    # Ricarica le squadre per verificare che la nuova squadra sia stata salvata
    print("\nRicaricamento delle squadre per verifica...")
    squadre_verificate = carica_squadre()
    
    # Cerca la squadra di test
    if categoria_test in squadre_verificate and squadra_test in squadre_verificate[categoria_test]:
        print("\nSquadra di test trovata nel database:")
        print(f"Categoria: {categoria_test}")
        print(f"Squadra: {squadra_test}")
        print("\nVerifica completata: I dati sono stati salvati correttamente!")
    else:
        print("\nErrore: Squadra di test non trovata dopo il salvataggio.")
        return False
    
    # Rimuovi la squadra di test
    print("\nRimozione della squadra di test...")
    squadre_finali = squadre_verificate.copy()
    if categoria_test in squadre_finali:
        squadre_finali[categoria_test] = [s for s in squadre_finali[categoria_test] if s != squadra_test]
        if not squadre_finali[categoria_test]:
            del squadre_finali[categoria_test]
    
    # Salva le squadre senza la squadra di test
    success = salva_squadre(squadre_finali)
    
    if not success:
        print("Errore: Impossibile rimuovere la squadra di test.")
        return False
    
    # Verifica che la squadra di test sia stata rimossa
    squadre_finali_verificate = carica_squadre()
    if categoria_test in squadre_finali_verificate and squadra_test in squadre_finali_verificate[categoria_test]:
        print("\nErrore: La squadra di test non è stata rimossa correttamente.")
        return False
    
    print("\nSquadra di test rimossa correttamente.")
    print("\nTest delle funzioni per le squadre completato con successo!")
    return True

def main():
    """Funzione principale per eseguire tutti i test."""
    print("=== Test di integrazione per le funzioni di database ===")
    
    # Verifica che Supabase sia configurato
    if not is_supabase_configured():
        print("Errore: Supabase non è configurato. Impossibile eseguire i test.")
        print("Assicurati che le variabili d'ambiente SUPABASE_URL e SUPABASE_KEY siano impostate.")
        sys.exit(1)
    
    # Esegui il test per i risultati
    risultati_ok = test_risultati()
    
    # Esegui il test per le squadre
    squadre_ok = test_squadre()
    
    # Verifica se tutti i test sono stati completati con successo
    if risultati_ok and squadre_ok:
        print("\n=== Tutti i test sono stati completati con successo! ===")
        print("Le funzioni di lettura e scrittura delle informazioni sul database funzionano correttamente.")
    else:
        print("\n=== Alcuni test non sono stati completati con successo. ===")
        print("Controlla i log per maggiori dettagli.")
        sys.exit(1)

if __name__ == "__main__":
    main()