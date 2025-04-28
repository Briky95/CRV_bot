#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Importa le costanti dal modulo di configurazione
from modules.config import RISULTATI_FILE, UTENTI_FILE, REAZIONI_FILE

# Funzione per caricare le squadre dal file JSON
def carica_squadre():
    try:
        # Carica il file JSON
        if os.path.exists('squadre.json'):
            with open('squadre.json', 'r', encoding='utf-8') as file:
                return json.load(file)
        else:
            # Squadre di default in caso di errore
            default_squadre = [
                "ASD AVALON",
                "BOLZANO RUGBY ASD",
                "ASD C'E' L'ESTE RUGBY",
                "PATAVIUM RUGBY JUNIOR A.S.D.",
                "ASD I MAI SOBRI - BEACH RUGBY",
                "OMBRE ROSSE WLFTM OLD R.PADOVA ASD PD",
                "ASD RUGBY TRENTO",
                "RUGBY ROVIGO DELTA SRL SSD",
                "RUGBY PAESE ASD",
                "RUGBY BASSANO 1976 ASD",
                "RUGBY FELTRE ASD",
                "RUGBY BELLUNO ASD",
                "RUGBY CONEGLIANO ASD",
                "RUGBY CASALE ASD",
                "RUGBY VICENZA ASD",
                "RUGBY MIRANO 1957 ASD",
                "RUGBY VALPOLICELLA ASD",
                "VERONA RUGBY ASD"
            ]
            # Salva le squadre di default nel file JSON
            with open('squadre.json', 'w', encoding='utf-8') as file:
                json.dump(default_squadre, file, indent=2, ensure_ascii=False)
            return default_squadre
    except Exception as e:
        logger.error(f"Errore nel caricamento del file JSON: {e}")
        # Squadre di default in caso di errore
        return [
            "ASD AVALON",
            "BOLZANO RUGBY ASD",
            "ASD C'E' L'ESTE RUGBY",
            "PATAVIUM RUGBY JUNIOR A.S.D.",
            "ASD I MAI SOBRI - BEACH RUGBY",
            "OMBRE ROSSE WLFTM OLD R.PADOVA ASD PD",
            "ASD RUGBY TRENTO",
            "RUGBY ROVIGO DELTA SRL SSD",
            "RUGBY PAESE ASD",
            "RUGBY BASSANO 1976 ASD",
            "RUGBY FELTRE ASD",
            "RUGBY BELLUNO ASD",
            "RUGBY CONEGLIANO ASD",
            "RUGBY CASALE ASD",
            "RUGBY VICENZA ASD",
            "RUGBY MIRANO 1957 ASD",
            "RUGBY VALPOLICELLA ASD",
            "VERONA RUGBY ASD"
        ]

