#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union, Tuple

# Cache per i dati
_cache = {
    'stagioni': None,
    'campionati': None,
    'arbitri': None,
    'last_load_stagioni': 0,
    'last_load_campionati': 0,
    'last_load_arbitri': 0
}

# Tempo di validità della cache in secondi (5 secondi)
CACHE_TTL = 5

# Funzioni per la gestione delle stagioni sportive
def carica_stagioni(force_reload=False) -> List[Dict[str, Any]]:
    """
    Carica le stagioni sportive dal database.
    
    Args:
        force_reload: Se True, forza il ricaricamento anche se la cache è valida
        
    Returns:
        Lista delle stagioni sportive
    """
    current_time = time.time()
    
    # Usa la cache se disponibile e non scaduta
    if not force_reload and _cache['stagioni'] is not None and (current_time - _cache['last_load_stagioni']) < CACHE_TTL:
        return _cache['stagioni']
    
    # Carica dal database
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('stagioni').select('*').order('data_inizio', desc=True).execute()
            stagioni = response.data
            
            # Aggiorna la cache
            _cache['stagioni'] = stagioni
            _cache['last_load_stagioni'] = current_time
            return stagioni
    except Exception as e:
        print(f"Errore nel caricamento delle stagioni dal database: {e}")
    
    # Se non ci sono dati o si è verificato un errore, restituisci una lista vuota
    return []

def crea_stagione(nome: str, data_inizio: str, data_fine: str, attiva: bool = False) -> Optional[Dict[str, Any]]:
    """
    Crea una nuova stagione sportiva.
    
    Args:
        nome: Nome della stagione (es. "Stagione 2023-2024")
        data_inizio: Data di inizio della stagione (formato "YYYY-MM-DD")
        data_fine: Data di fine della stagione (formato "YYYY-MM-DD")
        attiva: Se True, imposta questa stagione come attiva
        
    Returns:
        Dizionario con i dati della stagione creata, o None in caso di errore
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Se la nuova stagione è attiva, disattiva tutte le altre
            if attiva:
                supabase.table('stagioni').update({'attiva': False}).neq('id', 0).execute()
            
            # Crea la nuova stagione
            stagione_data = {
                'nome': nome,
                'data_inizio': data_inizio,
                'data_fine': data_fine,
                'attiva': attiva
            }
            
            response = supabase.table('stagioni').insert(stagione_data).execute()
            
            if response.data:
                # Invalida la cache
                _cache['stagioni'] = None
                return response.data[0]
    except Exception as e:
        print(f"Errore nella creazione della stagione: {e}")
    
    return None

def aggiorna_stagione(stagione_id: int, nome: str, data_inizio: str, data_fine: str, attiva: bool = False) -> bool:
    """
    Aggiorna una stagione sportiva esistente.
    
    Args:
        stagione_id: ID della stagione da aggiornare
        nome: Nuovo nome della stagione
        data_inizio: Nuova data di inizio (formato "YYYY-MM-DD")
        data_fine: Nuova data di fine (formato "YYYY-MM-DD")
        attiva: Se True, imposta questa stagione come attiva
        
    Returns:
        True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Se la stagione diventa attiva, disattiva tutte le altre
            if attiva:
                supabase.table('stagioni').update({'attiva': False}).neq('id', stagione_id).execute()
            
            # Aggiorna la stagione
            stagione_data = {
                'nome': nome,
                'data_inizio': data_inizio,
                'data_fine': data_fine,
                'attiva': attiva
            }
            
            supabase.table('stagioni').update(stagione_data).eq('id', stagione_id).execute()
            
            # Invalida la cache
            _cache['stagioni'] = None
            return True
    except Exception as e:
        print(f"Errore nell'aggiornamento della stagione: {e}")
    
    return False

