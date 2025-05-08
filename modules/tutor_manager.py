#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from typing import List, Dict, Any, Optional

# Cache per i dati
_cache = {
    'tutor_arbitrali': None,
    'last_load_tutor_arbitrali': 0
}

# Tempo di validità della cache in secondi (5 secondi)
CACHE_TTL = 5

# Funzioni per la gestione dei tutor arbitrali
def carica_tutor_arbitrali(force_reload=False) -> List[Dict[str, Any]]:
    """
    Carica i tutor arbitrali dal database.
    
    Args:
        force_reload: Se True, forza il ricaricamento anche se la cache è valida
        
    Returns:
        Lista dei tutor arbitrali
    """
    current_time = time.time()
    
    # Usa la cache se disponibile e non scaduta
    if not force_reload and _cache['tutor_arbitrali'] is not None and (current_time - _cache['last_load_tutor_arbitrali']) < CACHE_TTL:
        return _cache['tutor_arbitrali']
    
    # Carica dal database
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('tutor_arbitrali').select('*').order('cognome').execute()
            tutor_arbitrali = response.data
            
            # Aggiorna la cache
            _cache['tutor_arbitrali'] = tutor_arbitrali
            _cache['last_load_tutor_arbitrali'] = current_time
            
            return tutor_arbitrali
        else:
            # Dati di esempio se Supabase non è configurato
            tutor_arbitrali = [
                {
                    'id': 1,
                    'nome': 'Mario',
                    'cognome': 'Rossi',
                    'email': 'mario.rossi@example.com',
                    'telefono': '3331234567',
                    'qualifica': 'nazionale',
                    'attivo': True,
                    'note': 'Tutor esperto'
                },
                {
                    'id': 2,
                    'nome': 'Giuseppe',
                    'cognome': 'Verdi',
                    'email': 'giuseppe.verdi@example.com',
                    'telefono': '3339876543',
                    'qualifica': 'regionale',
                    'attivo': True,
                    'note': ''
                }
            ]
            
            # Aggiorna la cache
            _cache['tutor_arbitrali'] = tutor_arbitrali
            _cache['last_load_tutor_arbitrali'] = current_time
            
            return tutor_arbitrali
    except Exception as e:
        print(f"Errore nel caricamento dei tutor arbitrali: {e}")
        return []

def get_tutor(tutor_id: int) -> Optional[Dict[str, Any]]:
    """
    Ottiene un tutor arbitrale dal database.
    
    Args:
        tutor_id: ID del tutor
        
    Returns:
        Dati del tutor o None se non trovato
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('tutor_arbitrali').select('*').eq('id', tutor_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
        else:
            # Dati di esempio se Supabase non è configurato
            tutor_arbitrali = carica_tutor_arbitrali()
            for tutor in tutor_arbitrali:
                if tutor['id'] == tutor_id:
                    return tutor
    except Exception as e:
        print(f"Errore nel caricamento del tutor: {e}")
    
    return None

def crea_tutor(nome: str, cognome: str, email: str, telefono: str, qualifica: str, attivo: bool, note: str) -> Optional[Dict[str, Any]]:
    """
    Crea un nuovo tutor arbitrale.
    
    Args:
        nome: Nome del tutor
        cognome: Cognome del tutor
        email: Email del tutor
        telefono: Telefono del tutor
        qualifica: Qualifica del tutor (regionale, nazionale, internazionale)
        attivo: Se il tutor è attivo
        note: Note sul tutor
        
    Returns:
        Dati del tutor creato o None in caso di errore
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            tutor_data = {
                'nome': nome,
                'cognome': cognome,
                'email': email,
                'telefono': telefono,
                'qualifica': qualifica,
                'attivo': attivo,
                'note': note
            }
            
            response = supabase.table('tutor_arbitrali').insert(tutor_data).execute()
            
            if response.data and len(response.data) > 0:
                # Invalida la cache
                _cache['tutor_arbitrali'] = None
                return response.data[0]
        else:
            # Simulazione di creazione se Supabase non è configurato
            tutor_arbitrali = carica_tutor_arbitrali()
            new_id = max([t['id'] for t in tutor_arbitrali], default=0) + 1
            
            tutor_data = {
                'id': new_id,
                'nome': nome,
                'cognome': cognome,
                'email': email,
                'telefono': telefono,
                'qualifica': qualifica,
                'attivo': attivo,
                'note': note
            }
            
            # Invalida la cache
            _cache['tutor_arbitrali'] = None
            return tutor_data
    except Exception as e:
        print(f"Errore nella creazione del tutor: {e}")
    
    return None

