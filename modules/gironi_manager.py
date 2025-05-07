#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union

# Percorso del file JSON per i gironi
if os.environ.get('AWS_EXECUTION_ENV'):
    # Siamo in AWS Lambda, usa /tmp
    GIRONI_FILE = '/tmp/gironi.json'
    
    # Copia il file dalla directory principale a /tmp se non esiste già
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'gironi.json')
    if os.path.exists(src) and not os.path.exists(GIRONI_FILE):
        try:
            import shutil
            shutil.copy2(src, GIRONI_FILE)
            print(f"File copiato da {src} a {GIRONI_FILE}")
        except Exception as e:
            print(f"Errore nel copiare il file {src} in {GIRONI_FILE}: {e}")
else:
    # Ambiente normale, usa i percorsi standard
    GIRONI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'gironi.json')

# Cache per i dati
_cache = {
    'gironi': None,
    'last_load': 0
}

# Tempo di validità della cache in secondi (5 secondi)
CACHE_TTL = 5

def carica_gironi(force_reload=False) -> Dict[str, Any]:
    """
    Carica i gironi dal database o dal file JSON.
    
    Args:
        force_reload: Se True, forza il ricaricamento anche se la cache è valida
        
    Returns:
        Dizionario con i dati dei gironi
    """
    current_time = time.time()
    
    # Usa la cache se disponibile e non scaduta
    if not force_reload and _cache['gironi'] is not None and (current_time - _cache['last_load']) < CACHE_TTL:
        return _cache['gironi']
    
    # Prova a caricare dal database
    try:
        from modules.db_manager import carica_gironi_da_db, is_supabase_configured
        
        if is_supabase_configured():
            gironi = carica_gironi_da_db()
            if gironi is not None:
                # Aggiorna la cache
                _cache['gironi'] = gironi
                _cache['last_load'] = current_time
                return gironi
    except Exception as e:
        print(f"Errore nel caricamento dei gironi dal database: {e}")
    
    # Fallback al file JSON
    if os.path.exists(GIRONI_FILE):
        with open(GIRONI_FILE, 'r', encoding='utf-8') as file:
            try:
                gironi = json.load(file)
                # Aggiorna la cache
                _cache['gironi'] = gironi
                _cache['last_load'] = current_time
                return gironi
            except json.JSONDecodeError:
                print(f"Errore nel parsing del file dei gironi: {GIRONI_FILE}")
                return {"tornei": []}
    else:
        # Se il file non esiste, crea una struttura vuota
        gironi = {"tornei": []}
        salva_gironi(gironi)
        return gironi