def elimina_stagione(stagione_id: int) -> bool:
    """
    Elimina una stagione sportiva.
    
    Args:
        stagione_id: ID della stagione da eliminare
        
    Returns:
        True se l'eliminazione è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Elimina la stagione
            supabase.table('stagioni').delete().eq('id', stagione_id).execute()
            
            # Invalida la cache
            _cache['stagioni'] = None
            return True
    except Exception as e:
        print(f"Errore nell'eliminazione della stagione: {e}")
    
    return False

def get_stagione_attiva() -> Optional[Dict[str, Any]]:
    """
    Ottiene la stagione attiva.
    
    Returns:
        Dizionario con i dati della stagione attiva, o None se non c'è una stagione attiva
    """
    stagioni = carica_stagioni()
    
    for stagione in stagioni:
        if stagione.get('attiva'):
            return stagione
    
    # Se non c'è una stagione attiva ma ci sono stagioni, restituisci la più recente
    if stagioni:
        return stagioni[0]
    
    return None

# Funzioni per la gestione dei campionati
def carica_campionati(stagione_id: Optional[int] = None, force_reload=False) -> List[Dict[str, Any]]:
    """
    Carica i campionati dal database.
    
    Args:
        stagione_id: Se specificato, carica solo i campionati di questa stagione
        force_reload: Se True, forza il ricaricamento anche se la cache è valida
        
    Returns:
        Lista dei campionati
    """
    current_time = time.time()
    
    # Usa la cache se disponibile e non scaduta
    if not force_reload and _cache['campionati'] is not None and (current_time - _cache['last_load_campionati']) < CACHE_TTL:
        campionati = _cache['campionati']
        if stagione_id is not None:
            return [c for c in campionati if c.get('stagione_id') == stagione_id]
        return campionati
    
    # Carica dal database
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            query = supabase.table('campionati').select('*')
            
            if stagione_id is not None:
                query = query.eq('stagione_id', stagione_id)
            
            response = query.execute()
            campionati = response.data
            
            # Aggiorna la cache
            _cache['campionati'] = campionati
            _cache['last_load_campionati'] = current_time
            
            if stagione_id is not None:
                return [c for c in campionati if c.get('stagione_id') == stagione_id]
            return campionati
    except Exception as e:
        print(f"Errore nel caricamento dei campionati dal database: {e}")
    
    # Se non ci sono dati o si è verificato un errore, restituisci una lista vuota
    return []

def get_campionato(campionato_id: int) -> Optional[Dict[str, Any]]:
    """
    Ottiene i dettagli di un campionato.
    
    Args:
        campionato_id: ID del campionato
        
    Returns:
        Dizionario con i dati del campionato, o None se non trovato
    """
    campionati = carica_campionati()
    
    for campionato in campionati:
        if campionato.get('id') == campionato_id:
            return campionato
    
    # Se non trovato nella cache, prova a caricare direttamente dal database
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('campionati').select('*').eq('id', campionato_id).execute()
            
            if response.data:
                return response.data[0]
    except Exception as e:
        print(f"Errore nel caricamento del campionato dal database: {e}")
    
    return None

def crea_campionato(stagione_id: int, nome: str, categoria: str, genere: str, 
                   formato: str, descrizione: str = "") -> Optional[Dict[str, Any]]:
    """
    Crea un nuovo campionato.
    
    Args:
        stagione_id: ID della stagione
        nome: Nome del campionato
        categoria: Categoria del campionato (es. "Seniores", "Under 18")
        genere: Genere del campionato (es. "Maschile", "Femminile")
        formato: Formato del campionato (es. "girone", "eliminazione", "misto")
        descrizione: Descrizione del campionato
        
    Returns:
        Dizionario con i dati del campionato creato, o None in caso di errore
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Crea il nuovo campionato
            campionato_data = {
                'stagione_id': stagione_id,
                'nome': nome,
                'categoria': categoria,
                'genere': genere,
                'formato': formato,
                'descrizione': descrizione
            }
            
            response = supabase.table('campionati').insert(campionato_data).execute()
            
            if response.data:
                # Invalida la cache
                _cache['campionati'] = None
                return response.data[0]
    except Exception as e:
        print(f"Errore nella creazione del campionato: {e}")
    
    return None

def aggiorna_campionato(campionato_id: int, nome: str, categoria: str, genere: str, 
                       formato: str, descrizione: str = "") -> bool:
    """
    Aggiorna un campionato esistente.
    
    Args:
        campionato_id: ID del campionato da aggiornare
        nome: Nuovo nome del campionato
        categoria: Nuova categoria del campionato
        genere: Nuovo genere del campionato
        formato: Nuovo formato del campionato
        descrizione: Nuova descrizione del campionato
        
    Returns:
        True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Aggiorna il campionato
            campionato_data = {
                'nome': nome,
                'categoria': categoria,
                'genere': genere,
                'formato': formato,
                'descrizione': descrizione
            }
            
            supabase.table('campionati').update(campionato_data).eq('id', campionato_id).execute()
            
            # Invalida la cache
            _cache['campionati'] = None
            return True
    except Exception as e:
        print(f"Errore nell'aggiornamento del campionato: {e}")
    
    return False

def elimina_campionato(campionato_id: int) -> bool:
    """
    Elimina un campionato.
    
    Args:
        campionato_id: ID del campionato da eliminare
        
    Returns:
        True se l'eliminazione è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Elimina il campionato
            supabase.table('campionati').delete().eq('id', campionato_id).execute()
            
            # Invalida la cache
            _cache['campionati'] = None
            return True
    except Exception as e:
        print(f"Errore nell'eliminazione del campionato: {e}")
    
    return False

