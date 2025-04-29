#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script per eseguire tutti i test di integrazione.
"""

import os
import sys
import subprocess
from datetime import datetime

def esegui_test(nome_script, descrizione):
    """Esegue un test e restituisce True se il test è stato completato con successo."""
    print(f"\n{'=' * 80}")
    print(f"Esecuzione del test: {descrizione}")
    print(f"{'=' * 80}")
    
    # Esegui il test
    risultato = subprocess.run(['python3', nome_script], capture_output=True, text=True)
    
    # Stampa l'output del test
    print(risultato.stdout)
    
    if risultato.stderr:
        print("ERRORI:")
        print(risultato.stderr)
    
    # Verifica se il test è stato completato con successo
    if risultato.returncode == 0:
        print(f"\n✅ Test completato con successo: {descrizione}")
        return True
    else:
        print(f"\n❌ Test fallito: {descrizione}")
        return False

def main():
    """Funzione principale per eseguire tutti i test."""
    print(f"{'=' * 80}")
    print(f"ESECUZIONE DI TUTTI I TEST DI INTEGRAZIONE")
    print(f"Data e ora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'=' * 80}")
    
    # Lista dei test da eseguire
    test_da_eseguire = [
        ('test_db_integration.py', 'Test di integrazione per le funzioni di database'),
        ('test_web_interface.py', 'Test dell\'interfaccia web con il database'),
        ('test_bot_integration.py', 'Test del bot Telegram con il database')
    ]
    
    # Esegui tutti i test
    test_completati = 0
    test_falliti = 0
    
    for nome_script, descrizione in test_da_eseguire:
        if esegui_test(nome_script, descrizione):
            test_completati += 1
        else:
            test_falliti += 1
    
    # Stampa il riepilogo
    print(f"\n{'=' * 80}")
    print(f"RIEPILOGO DEI TEST")
    print(f"{'=' * 80}")
    print(f"Test completati con successo: {test_completati}/{len(test_da_eseguire)}")
    print(f"Test falliti: {test_falliti}/{len(test_da_eseguire)}")
    
    if test_falliti == 0:
        print("\n✅ TUTTI I TEST SONO STATI COMPLETATI CON SUCCESSO!")
        print("Le funzioni di lettura e scrittura delle informazioni sul database funzionano correttamente.")
    else:
        print("\n❌ ALCUNI TEST SONO FALLITI.")
        print("Controlla i log per maggiori dettagli.")
        sys.exit(1)

if __name__ == "__main__":
    main()