def aggiorna_tutor(tutor_id: int, nome: str, cognome: str, email: str, telefono: str, qualifica: str, attivo: bool, note: str) -> bool:
    """
    Aggiorna un tutor arbitrale esistente.
    
    Args:
        tutor_id: ID del tutor
        nome: Nome del tutor
        cognome: Cognome del tutor
        email: Email del tutor
        telefono: Telefono del tutor
        qualifica: Qualifica del tutor (regionale, nazionale, internazionale)
        attivo: Se il tutor è attivo
        note: Note sul tutor
        
    Returns:
        True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            tutor_data = {
                'nome': nome,
                'cognome': cognome,
                'email': email,
                'telefono': telefono,
                'qualifica': qualifica,
                'attivo': attivo,
                'note': note
            }
            
            response = supabase.table('tutor_arbitrali').update(tutor_data).eq('id', tutor_id).execute()
            
            # Invalida la cache
            _cache['tutor_arbitrali'] = None
            return True
        else:
            # Simulazione di aggiornamento se Supabase non è configurato
            tutor_arbitrali = carica_tutor_arbitrali()
            for i, tutor in enumerate(tutor_arbitrali):
                if tutor['id'] == tutor_id:
                    tutor_arbitrali[i] = {
                        'id': tutor_id,
                        'nome': nome,
                        'cognome': cognome,
                        'email': email,
                        'telefono': telefono,
                        'qualifica': qualifica,
                        'attivo': attivo,
                        'note': note
                    }
                    
                    # Invalida la cache
                    _cache['tutor_arbitrali'] = None
                    return True
    except Exception as e:
        print(f"Errore nell'aggiornamento del tutor: {e}")
    
    return False

def elimina_tutor(tutor_id: int) -> bool:
    """
    Elimina un tutor arbitrale.
    
    Args:
        tutor_id: ID del tutor
        
    Returns:
        True se l'eliminazione è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Elimina il tutor
            response = supabase.table('tutor_arbitrali').delete().eq('id', tutor_id).execute()
            
            # Invalida la cache
            _cache['tutor_arbitrali'] = None
            return True
        else:
            # Simulazione di eliminazione se Supabase non è configurato
            tutor_arbitrali = carica_tutor_arbitrali()
            for i, tutor in enumerate(tutor_arbitrali):
                if tutor['id'] == tutor_id:
                    del tutor_arbitrali[i]
                    
                    # Invalida la cache
                    _cache['tutor_arbitrali'] = None
                    return True
    except Exception as e:
        print(f"Errore nell'eliminazione del tutor: {e}")
    
    return False

def get_tutor_partita(partita_id: int) -> Optional[Dict[str, Any]]:
    """
    Ottiene il tutor assegnato a una partita.
    
    Args:
        partita_id: ID della partita
        
    Returns:
        Dati dell'assegnazione del tutor o None se non trovato
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            response = supabase.table('tutor_partite').select('*').eq('partita_id', partita_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
        else:
            # Dati di esempio se Supabase non è configurato
            if partita_id % 2 == 0:  # Simuliamo che solo alcune partite hanno tutor
                return {
                    'id': partita_id * 10,
                    'partita_id': partita_id,
                    'tutor_id': 1,
                    'note': 'Osservazione arbitrale'
                }
    except Exception as e:
        print(f"Errore nel caricamento del tutor della partita: {e}")
    
    return None

def assegna_tutor_partita(partita_id: int, tutor_id: int, note: str) -> bool:
    """
    Assegna un tutor a una partita.
    
    Args:
        partita_id: ID della partita
        tutor_id: ID del tutor
        note: Note sull'assegnazione
        
    Returns:
        True se l'assegnazione è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            tutor_partita_data = {
                'partita_id': partita_id,
                'tutor_id': tutor_id,
                'note': note
            }
            
            response = supabase.table('tutor_partite').insert(tutor_partita_data).execute()
            
            return True
        else:
            # Simulazione di assegnazione se Supabase non è configurato
            return True
    except Exception as e:
        print(f"Errore nell'assegnazione del tutor alla partita: {e}")
    
    return False

def rimuovi_tutor_partita(tutor_partita_id: int) -> bool:
    """
    Rimuove un tutor da una partita.
    
    Args:
        tutor_partita_id: ID dell'assegnazione del tutor
        
    Returns:
        True se la rimozione è riuscita, False altrimenti
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Rimuovi l'assegnazione
            response = supabase.table('tutor_partite').delete().eq('id', tutor_partita_id).execute()
            
            return True
        else:
            # Simulazione di rimozione se Supabase non è configurato
            return True
    except Exception as e:
        print(f"Errore nella rimozione del tutor dalla partita: {e}")
    
    return False