# Funzioni per la gestione delle squadre nei campionati
def carica_squadre_campionato(campionato_id: int) -> List[str]:
    """
    Carica le squadre di un campionato.
    
    Args:
        campionato_id: ID del campionato
        
    Returns:
        Lista dei nomi delle squadre
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('campionato_squadre').select('squadra').eq('campionato_id', campionato_id).execute()
            
            return [item.get('squadra') for item in response.data]
    except Exception as e:
        print(f"Errore nel caricamento delle squadre del campionato: {e}")
    
    return []

def aggiungi_squadra_campionato(campionato_id: int, squadra: str) -> bool:
    """
    Aggiunge una squadra a un campionato.
    
    Args:
        campionato_id: ID del campionato
        squadra: Nome della squadra
        
    Returns:
        True se l'aggiunta è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Verifica se la squadra esiste già nel campionato
            response = supabase.table('campionato_squadre').select('*').eq('campionato_id', campionato_id).eq('squadra', squadra).execute()
            
            if not response.data:
                # Aggiungi la squadra
                supabase.table('campionato_squadre').insert({
                    'campionato_id': campionato_id,
                    'squadra': squadra
                }).execute()
            
            return True
    except Exception as e:
        print(f"Errore nell'aggiunta della squadra al campionato: {e}")
    
    return False

def rimuovi_squadra_campionato(campionato_id: int, squadra: str) -> bool:
    """
    Rimuove una squadra da un campionato.
    
    Args:
        campionato_id: ID del campionato
        squadra: Nome della squadra
        
    Returns:
        True se la rimozione è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Rimuovi la squadra
            supabase.table('campionato_squadre').delete().eq('campionato_id', campionato_id).eq('squadra', squadra).execute()
            
            return True
    except Exception as e:
        print(f"Errore nella rimozione della squadra dal campionato: {e}")
    
    return False

# Funzioni per la gestione degli arbitri
def carica_arbitri(force_reload=False) -> List[Dict[str, Any]]:
    """
    Carica gli arbitri dal database.
    
    Args:
        force_reload: Se True, forza il ricaricamento anche se la cache è valida
        
    Returns:
        Lista degli arbitri
    """
    current_time = time.time()
    
    # Usa la cache se disponibile e non scaduta
    if not force_reload and _cache['arbitri'] is not None and (current_time - _cache['last_load_arbitri']) < CACHE_TTL:
        return _cache['arbitri']
    
    # Carica dal database
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('arbitri').select('*').order('cognome').execute()
            arbitri = response.data
            
            # Aggiorna la cache
            _cache['arbitri'] = arbitri
            _cache['last_load_arbitri'] = current_time
            return arbitri
    except Exception as e:
        print(f"Errore nel caricamento degli arbitri dal database: {e}")
    
    # Se non ci sono dati o si è verificato un errore, restituisci una lista vuota
    return []

def get_arbitro(arbitro_id: int) -> Optional[Dict[str, Any]]:
    """
    Ottiene i dettagli di un arbitro.
    
    Args:
        arbitro_id: ID dell'arbitro
        
    Returns:
        Dizionario con i dati dell'arbitro, o None se non trovato
    """
    arbitri = carica_arbitri()
    
    for arbitro in arbitri:
        if arbitro.get('id') == arbitro_id:
            return arbitro
    
    # Se non trovato nella cache, prova a caricare direttamente dal database
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('arbitri').select('*').eq('id', arbitro_id).execute()
            
            if response.data:
                return response.data[0]
    except Exception as e:
        print(f"Errore nel caricamento dell'arbitro dal database: {e}")
    
    return None

def crea_arbitro(nome: str, cognome: str, email: str = "", telefono: str = "", 
                livello: str = "", attivo: bool = True, note: str = "") -> Optional[Dict[str, Any]]:
    """
    Crea un nuovo arbitro.
    
    Args:
        nome: Nome dell'arbitro
        cognome: Cognome dell'arbitro
        email: Email dell'arbitro
        telefono: Telefono dell'arbitro
        livello: Livello dell'arbitro (es. "regionale", "nazionale", "internazionale")
        attivo: Se True, l'arbitro è attivo
        note: Note sull'arbitro
        
    Returns:
        Dizionario con i dati dell'arbitro creato, o None in caso di errore
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Crea il nuovo arbitro
            arbitro_data = {
                'nome': nome,
                'cognome': cognome,
                'email': email,
                'telefono': telefono,
                'livello': livello,
                'attivo': attivo,
                'note': note
            }
            
            response = supabase.table('arbitri').insert(arbitro_data).execute()
            
            if response.data:
                # Invalida la cache
                _cache['arbitri'] = None
                return response.data[0]
    except Exception as e:
        print(f"Errore nella creazione dell'arbitro: {e}")
    
    return None

