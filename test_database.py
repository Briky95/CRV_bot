#!/usr/bin/env python
# -*- coding: utf-8 -*-

from modules.db_manager import (
    is_supabase_configured,
    carica_utenti,
    salva_utenti,
    carica_risultati,
    salva_risultati,
    carica_squadre,
    salva_squadre,
    carica_admin_users,
    salva_admin_users
)

def test_database():
    # Verifica la connessione a Supabase
    supabase_ok = is_supabase_configured()
    print(f'Connessione a Supabase: {"OK" if supabase_ok else "ERRORE"}')
    
    # Test delle funzioni di utenti
    print("\n=== Test delle funzioni di utenti ===")
    utenti = carica_utenti()
    print(f'Utenti autorizzati: {len(utenti["autorizzati"])}')
    print(f'Utenti in attesa: {len(utenti["in_attesa"])}')
    
    # Aggiungi un utente di test
    utenti["in_attesa"].append({
        "id": 123456789,
        "nome": "Utente Test",
        "username": "utente_test",
        "ruolo": "utente",
        "stato": "in_attesa"
    })
    
    # Salva gli utenti
    salva_utenti(utenti)
    print("Utente di test aggiunto")
    
    # Verifica che l'utente sia stato aggiunto
    utenti = carica_utenti()
    print(f'Utenti in attesa dopo l\'aggiunta: {len(utenti["in_attesa"])}')
    
    # Rimuovi l'utente di test
    utenti["in_attesa"] = [u for u in utenti["in_attesa"] if u.get("id") != 123456789]
    salva_utenti(utenti)
    print("Utente di test rimosso")
    
    # Verifica che l'utente sia stato rimosso
    utenti = carica_utenti()
    print(f'Utenti in attesa dopo la rimozione: {len(utenti["in_attesa"])}')
    
    # Test delle funzioni di risultati
    print("\n=== Test delle funzioni di risultati ===")
    risultati = carica_risultati()
    print(f'Risultati: {len(risultati)}')
    
    # Aggiungi un risultato di test
    risultati.append({
        "id": 999999,
        "categoria": "Test",
        "squadra1": "Squadra A",
        "squadra2": "Squadra B",
        "punteggio1": 10,
        "punteggio2": 5,
        "mete1": 2,
        "mete2": 1,
        "arbitro": "Arbitro Test",
        "inserito_da": "Utente Test",
        "data_partita": "01/01/2025"
    })
    
    # Salva i risultati
    salva_risultati(risultati)
    print("Risultato di test aggiunto")
    
    # Verifica che il risultato sia stato aggiunto
    risultati = carica_risultati()
    print(f'Risultati dopo l\'aggiunta: {len(risultati)}')
    
    # Rimuovi il risultato di test
    risultati = [r for r in risultati if r.get("id") != 999999]
    salva_risultati(risultati)
    print("Risultato di test rimosso")
    
    # Verifica che il risultato sia stato rimosso
    risultati = carica_risultati()
    print(f'Risultati dopo la rimozione: {len(risultati)}')
    
    # Test delle funzioni di squadre
    print("\n=== Test delle funzioni di squadre ===")
    squadre = carica_squadre()
    print(f'Categorie: {len(squadre)}')
    
    # Aggiungi una categoria di test
    squadre["Test"] = ["Squadra Test A", "Squadra Test B"]
    
    # Salva le squadre
    salva_squadre(squadre)
    print("Categoria di test aggiunta")
    
    # Verifica che la categoria sia stata aggiunta
    squadre = carica_squadre()
    print(f'Categorie dopo l\'aggiunta: {len(squadre)}')
    
    # Rimuovi la categoria di test
    del squadre["Test"]
    salva_squadre(squadre)
    print("Categoria di test rimossa")
    
    # Verifica che la categoria sia stata rimossa
    squadre = carica_squadre()
    print(f'Categorie dopo la rimozione: {len(squadre)}')
    
    # Test delle funzioni di admin
    print("\n=== Test delle funzioni di admin ===")
    admin_users = carica_admin_users()
    print(f'Admin: {len(admin_users)}')
    
    # Aggiungi un admin di test
    admin_users.append({
        "id": 123456789,
        "username": "admin_test",
        "password": "password_test",
        "nome": "Admin Test",
        "ruolo": "admin"
    })
    
    # Salva gli admin
    salva_admin_users(admin_users)
    print("Admin di test aggiunto")
    
    # Verifica che l'admin sia stato aggiunto
    admin_users = carica_admin_users()
    print(f'Admin dopo l\'aggiunta: {len(admin_users)}')
    
    # Rimuovi l'admin di test
    admin_users = [a for a in admin_users if a.get("id") != 123456789]
    salva_admin_users(admin_users)
    print("Admin di test rimosso")
    
    # Verifica che l'admin sia stato rimosso
    admin_users = carica_admin_users()
    print(f'Admin dopo la rimozione: {len(admin_users)}')
    
    print("\nTest del database completato con successo!")

if __name__ == "__main__":
    test_database()