def salva_gironi(gironi: Dict[str, Any]) -> bool:
    """
    Salva i gironi nel database e nel file JSON.
    
    Args:
        gironi: Dizionario con i dati dei gironi
        
    Returns:
        True se il salvataggio è avvenuto con successo, False altrimenti
    """
    # Salva sempre nel file JSON per compatibilità
    try:
        with open(GIRONI_FILE, 'w', encoding='utf-8') as file:
            json.dump(gironi, file, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Errore nel salvataggio dei gironi nel file JSON: {e}")
    
    # Prova a salvare nel database
    try:
        from modules.db_manager import salva_gironi_su_db, is_supabase_configured
        
        if is_supabase_configured():
            db_result = salva_gironi_su_db(gironi)
            if db_result:
                # Aggiorna la cache
                _cache['gironi'] = gironi
                _cache['last_load'] = time.time()
                return True
    except Exception as e:
        print(f"Errore nel salvataggio dei gironi nel database: {e}")
    
    # Aggiorna la cache anche se il salvataggio nel database fallisce
    _cache['gironi'] = gironi
    _cache['last_load'] = time.time()
    return True

def crea_torneo(nome: str, categoria: str, genere: str, data_inizio: str, data_fine: str, descrizione: str = "") -> int:
    """
    Crea un nuovo torneo.
    
    Args:
        nome: Nome del torneo
        categoria: Categoria del torneo (es. "Serie A", "U18", ecc.)
        genere: Genere del torneo (es. "Maschile", "Femminile")
        data_inizio: Data di inizio del torneo (formato "DD/MM/YYYY")
        data_fine: Data di fine del torneo (formato "DD/MM/YYYY")
        descrizione: Descrizione opzionale del torneo
        
    Returns:
        ID del torneo creato
    """
    gironi = carica_gironi()
    
    # Genera un nuovo ID per il torneo
    torneo_id = 1
    if gironi["tornei"]:
        torneo_id = max(torneo["id"] for torneo in gironi["tornei"]) + 1
    
    # Crea il nuovo torneo
    nuovo_torneo = {
        "id": torneo_id,
        "nome": nome,
        "categoria": categoria,
        "genere": genere,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "descrizione": descrizione,
        "data_creazione": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "gironi": []
    }
    
    # Aggiungi il torneo alla lista
    gironi["tornei"].append(nuovo_torneo)
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return torneo_id

def elimina_torneo(torneo_id: int) -> bool:
    """
    Elimina un torneo esistente.
    
    Args:
        torneo_id: ID del torneo da eliminare
        
    Returns:
        True se l'eliminazione è avvenuta con successo, False altrimenti
    """
    gironi = carica_gironi()
    
    # Trova l'indice del torneo da eliminare
    torneo_index = None
    for i, torneo in enumerate(gironi["tornei"]):
        if torneo["id"] == torneo_id:
            torneo_index = i
            break
    
    # Se il torneo non esiste, restituisci False
    if torneo_index is None:
        return False
    
    # Rimuovi il torneo dalla lista
    gironi["tornei"].pop(torneo_index)
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return True

def modifica_torneo(torneo_id: int, nome: str = None, categoria: str = None, genere: str = None, 
                   data_inizio: str = None, data_fine: str = None, descrizione: str = None) -> bool:
    """
    Modifica un torneo esistente.
    
    Args:
        torneo_id: ID del torneo da modificare
        nome: Nuovo nome del torneo (opzionale)
        categoria: Nuova categoria del torneo (opzionale)
        genere: Nuovo genere del torneo (opzionale)
        data_inizio: Nuova data di inizio del torneo (opzionale)
        data_fine: Nuova data di fine del torneo (opzionale)
        descrizione: Nuova descrizione del torneo (opzionale)
        
    Returns:
        True se la modifica è avvenuta con successo, False altrimenti
    """
    gironi = carica_gironi()
    
    # Trova il torneo da modificare
    torneo = None
    for t in gironi["tornei"]:
        if t["id"] == torneo_id:
            torneo = t
            break
    
    # Se il torneo non esiste, restituisci False
    if torneo is None:
        return False
    
    # Modifica i campi specificati
    if nome is not None:
        torneo["nome"] = nome
    if categoria is not None:
        torneo["categoria"] = categoria
    if genere is not None:
        torneo["genere"] = genere
    if data_inizio is not None:
        torneo["data_inizio"] = data_inizio
    if data_fine is not None:
        torneo["data_fine"] = data_fine
    if descrizione is not None:
        torneo["descrizione"] = descrizione
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return True

def crea_girone(torneo_id: int, nome: str, descrizione: str = "") -> int:
    """
    Crea un nuovo girone all'interno di un torneo.
    
    Args:
        torneo_id: ID del torneo a cui aggiungere il girone
        nome: Nome del girone
        descrizione: Descrizione opzionale del girone
        
    Returns:
        ID del girone creato, o -1 se il torneo non esiste
    """
    gironi = carica_gironi()
    
    # Trova il torneo
    torneo = None
    for t in gironi["tornei"]:
        if t["id"] == torneo_id:
            torneo = t
            break
    
    # Se il torneo non esiste, restituisci -1
    if torneo is None:
        return -1
    
    # Genera un nuovo ID per il girone
    girone_id = 1
    if torneo["gironi"]:
        girone_id = max(girone["id"] for girone in torneo["gironi"]) + 1
    
    # Crea il nuovo girone
    nuovo_girone = {
        "id": girone_id,
        "nome": nome,
        "descrizione": descrizione,
        "data_creazione": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "squadre": [],
        "partite": []
    }
    
    # Aggiungi il girone al torneo
    torneo["gironi"].append(nuovo_girone)
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return girone_id

def elimina_girone(torneo_id: int, girone_id: int) -> bool:
    """
    Elimina un girone esistente.
    
    Args:
        torneo_id: ID del torneo che contiene il girone
        girone_id: ID del girone da eliminare
        
    Returns:
        True se l'eliminazione è avvenuta con successo, False altrimenti
    """
    gironi = carica_gironi()
    
    # Trova il torneo
    torneo = None
    for t in gironi["tornei"]:
        if t["id"] == torneo_id:
            torneo = t
            break
    
    # Se il torneo non esiste, restituisci False
    if torneo is None:
        return False
    
    # Trova l'indice del girone da eliminare
    girone_index = None
    for i, girone in enumerate(torneo["gironi"]):
        if girone["id"] == girone_id:
            girone_index = i
            break
    
    # Se il girone non esiste, restituisci False
    if girone_index is None:
        return False
    
    # Rimuovi il girone dalla lista
    torneo["gironi"].pop(girone_index)
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return True

def modifica_girone(torneo_id: int, girone_id: int, nome: str = None, descrizione: str = None) -> bool:
    """
    Modifica un girone esistente.
    
    Args:
        torneo_id: ID del torneo che contiene il girone
        girone_id: ID del girone da modificare
        nome: Nuovo nome del girone (opzionale)
        descrizione: Nuova descrizione del girone (opzionale)
        
    Returns:
        True se la modifica è avvenuta con successo, False altrimenti
    """
    gironi = carica_gironi()
    
    # Trova il torneo
    torneo = None
    for t in gironi["tornei"]:
        if t["id"] == torneo_id:
            torneo = t
            break
    
    # Se il torneo non esiste, restituisci False
    if torneo is None:
        return False
    
    # Trova il girone da modificare
    girone = None
    for g in torneo["gironi"]:
        if g["id"] == girone_id:
            girone = g
            break
    
    # Se il girone non esiste, restituisci False
    if girone is None:
        return False
    
    # Modifica i campi specificati
    if nome is not None:
        girone["nome"] = nome
    if descrizione is not None:
        girone["descrizione"] = descrizione
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return True

def aggiungi_squadra_a_girone(torneo_id: int, girone_id: int, nome_squadra: str) -> bool:
    """
    Aggiunge una squadra a un girone.
    
    Args:
        torneo_id: ID del torneo che contiene il girone
        girone_id: ID del girone a cui aggiungere la squadra
        nome_squadra: Nome della squadra da aggiungere
        
    Returns:
        True se l'aggiunta è avvenuta con successo, False altrimenti
    """
    gironi = carica_gironi()
    
    # Trova il torneo
    torneo = None
    for t in gironi["tornei"]:
        if t["id"] == torneo_id:
            torneo = t
            break
    
    # Se il torneo non esiste, restituisci False
    if torneo is None:
        return False
    
    # Trova il girone
    girone = None
    for g in torneo["gironi"]:
        if g["id"] == girone_id:
            girone = g
            break
    
    # Se il girone non esiste, restituisci False
    if girone is None:
        return False
    
    # Verifica se la squadra è già presente nel girone
    if nome_squadra in girone["squadre"]:
        return False
    
    # Aggiungi la squadra al girone
    girone["squadre"].append(nome_squadra)
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return True

def rimuovi_squadra_da_girone(torneo_id: int, girone_id: int, nome_squadra: str) -> bool:
    """
    Rimuove una squadra da un girone.
    
    Args:
        torneo_id: ID del torneo che contiene il girone
        girone_id: ID del girone da cui rimuovere la squadra
        nome_squadra: Nome della squadra da rimuovere
        
    Returns:
        True se la rimozione è avvenuta con successo, False altrimenti
    """
    gironi = carica_gironi()
    
    # Trova il torneo
    torneo = None
    for t in gironi["tornei"]:
        if t["id"] == torneo_id:
            torneo = t
            break
    
    # Se il torneo non esiste, restituisci False
    if torneo is None:
        return False
    
    # Trova il girone
    girone = None
    for g in torneo["gironi"]:
        if g["id"] == girone_id:
            girone = g
            break
    
    # Se il girone non esiste, restituisci False
    if girone is None:
        return False
    
    # Verifica se la squadra è presente nel girone
    if nome_squadra not in girone["squadre"]:
        return False
    
    # Rimuovi la squadra dal girone
    girone["squadre"].remove(nome_squadra)
    
    # Rimuovi anche tutte le partite che coinvolgono questa squadra
    girone["partite"] = [p for p in girone["partite"] if p["squadra1"] != nome_squadra and p["squadra2"] != nome_squadra]
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return True

def aggiungi_partita_a_girone(torneo_id: int, girone_id: int, squadra1: str, squadra2: str, 
                             data_partita: str, punteggio1: int = None, punteggio2: int = None,
                             mete1: int = None, mete2: int = None, arbitro: str = None,
                             sezione_arbitrale: str = None, note: str = None) -> int:
    """
    Aggiunge una partita a un girone.
    
    Args:
        torneo_id: ID del torneo che contiene il girone
        girone_id: ID del girone a cui aggiungere la partita
        squadra1: Nome della prima squadra
        squadra2: Nome della seconda squadra
        data_partita: Data della partita (formato "DD/MM/YYYY")
        punteggio1: Punteggio della prima squadra (opzionale)
        punteggio2: Punteggio della seconda squadra (opzionale)
        mete1: Numero di mete della prima squadra (opzionale)
        mete2: Numero di mete della seconda squadra (opzionale)
        arbitro: Nome dell'arbitro (opzionale)
        sezione_arbitrale: Sezione arbitrale (opzionale)
        note: Note sulla partita (opzionale)
        
    Returns:
        ID della partita creata, o -1 se il girone non esiste o le squadre non sono nel girone
    """
    gironi = carica_gironi()
    
    # Trova il torneo
    torneo = None
    for t in gironi["tornei"]:
        if t["id"] == torneo_id:
            torneo = t
            break
    
    # Se il torneo non esiste, restituisci -1
    if torneo is None:
        return -1
    
    # Trova il girone
    girone = None
    for g in torneo["gironi"]:
        if g["id"] == girone_id:
            girone = g
            break
    
    # Se il girone non esiste, restituisci -1
    if girone is None:
        return -1
    
    # Verifica che entrambe le squadre siano nel girone
    if squadra1 not in girone["squadre"] or squadra2 not in girone["squadre"]:
        return -1
    
    # Genera un nuovo ID per la partita
    partita_id = 1
    if girone["partite"]:
        partita_id = max(partita["id"] for partita in girone["partite"]) + 1
    
    # Crea la nuova partita
    nuova_partita = {
        "id": partita_id,
        "squadra1": squadra1,
        "squadra2": squadra2,
        "data_partita": data_partita,
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }
    
    # Aggiungi i campi opzionali se specificati
    if punteggio1 is not None:
        nuova_partita["punteggio1"] = punteggio1
    if punteggio2 is not None:
        nuova_partita["punteggio2"] = punteggio2
    if mete1 is not None:
        nuova_partita["mete1"] = mete1
    if mete2 is not None:
        nuova_partita["mete2"] = mete2
    if arbitro is not None:
        nuova_partita["arbitro"] = arbitro
    if sezione_arbitrale is not None:
        nuova_partita["sezione_arbitrale"] = sezione_arbitrale
    if note is not None:
        nuova_partita["note"] = note
    
    # Aggiungi la partita al girone
    girone["partite"].append(nuova_partita)
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return partita_id

def modifica_partita_girone(torneo_id: int, girone_id: int, partita_id: int, 
                           punteggio1: int = None, punteggio2: int = None,
                           mete1: int = None, mete2: int = None, 
                           data_partita: str = None, arbitro: str = None,
                           sezione_arbitrale: str = None, note: str = None) -> bool:
    """
    Modifica una partita esistente in un girone.
    
    Args:
        torneo_id: ID del torneo che contiene il girone
        girone_id: ID del girone che contiene la partita
        partita_id: ID della partita da modificare
        punteggio1: Nuovo punteggio della prima squadra (opzionale)
        punteggio2: Nuovo punteggio della seconda squadra (opzionale)
        mete1: Nuovo numero di mete della prima squadra (opzionale)
        mete2: Nuovo numero di mete della seconda squadra (opzionale)
        data_partita: Nuova data della partita (opzionale)
        arbitro: Nuovo nome dell'arbitro (opzionale)
        sezione_arbitrale: Nuova sezione arbitrale (opzionale)
        note: Nuove note sulla partita (opzionale)
        
    Returns:
        True se la modifica è avvenuta con successo, False altrimenti
    """
    gironi = carica_gironi()
    
    # Trova il torneo
    torneo = None
    for t in gironi["tornei"]:
        if t["id"] == torneo_id:
            torneo = t
            break
    
    # Se il torneo non esiste, restituisci False
    if torneo is None:
        return False
    
    # Trova il girone
    girone = None
    for g in torneo["gironi"]:
        if g["id"] == girone_id:
            girone = g
            break
    
    # Se il girone non esiste, restituisci False
    if girone is None:
        return False
    
    # Trova la partita
    partita = None
    for p in girone["partite"]:
        if p["id"] == partita_id:
            partita = p
            break
    
    # Se la partita non esiste, restituisci False
    if partita is None:
        return False
    
    # Modifica i campi specificati
    if punteggio1 is not None:
        partita["punteggio1"] = punteggio1
    if punteggio2 is not None:
        partita["punteggio2"] = punteggio2
    if mete1 is not None:
        partita["mete1"] = mete1
    if mete2 is not None:
        partita["mete2"] = mete2
    if data_partita is not None:
        partita["data_partita"] = data_partita
    if arbitro is not None:
        partita["arbitro"] = arbitro
    if sezione_arbitrale is not None:
        partita["sezione_arbitrale"] = sezione_arbitrale
    if note is not None:
        partita["note"] = note
    
    # Aggiorna il timestamp
    partita["timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return True

def elimina_partita_girone(torneo_id: int, girone_id: int, partita_id: int) -> bool:
    """
    Elimina una partita da un girone.
    
    Args:
        torneo_id: ID del torneo che contiene il girone
        girone_id: ID del girone che contiene la partita
        partita_id: ID della partita da eliminare
        
    Returns:
        True se l'eliminazione è avvenuta con successo, False altrimenti
    """
    gironi = carica_gironi()
    
    # Trova il torneo
    torneo = None
    for t in gironi["tornei"]:
        if t["id"] == torneo_id:
            torneo = t
            break
    
    # Se il torneo non esiste, restituisci False
    if torneo is None:
        return False
    
    # Trova il girone
    girone = None
    for g in torneo["gironi"]:
        if g["id"] == girone_id:
            girone = g
            break
    
    # Se il girone non esiste, restituisci False
    if girone is None:
        return False
    
    # Trova l'indice della partita da eliminare
    partita_index = None
    for i, partita in enumerate(girone["partite"]):
        if partita["id"] == partita_id:
            partita_index = i
            break
    
    # Se la partita non esiste, restituisci False
    if partita_index is None:
        return False
    
    # Rimuovi la partita dalla lista
    girone["partite"].pop(partita_index)
    
    # Salva i gironi
    salva_gironi(gironi)
    
    return True

def calcola_classifica_girone(torneo_id: int, girone_id: int) -> List[Dict[str, Any]]:
    """
    Calcola la classifica di un girone.
    
    Args:
        torneo_id: ID del torneo che contiene il girone
        girone_id: ID del girone di cui calcolare la classifica
        
    Returns:
        Lista di dizionari con le statistiche delle squadre, ordinata per punteggio
    """
    gironi = carica_gironi()
    
    # Trova il torneo
    torneo = None
    for t in gironi["tornei"]:
        if t["id"] == torneo_id:
            torneo = t
            break
    
    # Se il torneo non esiste, restituisci una lista vuota
    if torneo is None:
        return []
    
    # Trova il girone
    girone = None
    for g in torneo["gironi"]:
        if g["id"] == girone_id:
            girone = g
            break
    
    # Se il girone non esiste, restituisci una lista vuota
    if girone is None:
        return []
    
    # Inizializza la classifica
    classifica = {}
    for squadra in girone["squadre"]:
        classifica[squadra] = {
            "squadra": squadra,
            "punti": 0,
            "partite_giocate": 0,
            "vittorie": 0,
            "pareggi": 0,
            "sconfitte": 0,
            "mete_fatte": 0,
            "mete_subite": 0,
            "punti_fatti": 0,
            "punti_subiti": 0,
            "differenza_punti": 0
        }
    
    # Calcola le statistiche per ogni partita
    for partita in girone["partite"]:
        # Salta le partite senza punteggio
        if "punteggio1" not in partita or "punteggio2" not in partita:
            continue
        
        squadra1 = partita["squadra1"]
        squadra2 = partita["squadra2"]
        punteggio1 = partita["punteggio1"]
        punteggio2 = partita["punteggio2"]
        
        # Aggiorna le partite giocate
        classifica[squadra1]["partite_giocate"] += 1
        classifica[squadra2]["partite_giocate"] += 1
        
        # Aggiorna i punti fatti e subiti
        classifica[squadra1]["punti_fatti"] += punteggio1
        classifica[squadra1]["punti_subiti"] += punteggio2
        classifica[squadra2]["punti_fatti"] += punteggio2
        classifica[squadra2]["punti_subiti"] += punteggio1
        
        # Aggiorna le mete fatte e subite se disponibili
        if "mete1" in partita and "mete2" in partita:
            classifica[squadra1]["mete_fatte"] += partita["mete1"]
            classifica[squadra1]["mete_subite"] += partita["mete2"]
            classifica[squadra2]["mete_fatte"] += partita["mete2"]
            classifica[squadra2]["mete_subite"] += partita["mete1"]
        
        # Aggiorna vittorie, pareggi e sconfitte
        if punteggio1 > punteggio2:
            classifica[squadra1]["vittorie"] += 1
            classifica[squadra2]["sconfitte"] += 1
            classifica[squadra1]["punti"] += 4  # 4 punti per la vittoria
            
            # Bonus offensivo: 1 punto extra se la squadra segna 4 o più mete
            if "mete1" in partita and partita["mete1"] >= 4:
                classifica[squadra1]["punti"] += 1
            
            # Bonus difensivo: 1 punto extra se la squadra perde con 7 o meno punti di scarto
            if punteggio2 >= punteggio1 - 7:
                classifica[squadra2]["punti"] += 1
                
        elif punteggio1 < punteggio2:
            classifica[squadra1]["sconfitte"] += 1
            classifica[squadra2]["vittorie"] += 1
            classifica[squadra2]["punti"] += 4  # 4 punti per la vittoria
            
            # Bonus offensivo: 1 punto extra se la squadra segna 4 o più mete
            if "mete2" in partita and partita["mete2"] >= 4:
                classifica[squadra2]["punti"] += 1
            
            # Bonus difensivo: 1 punto extra se la squadra perde con 7 o meno punti di scarto
            if punteggio1 >= punteggio2 - 7:
                classifica[squadra1]["punti"] += 1
                
        else:  # Pareggio
            classifica[squadra1]["pareggi"] += 1
            classifica[squadra2]["pareggi"] += 1
            classifica[squadra1]["punti"] += 2  # 2 punti per il pareggio
            classifica[squadra2]["punti"] += 2  # 2 punti per il pareggio
            
            # Bonus offensivo: 1 punto extra se la squadra segna 4 o più mete
            if "mete1" in partita and partita["mete1"] >= 4:
                classifica[squadra1]["punti"] += 1
            if "mete2" in partita and partita["mete2"] >= 4:
                classifica[squadra2]["punti"] += 1
    
    # Calcola la differenza punti
    for squadra in classifica:
        classifica[squadra]["differenza_punti"] = classifica[squadra]["punti_fatti"] - classifica[squadra]["punti_subiti"]
    
    # Converti il dizionario in una lista e ordina per punti (decrescente) e differenza punti (decrescente)
    classifica_list = list(classifica.values())
    classifica_list.sort(key=lambda x: (x["punti"], x["differenza_punti"], x["mete_fatte"]), reverse=True)
    
    return classifica_list

def ottieni_tornei_attivi() -> List[Dict[str, Any]]:
    """
    Ottiene la lista dei tornei attivi (la cui data di fine è successiva alla data corrente).
    
    Returns:
        Lista di dizionari con i dati dei tornei attivi
    """
    gironi = carica_gironi()
    oggi = datetime.now().strftime("%d/%m/%Y")
    
    tornei_attivi = []
    for torneo in gironi["tornei"]:
        try:
            data_fine = datetime.strptime(torneo["data_fine"], "%d/%m/%Y")
            data_oggi = datetime.strptime(oggi, "%d/%m/%Y")
            
            if data_fine >= data_oggi:
                tornei_attivi.append(torneo)
        except (ValueError, KeyError):
            # Se c'è un errore nella conversione della data, ignora il torneo
            continue
    
    return tornei_attivi

def ottieni_prossime_partite(giorni: int = 7) -> List[Dict[str, Any]]:
    """
    Ottiene la lista delle partite in programma nei prossimi giorni.
    
    Args:
        giorni: Numero di giorni da considerare (default: 7)
        
    Returns:
        Lista di dizionari con i dati delle partite in programma
    """
    gironi = carica_gironi()
    oggi = datetime.now()
    limite = oggi + timedelta(days=giorni)
    
    prossime_partite = []
    for torneo in gironi["tornei"]:
        for girone in torneo["gironi"]:
            for partita in girone["partite"]:
                try:
                    data_partita = datetime.strptime(partita["data_partita"], "%d/%m/%Y")
                    
                    # Verifica se la partita è nei prossimi giorni e non ha ancora un punteggio
                    if oggi <= data_partita <= limite and ("punteggio1" not in partita or "punteggio2" not in partita):
                        # Crea una copia della partita con informazioni aggiuntive
                        partita_info = partita.copy()
                        partita_info["torneo_id"] = torneo["id"]
                        partita_info["torneo_nome"] = torneo["nome"]
                        partita_info["girone_id"] = girone["id"]
                        partita_info["girone_nome"] = girone["nome"]
                        
                        prossime_partite.append(partita_info)
                except (ValueError, KeyError):
                    # Se c'è un errore nella conversione della data, ignora la partita
                    continue
    
    # Ordina le partite per data
    prossime_partite.sort(key=lambda x: datetime.strptime(x["data_partita"], "%d/%m/%Y"))
    
    return prossime_partite

def ottieni_ultimi_risultati(giorni: int = 7) -> List[Dict[str, Any]]:
    """
    Ottiene la lista degli ultimi risultati registrati.
    
    Args:
        giorni: Numero di giorni passati da considerare (default: 7)
        
    Returns:
        Lista di dizionari con i dati delle partite giocate
    """
    gironi = carica_gironi()
    oggi = datetime.now()
    limite = oggi - timedelta(days=giorni)
    
    ultimi_risultati = []
    for torneo in gironi["tornei"]:
        for girone in torneo["gironi"]:
            for partita in girone["partite"]:
                try:
                    # Verifica se la partita ha un punteggio
                    if "punteggio1" in partita and "punteggio2" in partita:
                        data_partita = datetime.strptime(partita["data_partita"], "%d/%m/%Y")
                        
                        # Verifica se la partita è stata giocata negli ultimi giorni
                        if data_partita >= limite:
                            # Crea una copia della partita con informazioni aggiuntive
                            partita_info = partita.copy()
                            partita_info["torneo_id"] = torneo["id"]
                            partita_info["torneo_nome"] = torneo["nome"]
                            partita_info["girone_id"] = girone["id"]
                            partita_info["girone_nome"] = girone["nome"]
                            
                            ultimi_risultati.append(partita_info)
                except (ValueError, KeyError):
                    # Se c'è un errore nella conversione della data, ignora la partita
                    continue
    
    # Ordina le partite per data (più recenti prima)
    ultimi_risultati.sort(key=lambda x: datetime.strptime(x["data_partita"], "%d/%m/%Y"), reverse=True)
    
    return ultimi_risultati