def aggiorna_arbitro(arbitro_id: int, nome: str, cognome: str, email: str = "", telefono: str = "", 
                    livello: str = "", attivo: bool = True, note: str = "") -> bool:
    """
    Aggiorna un arbitro esistente.
    
    Args:
        arbitro_id: ID dell'arbitro da aggiornare
        nome: Nuovo nome dell'arbitro
        cognome: Nuovo cognome dell'arbitro
        email: Nuova email dell'arbitro
        telefono: Nuovo telefono dell'arbitro
        livello: Nuovo livello dell'arbitro
        attivo: Se True, l'arbitro è attivo
        note: Nuove note sull'arbitro
        
    Returns:
        True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Aggiorna l'arbitro
            arbitro_data = {
                'nome': nome,
                'cognome': cognome,
                'email': email,
                'telefono': telefono,
                'livello': livello,
                'attivo': attivo,
                'note': note
            }
            
            supabase.table('arbitri').update(arbitro_data).eq('id', arbitro_id).execute()
            
            # Invalida la cache
            _cache['arbitri'] = None
            return True
    except Exception as e:
        print(f"Errore nell'aggiornamento dell'arbitro: {e}")
    
    return False

def elimina_arbitro(arbitro_id: int) -> bool:
    """
    Elimina un arbitro.
    
    Args:
        arbitro_id: ID dell'arbitro da eliminare
        
    Returns:
        True se l'eliminazione è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Elimina l'arbitro
            supabase.table('arbitri').delete().eq('id', arbitro_id).execute()
            
            # Invalida la cache
            _cache['arbitri'] = None
            return True
    except Exception as e:
        print(f"Errore nell'eliminazione dell'arbitro: {e}")
    
    return False

# Funzioni per la gestione delle partite dei campionati
def carica_partite_campionato(campionato_id: int) -> List[Dict[str, Any]]:
    """
    Carica le partite di un campionato.
    
    Args:
        campionato_id: ID del campionato
        
    Returns:
        Lista delle partite
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('partite_campionato').select('*').eq('campionato_id', campionato_id).order('data_partita').execute()
            
            return response.data
    except Exception as e:
        print(f"Errore nel caricamento delle partite del campionato: {e}")
    
    return []

def get_partita(partita_id: int) -> Optional[Dict[str, Any]]:
    """
    Ottiene i dettagli di una partita.
    
    Args:
        partita_id: ID della partita
        
    Returns:
        Dizionario con i dati della partita, o None se non trovata
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('partite_campionato').select('*').eq('id', partita_id).execute()
            
            if response.data:
                return response.data[0]
    except Exception as e:
        print(f"Errore nel caricamento della partita dal database: {e}")
    
    return None

def crea_partita(campionato_id: int, data_partita: str, squadra_casa: str, squadra_trasferta: str, 
                giornata: Optional[int] = None, ora: Optional[str] = None, luogo: str = "", 
                note: str = "", stato: str = "programmata") -> Optional[Dict[str, Any]]:
    """
    Crea una nuova partita.
    
    Args:
        campionato_id: ID del campionato
        data_partita: Data della partita (formato "YYYY-MM-DD")
        squadra_casa: Nome della squadra di casa
        squadra_trasferta: Nome della squadra in trasferta
        giornata: Numero della giornata
        ora: Ora della partita (formato "HH:MM")
        luogo: Luogo della partita
        note: Note sulla partita
        stato: Stato della partita (es. "programmata", "in_corso", "completata")
        
    Returns:
        Dizionario con i dati della partita creata, o None in caso di errore
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Crea la nuova partita
            partita_data = {
                'campionato_id': campionato_id,
                'data_partita': data_partita,
                'squadra_casa': squadra_casa,
                'squadra_trasferta': squadra_trasferta,
                'stato': stato
            }
            
            # Aggiungi i campi opzionali se presenti
            if giornata is not None:
                partita_data['giornata'] = giornata
            if ora:
                partita_data['ora'] = ora
            if luogo:
                partita_data['luogo'] = luogo
            if note:
                partita_data['note'] = note
            
            response = supabase.table('partite_campionato').insert(partita_data).execute()
            
            if response.data:
                return response.data[0]
    except Exception as e:
        print(f"Errore nella creazione della partita: {e}")
    
    return None

def aggiorna_partita(partita_id: int, data_partita: str, squadra_casa: str, squadra_trasferta: str, 
                    giornata: Optional[int] = None, ora: Optional[str] = None, luogo: str = "", 
                    note: str = "", stato: str = "programmata", punteggio_casa: Optional[int] = None, 
                    punteggio_trasferta: Optional[int] = None, mete_casa: Optional[int] = None, 
                    mete_trasferta: Optional[int] = None) -> bool:
    """
    Aggiorna una partita esistente.
    
    Args:
        partita_id: ID della partita da aggiornare
        data_partita: Nuova data della partita
        squadra_casa: Nuovo nome della squadra di casa
        squadra_trasferta: Nuovo nome della squadra in trasferta
        giornata: Nuovo numero della giornata
        ora: Nuova ora della partita
        luogo: Nuovo luogo della partita
        note: Nuove note sulla partita
        stato: Nuovo stato della partita
        punteggio_casa: Nuovo punteggio della squadra di casa
        punteggio_trasferta: Nuovo punteggio della squadra in trasferta
        mete_casa: Nuovo numero di mete della squadra di casa
        mete_trasferta: Nuovo numero di mete della squadra in trasferta
        
    Returns:
        True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Aggiorna la partita
            partita_data = {
                'data_partita': data_partita,
                'squadra_casa': squadra_casa,
                'squadra_trasferta': squadra_trasferta,
                'stato': stato
            }
            
            # Aggiungi i campi opzionali se presenti
            if giornata is not None:
                partita_data['giornata'] = giornata
            if ora:
                partita_data['ora'] = ora
            if luogo:
                partita_data['luogo'] = luogo
            if note:
                partita_data['note'] = note
            if punteggio_casa is not None:
                partita_data['punteggio_casa'] = punteggio_casa
            if punteggio_trasferta is not None:
                partita_data['punteggio_trasferta'] = punteggio_trasferta
            if mete_casa is not None:
                partita_data['mete_casa'] = mete_casa
            if mete_trasferta is not None:
                partita_data['mete_trasferta'] = mete_trasferta
            
            supabase.table('partite_campionato').update(partita_data).eq('id', partita_id).execute()
            
            # Se la partita è completata, aggiorna la classifica
            if stato == "completata" and punteggio_casa is not None and punteggio_trasferta is not None:
                partita = get_partita(partita_id)
                if partita:
                    aggiorna_classifica_dopo_partita(partita)
            
            return True
    except Exception as e:
        print(f"Errore nell'aggiornamento della partita: {e}")
    
    return False