# Funzione per salvare le squadre
def salva_squadre(squadre):
    """Salva le squadre nel file JSON."""
    try:
        with open('squadre.json', 'w', encoding='utf-8') as file:
            json.dump(squadre, file, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvare le squadre: {e}")
        return False

# Funzione per caricare le reazioni
def carica_reazioni():
    """Carica le reazioni dal file JSON."""
    if os.path.exists(REAZIONI_FILE):
        try:
            with open(REAZIONI_FILE, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            logger.error(f"Errore nel caricamento delle reazioni: {e}")
    return {}

# Funzione per salvare le reazioni
def salva_reazioni(reazioni):
    """Salva le reazioni nel file JSON."""
    try:
        with open(REAZIONI_FILE, 'w', encoding='utf-8') as file:
            json.dump(reazioni, file, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvare le reazioni: {e}")
        return False

# Funzione per caricare i risultati esistenti
def carica_risultati():
    if os.path.exists(RISULTATI_FILE):
        with open(RISULTATI_FILE, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                logger.error("Errore nel parsing del file JSON")
                return []
    return []

# Funzione per salvare i risultati
def salva_risultati(risultati):
    with open(RISULTATI_FILE, 'w', encoding='utf-8') as file:
        json.dump(risultati, file, indent=2, ensure_ascii=False)

# Funzione per caricare gli utenti autorizzati
def carica_utenti():
    if os.path.exists(UTENTI_FILE):
        with open(UTENTI_FILE, 'r', encoding='utf-8') as file:
            try:
                data = json.load(file)
                
                # Verifica se il file ha il nuovo formato (con dettagli utente)
                if isinstance(data, dict) and "autorizzati" in data and "in_attesa" in data:
                    # Verifica se gli utenti autorizzati sono nel nuovo formato (dizionari invece di ID)
                    if data["autorizzati"] and not isinstance(data["autorizzati"][0], dict):
                        # Converti al nuovo formato
                        data["autorizzati"] = [{"id": uid, "nome": "Utente", "username": None, "data_registrazione": None} for uid in data["autorizzati"]]
                    
                    # Verifica se gli utenti in attesa sono nel nuovo formato
                    if data["in_attesa"] and not isinstance(data["in_attesa"][0], dict):
                        # Converti al nuovo formato
                        data["in_attesa"] = [{"id": uid, "nome": "Utente", "username": None, "data_registrazione": None} for uid in data["in_attesa"]]
                    
                    return data
                else:
                    # Formato vecchio o non valido
                    logger.error("Formato file utenti non valido")
                    return {"autorizzati": [], "in_attesa": []}
            except json.JSONDecodeError:
                logger.error("Errore nel parsing del file degli utenti")
                return {"autorizzati": [], "in_attesa": []}
    return {"autorizzati": [], "in_attesa": []}

# Funzione per salvare gli utenti autorizzati
def salva_utenti(utenti):
    with open(UTENTI_FILE, 'w', encoding='utf-8') as file:
        json.dump(utenti, file, indent=2, ensure_ascii=False)

# Funzione per ottenere i risultati del weekend
def ottieni_risultati_weekend():
    risultati = carica_risultati()
    
    # Ottieni la data di oggi
    oggi = datetime.now().date()
    
    # Calcola l'inizio del weekend (venerdì)
    giorni_da_venerdi = (oggi.weekday() - 4) % 7
    inizio_weekend = oggi - timedelta(days=giorni_da_venerdi)
    
    # Filtra i risultati del weekend
    risultati_weekend = []
    for risultato in risultati:
        try:
            data_partita = datetime.strptime(risultato['data_partita'], '%d/%m/%Y').date()
            if data_partita >= inizio_weekend and data_partita <= oggi:
                risultati_weekend.append(risultato)
        except (ValueError, KeyError):
            # Ignora risultati con date non valide
            pass
    
    return risultati_weekend

# Funzione per verificare la congruenza tra punteggio e mete
def verifica_congruenza_punteggio_mete(punteggio, mete):
    """
    Verifica che il punteggio sia congruente con il numero di mete.
    
    Regole:
    - Una meta vale 5 punti
    - Una trasformazione (dopo meta) vale 2 punti
    - Un calcio di punizione vale 3 punti
    - Un drop vale 3 punti
    
    Quindi il punteggio minimo per n mete è 5*n, e il massimo è 7*n + altri punti.
    Consideriamo ragionevole un massimo di 5 calci/drop (15 punti) oltre alle mete.
    """
    # Punteggio minimo: 5 punti per meta
    punteggio_minimo = mete * 5
    
    # Punteggio massimo: 7 punti per meta (meta + trasformazione) + 15 punti (5 calci/drop)
    punteggio_massimo = mete * 7 + 15
    
    # Se non ci sono mete, il punteggio deve essere divisibile per 3 (calci/drop)
    if mete == 0 and punteggio % 3 != 0:
        return False, f"Con 0 mete, il punteggio dovrebbe essere divisibile per 3 (calci/drop da 3 punti)"
    
    # Verifica che il punteggio sia nell'intervallo ragionevole
    if punteggio < punteggio_minimo:
        return False, f"Il punteggio ({punteggio}) è troppo basso per {mete} mete (minimo {punteggio_minimo})"
    
    if punteggio > punteggio_massimo:
        return False, f"Il punteggio ({punteggio}) sembra troppo alto per {mete} mete (massimo ragionevole {punteggio_massimo})"
    
    return True, "Punteggio congruente con le mete"