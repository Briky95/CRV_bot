#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script per migrare i dati dal file JSON al database Supabase.
Questo script dovrebbe essere eseguito una sola volta durante la migrazione.
"""

import os
import sys
import json
from datetime import datetime
from modules.db_manager import (
    migra_risultati_da_file_a_db, 
    migra_squadre_da_file_a_db, 
    is_supabase_configured
)

def main():
    print("Iniziando la migrazione dei dati dal file JSON al database Supabase...")
    
    # Verifica che Supabase sia configurato
    if not is_supabase_configured():
        print("Errore: Supabase non è configurato. Impossibile procedere con la migrazione.")
        print("Assicurati che le variabili d'ambiente SUPABASE_URL e SUPABASE_KEY siano impostate.")
        sys.exit(1)
    
    # Migrazione dei risultati
    print("\n=== Migrazione dei risultati ===")
    migra_risultati()
    
    # Migrazione delle squadre
    print("\n=== Migrazione delle squadre ===")
    migra_squadre()
    
    print("\nPromemoria:")
    print("1. Ora i dati vengono salvati solo nel database Supabase.")
    print("2. I file JSON non vengono più utilizzati per salvare o caricare i dati.")
    print("3. Se necessario, puoi ripristinare i file JSON originali rinominando i file di backup.")

def migra_risultati():
    """Migra i risultati dal file JSON al database."""
    # Verifica che il file JSON esista
    risultati_file = os.path.join(os.path.dirname(__file__), 'risultati.json')
    if not os.path.exists(risultati_file):
        print(f"Attenzione: Il file {risultati_file} non esiste. Nessun risultato da migrare.")
        return
    
    # Leggi il file JSON per verificare quanti risultati ci sono
    try:
        with open(risultati_file, 'r', encoding='utf-8') as file:
            risultati = json.load(file)
            print(f"Trovati {len(risultati)} risultati nel file JSON.")
    except Exception as e:
        print(f"Errore nella lettura del file JSON dei risultati: {e}")
        return
    
    # Esegui la migrazione
    print("Migrazione dei risultati in corso...")
    success = migra_risultati_da_file_a_db()
    
    if success:
        print("Migrazione dei risultati completata con successo!")
        
        # Rinomina il file JSON originale per sicurezza
        backup_file = f"{risultati_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            os.rename(risultati_file, backup_file)
            print(f"Il file JSON originale è stato rinominato in {backup_file} per sicurezza.")
        except Exception as e:
            print(f"Attenzione: Impossibile rinominare il file JSON originale: {e}")
            print("Si consiglia di rinominare o eliminare manualmente il file per evitare confusione.")
    else:
        print("Errore durante la migrazione dei risultati. I dati potrebbero non essere stati migrati completamente.")
        print("Controlla i log per maggiori dettagli.")

def migra_squadre():
    """Migra le squadre dal file JSON al database."""
    # Verifica che il file JSON esista
    squadre_file = os.path.join(os.path.dirname(__file__), 'squadre.json')
    if not os.path.exists(squadre_file):
        print(f"Attenzione: Il file {squadre_file} non esiste. Nessuna squadra da migrare.")
        return
    
    # Leggi il file JSON per verificare quante squadre ci sono
    try:
        with open(squadre_file, 'r', encoding='utf-8') as file:
            squadre = json.load(file)
            num_squadre = sum(len(squadre_list) for squadre_list in squadre.values())
            print(f"Trovate {num_squadre} squadre in {len(squadre)} categorie nel file JSON.")
    except Exception as e:
        print(f"Errore nella lettura del file JSON delle squadre: {e}")
        return
    
    # Esegui la migrazione
    print("Migrazione delle squadre in corso...")
    success = migra_squadre_da_file_a_db()
    
    if success:
        print("Migrazione delle squadre completata con successo!")
        
        # Rinomina il file JSON originale per sicurezza
        backup_file = f"{squadre_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            os.rename(squadre_file, backup_file)
            print(f"Il file JSON originale è stato rinominato in {backup_file} per sicurezza.")
        except Exception as e:
            print(f"Attenzione: Impossibile rinominare il file JSON originale: {e}")
            print("Si consiglia di rinominare o eliminare manualmente il file per evitare confusione.")
    else:
        print("Errore durante la migrazione delle squadre. I dati potrebbero non essere stati migrati completamente.")
        print("Controlla i log per maggiori dettagli.")

if __name__ == "__main__":
    main()