def elimina_partita(partita_id: int) -> bool:
    """
    Elimina una partita.
    
    Args:
        partita_id: ID della partita da eliminare
        
    Returns:
        True se l'eliminazione è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Elimina la partita
            supabase.table('partite_campionato').delete().eq('id', partita_id).execute()
            
            return True
    except Exception as e:
        print(f"Errore nell'eliminazione della partita: {e}")
    
    return False

# Funzioni per la gestione delle designazioni arbitrali
def carica_designazioni_partita(partita_id: int) -> List[Dict[str, Any]]:
    """
    Carica le designazioni arbitrali di una partita.
    
    Args:
        partita_id: ID della partita
        
    Returns:
        Lista delle designazioni arbitrali
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('designazioni_arbitrali').select('*').eq('partita_id', partita_id).execute()
            
            return response.data
    except Exception as e:
        print(f"Errore nel caricamento delle designazioni arbitrali: {e}")
    
    return []

def aggiungi_designazione(partita_id: int, arbitro_id: int, ruolo: str, 
                         confermata: bool = False, note: str = "") -> Optional[Dict[str, Any]]:
    """
    Aggiunge una designazione arbitrale.
    
    Args:
        partita_id: ID della partita
        arbitro_id: ID dell'arbitro
        ruolo: Ruolo dell'arbitro (es. "primo", "secondo", "TMO")
        confermata: Se True, la designazione è confermata
        note: Note sulla designazione
        
    Returns:
        Dizionario con i dati della designazione creata, o None in caso di errore
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Verifica se esiste già una designazione per questo arbitro e ruolo
            response = supabase.table('designazioni_arbitrali').select('*').eq('partita_id', partita_id).eq('arbitro_id', arbitro_id).eq('ruolo', ruolo).execute()
            
            if response.data:
                # Aggiorna la designazione esistente
                supabase.table('designazioni_arbitrali').update({
                    'confermata': confermata,
                    'note': note
                }).eq('id', response.data[0].get('id')).execute()
                
                return response.data[0]
            else:
                # Crea una nuova designazione
                designazione_data = {
                    'partita_id': partita_id,
                    'arbitro_id': arbitro_id,
                    'ruolo': ruolo,
                    'confermata': confermata,
                    'note': note
                }
                
                response = supabase.table('designazioni_arbitrali').insert(designazione_data).execute()
                
                if response.data:
                    return response.data[0]
    except Exception as e:
        print(f"Errore nell'aggiunta della designazione arbitrale: {e}")
    
    return None

def rimuovi_designazione(designazione_id: int) -> bool:
    """
    Rimuove una designazione arbitrale.
    
    Args:
        designazione_id: ID della designazione da rimuovere
        
    Returns:
        True se la rimozione è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Rimuovi la designazione
            supabase.table('designazioni_arbitrali').delete().eq('id', designazione_id).execute()
            
            return True
    except Exception as e:
        print(f"Errore nella rimozione della designazione arbitrale: {e}")
    
    return False

