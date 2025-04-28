#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from modules.data_manager import carica_utenti, salva_utenti

logger = logging.getLogger(__name__)

# Importa le costanti dal modulo di configurazione
from modules.config import ADMIN_IDS

# Funzione per verificare se un utente è autorizzato
def is_utente_autorizzato(user_id):
    utenti = carica_utenti()
    # Verifica se l'utente è un amministratore
    if user_id in ADMIN_IDS:
        return True
    
    # Verifica se l'utente è nella lista degli autorizzati
    for utente in utenti["autorizzati"]:
        if isinstance(utente, dict) and utente.get("id") == user_id:
            return True
        elif not isinstance(utente, dict) and utente == user_id:  # Compatibilità con il vecchio formato
            return True
    
    return False

# Funzione per verificare se un utente è amministratore
def is_admin(user_id):
    # Verifica se l'utente è nella lista degli admin predefiniti
    if user_id in ADMIN_IDS:
        return True
    
    # Verifica se l'utente è un admin nel database
    utenti = carica_utenti()
    for utente in utenti["autorizzati"]:
        if isinstance(utente, dict) and utente.get("id") == user_id and utente.get("ruolo") == "admin":
            return True
    
    return False

# Funzione per aggiungere un utente alla lista di attesa
def aggiungi_utente_in_attesa(user_id, nome, username=None):
    utenti = carica_utenti()
    
    # Verifica se l'utente è già autorizzato
    for utente in utenti["autorizzati"]:
        if isinstance(utente, dict) and utente.get("id") == user_id:
            return False, "Utente già autorizzato"
        elif not isinstance(utente, dict) and utente == user_id:
            return False, "Utente già autorizzato"
    
    # Verifica se l'utente è già in attesa
    for utente in utenti["in_attesa"]:
        if isinstance(utente, dict) and utente.get("id") == user_id:
            return False, "Utente già in attesa di approvazione"
        elif not isinstance(utente, dict) and utente == user_id:
            return False, "Utente già in attesa di approvazione"
    
    # Aggiungi l'utente alla lista di attesa
    utenti["in_attesa"].append({
        "id": user_id,
        "nome": nome,
        "username": username,
        "data_registrazione": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    })
    
    salva_utenti(utenti)
    return True, "Utente aggiunto alla lista di attesa"

# Funzione per approvare un utente
def approva_utente(user_id):
    utenti = carica_utenti()
    
    # Cerca l'utente nella lista di attesa
    for i, utente in enumerate(utenti["in_attesa"]):
        if isinstance(utente, dict) and utente.get("id") == user_id:
            # Rimuovi l'utente dalla lista di attesa
            utente_da_approvare = utenti["in_attesa"].pop(i)
            # Aggiungi l'utente alla lista degli autorizzati
            utenti["autorizzati"].append(utente_da_approvare)
            salva_utenti(utenti)
            return True, "Utente approvato con successo"
        elif not isinstance(utente, dict) and utente == user_id:
            # Compatibilità con il vecchio formato
            utente_da_approvare = utenti["in_attesa"].pop(i)
            utenti["autorizzati"].append({"id": user_id, "nome": "Utente", "username": None, "data_registrazione": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
            salva_utenti(utenti)
            return True, "Utente approvato con successo"
    
    return False, "Utente non trovato nella lista di attesa"

# Funzione per rifiutare un utente
def rifiuta_utente(user_id):
    utenti = carica_utenti()
    
    # Cerca l'utente nella lista di attesa
    for i, utente in enumerate(utenti["in_attesa"]):
        if isinstance(utente, dict) and utente.get("id") == user_id:
            # Rimuovi l'utente dalla lista di attesa
            utenti["in_attesa"].pop(i)
            salva_utenti(utenti)
            return True, "Utente rifiutato con successo"
        elif not isinstance(utente, dict) and utente == user_id:
            # Compatibilità con il vecchio formato
            utenti["in_attesa"].pop(i)
            salva_utenti(utenti)
            return True, "Utente rifiutato con successo"
    
    return False, "Utente non trovato nella lista di attesa"

# Funzione per rimuovere un utente autorizzato
def rimuovi_utente_autorizzato(user_id):
    utenti = carica_utenti()
    
    # Cerca l'utente nella lista degli autorizzati
    for i, utente in enumerate(utenti["autorizzati"]):
        if isinstance(utente, dict) and utente.get("id") == user_id:
            # Rimuovi l'utente dalla lista degli autorizzati
            utenti["autorizzati"].pop(i)
            salva_utenti(utenti)
            return True, "Utente rimosso con successo"
        elif not isinstance(utente, dict) and utente == user_id:
            # Compatibilità con il vecchio formato
            utenti["autorizzati"].pop(i)
            salva_utenti(utenti)
            return True, "Utente rimosso con successo"
    
    return False, "Utente non trovato nella lista degli autorizzati"

# Funzione per promuovere un utente a admin
def promuovi_utente_admin(user_id):
    utenti = carica_utenti()
    
    # Cerca l'utente nella lista degli autorizzati
    for i, utente in enumerate(utenti["autorizzati"]):
        if isinstance(utente, dict) and utente.get("id") == user_id:
            # Verifica se l'utente è già admin
            if utente.get("ruolo") == "admin":
                return False, "L'utente è già amministratore"
            
            # Promuovi l'utente a admin
            utenti["autorizzati"][i]["ruolo"] = "admin"
            salva_utenti(utenti)
            return True, "Utente promosso ad amministratore con successo"
        elif not isinstance(utente, dict) and utente == user_id:
            # Converti il vecchio formato e promuovi a admin
            utenti["autorizzati"][i] = {
                "id": user_id,
                "nome": f"Utente {user_id}",
                "username": None,
                "data_registrazione": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "ruolo": "admin"
            }
            salva_utenti(utenti)
            return True, "Utente promosso ad amministratore con successo"
    
    return False, "Utente non trovato nella lista degli autorizzati"

# Funzione per declassare un utente da admin
def declassa_utente_admin(user_id):
    utenti = carica_utenti()
    
    # Cerca l'utente nella lista degli autorizzati
    for i, utente in enumerate(utenti["autorizzati"]):
        if isinstance(utente, dict) and utente.get("id") == user_id:
            # Verifica se l'utente è admin
            if utente.get("ruolo") != "admin":
                return False, "L'utente non è un amministratore"
            
            # Declassa l'utente a utente normale
            utenti["autorizzati"][i]["ruolo"] = "utente"
            salva_utenti(utenti)
            return True, "Privilegi di amministratore rimossi con successo"
    
    return False, "Utente non trovato nella lista degli autorizzati"