# Funzioni per la gestione della classifica
def carica_classifica_campionato(campionato_id: int) -> List[Dict[str, Any]]:
    """
    Carica la classifica di un campionato.
    
    Args:
        campionato_id: ID del campionato
        
    Returns:
        Lista delle squadre con i relativi punteggi
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('classifica_campionato').select('*').eq('campionato_id', campionato_id).order('punti', desc=True).execute()
            
            return response.data
    except Exception as e:
        print(f"Errore nel caricamento della classifica del campionato: {e}")
    
    return []

def inizializza_classifica_campionato(campionato_id: int) -> bool:
    """
    Inizializza la classifica di un campionato.
    
    Args:
        campionato_id: ID del campionato
        
    Returns:
        True se l'inizializzazione è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Carica le squadre del campionato
            squadre = carica_squadre_campionato(campionato_id)
            
            # Elimina la classifica esistente
            supabase.table('classifica_campionato').delete().eq('campionato_id', campionato_id).execute()
            
            # Crea una nuova riga per ogni squadra
            for squadra in squadre:
                supabase.table('classifica_campionato').insert({
                    'campionato_id': campionato_id,
                    'squadra': squadra
                }).execute()
            
            return True
    except Exception as e:
        print(f"Errore nell'inizializzazione della classifica del campionato: {e}")
    
    return False

def aggiorna_classifica_dopo_partita(partita: Dict[str, Any]) -> bool:
    """
    Aggiorna la classifica dopo una partita.
    
    Args:
        partita: Dizionario con i dati della partita
        
    Returns:
        True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            campionato_id = partita.get('campionato_id')
            squadra_casa = partita.get('squadra_casa')
            squadra_trasferta = partita.get('squadra_trasferta')
            punteggio_casa = partita.get('punteggio_casa')
            punteggio_trasferta = partita.get('punteggio_trasferta')
            mete_casa = partita.get('mete_casa', 0)
            mete_trasferta = partita.get('mete_trasferta', 0)
            
            # Verifica che i punteggi siano presenti
            if punteggio_casa is None or punteggio_trasferta is None:
                return False
            
            # Carica le righe della classifica per le due squadre
            response_casa = supabase.table('classifica_campionato').select('*').eq('campionato_id', campionato_id).eq('squadra', squadra_casa).execute()
            response_trasferta = supabase.table('classifica_campionato').select('*').eq('campionato_id', campionato_id).eq('squadra', squadra_trasferta).execute()
            
            # Se le righe non esistono, inizializza la classifica
            if not response_casa.data or not response_trasferta.data:
                inizializza_classifica_campionato(campionato_id)
                response_casa = supabase.table('classifica_campionato').select('*').eq('campionato_id', campionato_id).eq('squadra', squadra_casa).execute()
                response_trasferta = supabase.table('classifica_campionato').select('*').eq('campionato_id', campionato_id).eq('squadra', squadra_trasferta).execute()
            
            # Ottieni i dati attuali
            classifica_casa = response_casa.data[0] if response_casa.data else None
            classifica_trasferta = response_trasferta.data[0] if response_trasferta.data else None
            
            if not classifica_casa or not classifica_trasferta:
                return False
            
            # Calcola i punti per la partita
            punti_casa = 0
            punti_trasferta = 0
            vittoria_casa = False
            vittoria_trasferta = False
            pareggio = False
            
            if punteggio_casa > punteggio_trasferta:
                punti_casa = 4  # Vittoria
                vittoria_casa = True
            elif punteggio_trasferta > punteggio_casa:
                punti_trasferta = 4  # Vittoria
                vittoria_trasferta = True
            else:
                punti_casa = 2  # Pareggio
                punti_trasferta = 2  # Pareggio
                pareggio = True
            
            # Bonus offensivo (4+ mete)
            bonus_offensivo_casa = 1 if mete_casa >= 4 else 0
            bonus_offensivo_trasferta = 1 if mete_trasferta >= 4 else 0
            
            punti_casa += bonus_offensivo_casa
            punti_trasferta += bonus_offensivo_trasferta
            
            # Bonus difensivo (sconfitta con meno di 8 punti di scarto)
            if vittoria_casa and (punteggio_casa - punteggio_trasferta) < 8:
                punti_trasferta += 1  # Bonus difensivo
                bonus_difensivo_trasferta = 1
            else:
                bonus_difensivo_trasferta = 0
            
            if vittoria_trasferta and (punteggio_trasferta - punteggio_casa) < 8:
                punti_casa += 1  # Bonus difensivo
                bonus_difensivo_casa = 1
            else:
                bonus_difensivo_casa = 0
            
            # Aggiorna la classifica della squadra di casa
            dati_casa = {
                'punti': classifica_casa.get('punti', 0) + punti_casa,
                'partite_giocate': classifica_casa.get('partite_giocate', 0) + 1,
                'vittorie': classifica_casa.get('vittorie', 0) + (1 if vittoria_casa else 0),
                'pareggi': classifica_casa.get('pareggi', 0) + (1 if pareggio else 0),
                'sconfitte': classifica_casa.get('sconfitte', 0) + (1 if vittoria_trasferta else 0),
                'mete_fatte': classifica_casa.get('mete_fatte', 0) + mete_casa,
                'mete_subite': classifica_casa.get('mete_subite', 0) + mete_trasferta,
                'punti_fatti': classifica_casa.get('punti_fatti', 0) + punteggio_casa,
                'punti_subiti': classifica_casa.get('punti_subiti', 0) + punteggio_trasferta,
                'bonus_offensivi': classifica_casa.get('bonus_offensivi', 0) + bonus_offensivo_casa,
                'bonus_difensivi': classifica_casa.get('bonus_difensivi', 0) + bonus_difensivo_casa
            }
            
            supabase.table('classifica_campionato').update(dati_casa).eq('id', classifica_casa.get('id')).execute()
            
            # Aggiorna la classifica della squadra in trasferta
            dati_trasferta = {
                'punti': classifica_trasferta.get('punti', 0) + punti_trasferta,
                'partite_giocate': classifica_trasferta.get('partite_giocate', 0) + 1,
                'vittorie': classifica_trasferta.get('vittorie', 0) + (1 if vittoria_trasferta else 0),
                'pareggi': classifica_trasferta.get('pareggi', 0) + (1 if pareggio else 0),
                'sconfitte': classifica_trasferta.get('sconfitte', 0) + (1 if vittoria_casa else 0),
                'mete_fatte': classifica_trasferta.get('mete_fatte', 0) + mete_trasferta,
                'mete_subite': classifica_trasferta.get('mete_subite', 0) + mete_casa,
                'punti_fatti': classifica_trasferta.get('punti_fatti', 0) + punteggio_trasferta,
                'punti_subiti': classifica_trasferta.get('punti_subiti', 0) + punteggio_casa,
                'bonus_offensivi': classifica_trasferta.get('bonus_offensivi', 0) + bonus_offensivo_trasferta,
                'bonus_difensivi': classifica_trasferta.get('bonus_difensivi', 0) + bonus_difensivo_trasferta
            }
            
            supabase.table('classifica_campionato').update(dati_trasferta).eq('id', classifica_trasferta.get('id')).execute()
            
            return True
    except Exception as e:
        print(f"Errore nell'aggiornamento della classifica dopo la partita: {e}")
    
    return False

def ricalcola_classifica_campionato(campionato_id: int) -> bool:
    """
    Ricalcola la classifica di un campionato.
    
    Args:
        campionato_id: ID del campionato
        
    Returns:
        True se il ricalcolo è riuscito, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Inizializza la classifica
            inizializza_classifica_campionato(campionato_id)
            
            # Carica tutte le partite completate
            response = supabase.table('partite_campionato').select('*').eq('campionato_id', campionato_id).eq('stato', 'completata').execute()
            
            # Aggiorna la classifica per ogni partita
            for partita in response.data:
                aggiorna_classifica_dopo_partita(partita)
            
            return True
    except Exception as e:
        print(f"Errore nel ricalcolo della classifica del campionato: {e}")
    
    return False

# Funzioni di utilità
def get_nome_completo_arbitro(arbitro: Dict[str, Any]) -> str:
    """
    Ottiene il nome completo di un arbitro.
    
    Args:
        arbitro: Dizionario con i dati dell'arbitro
        
    Returns:
        Nome completo dell'arbitro (cognome + nome)
    """
    return f"{arbitro.get('cognome', '')} {arbitro.get('nome', '')}"

def get_prossime_partite(giorni: int = 7) -> List[Dict[str, Any]]:
    """
    Ottiene le prossime partite in programma.
    
    Args:
        giorni: Numero di giorni da considerare
        
    Returns:
        Lista delle prossime partite
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Calcola la data di inizio e fine
            oggi = datetime.now().date()
            data_fine = (oggi + timedelta(days=giorni)).strftime('%Y-%m-%d')
            oggi_str = oggi.strftime('%Y-%m-%d')
            
            # Carica le partite
            response = supabase.table('partite_campionato').select('*').gte('data_partita', oggi_str).lte('data_partita', data_fine).order('data_partita').execute()
            
            return response.data
    except Exception as e:
        print(f"Errore nel caricamento delle prossime partite: {e}")
    
    return []

def get_ultime_partite(giorni: int = 7) -> List[Dict[str, Any]]:
    """
    Ottiene le ultime partite giocate.
    
    Args:
        giorni: Numero di giorni da considerare
        
    Returns:
        Lista delle ultime partite
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Calcola la data di inizio e fine
            oggi = datetime.now().date()
            data_inizio = (oggi - timedelta(days=giorni)).strftime('%Y-%m-%d')
            oggi_str = oggi.strftime('%Y-%m-%d')
            
            # Carica le partite
            response = supabase.table('partite_campionato').select('*').gte('data_partita', data_inizio).lte('data_partita', oggi_str).eq('stato', 'completata').order('data_partita', desc=True).execute()
            
            return response.data
    except Exception as e:
        print(f"Errore nel caricamento delle ultime partite: {e}")
    
    return []

def get_designazioni_arbitro(arbitro_id: int) -> List[Dict[str, Any]]:
    """
    Ottiene le designazioni di un arbitro.
    
    Args:
        arbitro_id: ID dell'arbitro
        
    Returns:
        Lista delle designazioni
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Carica le designazioni
            response = supabase.table('designazioni_arbitrali').select('*').eq('arbitro_id', arbitro_id).execute()
            
            return response.data
    except Exception as e:
        print(f"Errore nel caricamento delle designazioni dell'arbitro: {e}")
    
    return []

def get_partite_squadra(squadra: str) -> List[Dict[str, Any]]:
    """
    Ottiene le partite di una squadra.
    
    Args:
        squadra: Nome della squadra
        
    Returns:
        Lista delle partite
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Carica le partite in casa
            response_casa = supabase.table('partite_campionato').select('*').eq('squadra_casa', squadra).execute()
            
            # Carica le partite in trasferta
            response_trasferta = supabase.table('partite_campionato').select('*').eq('squadra_trasferta', squadra).execute()
            
            # Unisci i risultati
            partite = response_casa.data + response_trasferta.data
            
            # Ordina per data
            partite.sort(key=lambda x: x.get('data_partita', ''))
            
            return partite
    except Exception as e:
        print(f"Errore nel caricamento delle partite della squadra: {e}")
    
    return []

def genera_calendario_campionato(campionato_id: int, data_inizio: str, intervallo_giorni: int = 7) -> bool:
    """
    Genera il calendario di un campionato.
    
    Args:
        campionato_id: ID del campionato
        data_inizio: Data di inizio del campionato (formato "YYYY-MM-DD")
        intervallo_giorni: Intervallo in giorni tra le giornate
        
    Returns:
        True se la generazione è riuscita, False altrimenti
    """
    try:
        # Carica le squadre del campionato
        squadre = carica_squadre_campionato(campionato_id)
        
        # Verifica che ci siano almeno 2 squadre
        if len(squadre) < 2:
            return False
        
        # Se il numero di squadre è dispari, aggiungi una squadra fittizia
        if len(squadre) % 2 != 0:
            squadre.append("Riposo")
        
        n = len(squadre)
        giornate = n - 1
        partite_per_giornata = n // 2
        
        # Crea il calendario
        calendario = []
        
        for giornata in range(giornate):
            partite_giornata = []
            
            for i in range(partite_per_giornata):
                squadra_casa = squadre[i]
                squadra_trasferta = squadre[n - 1 - i]
                
                # Salta le partite con la squadra fittizia
                if squadra_casa != "Riposo" and squadra_trasferta != "Riposo":
                    partite_giornata.append((squadra_casa, squadra_trasferta))
            
            calendario.append(partite_giornata)
            
            # Ruota le squadre (la prima rimane fissa)
            squadre = [squadre[0]] + [squadre[-1]] + squadre[1:-1]
        
        # Calcola le date delle giornate
        data_inizio_dt = datetime.strptime(data_inizio, '%Y-%m-%d')
        
        # Elimina le partite esistenti
        from modules.db_manager import is_supabase_configured, supabase
        if is_supabase_configured():
            supabase.table('partite_campionato').delete().eq('campionato_id', campionato_id).execute()
        
        # Crea le partite nel database
        for giornata, partite_giornata in enumerate(calendario, 1):
            data_giornata = (data_inizio_dt + timedelta(days=intervallo_giorni * (giornata - 1))).strftime('%Y-%m-%d')
            
            for squadra_casa, squadra_trasferta in partite_giornata:
                crea_partita(
                    campionato_id=campionato_id,
                    giornata=giornata,
                    data_partita=data_giornata,
                    squadra_casa=squadra_casa,
                    squadra_trasferta=squadra_trasferta
                )
        
        # Crea anche il girone di ritorno
        for giornata, partite_giornata in enumerate(calendario, giornate + 1):
            data_giornata = (data_inizio_dt + timedelta(days=intervallo_giorni * (giornata - 1))).strftime('%Y-%m-%d')
            
            for squadra_casa, squadra_trasferta in partite_giornata:
                # Inverti casa e trasferta
                crea_partita(
                    campionato_id=campionato_id,
                    giornata=giornata,
                    data_partita=data_giornata,
                    squadra_casa=squadra_trasferta,
                    squadra_trasferta=squadra_casa
                )
        
        return True
    except Exception as e:
        print(f"Errore nella generazione del calendario: {e}")
    
    return False