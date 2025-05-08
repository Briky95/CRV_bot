#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from modules.campionati_manager import (
    carica_designazioni_partita, get_partita, get_arbitro, get_tutor,
    get_tutor_partita
)
from modules.db_manager import format_date

# Cache per i dati
_cache = {
    'impegni_arbitri': {},
    'impegni_tutor': {},
    'last_load_impegni': 0
}

# Tempo di validità della cache in secondi (30 secondi)
CACHE_TTL = 30

def verifica_impegni_arbitro(arbitro_id: int, data_partita: str, partita_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Verifica se un arbitro è già impegnato in una partita nella data specificata.
    
    Args:
        arbitro_id: ID dell'arbitro
        data_partita: Data della partita in formato ISO (YYYY-MM-DD)
        partita_id: ID della partita corrente (opzionale, per escluderla dalla verifica)
        
    Returns:
        Lista di partite in cui l'arbitro è già impegnato nella data specificata
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Verifica se i dati sono in cache e ancora validi
            cache_key = f'impegni_arbitro_{arbitro_id}_{data_partita}'
            current_time = time.time()
            
            if cache_key in _cache['impegni_arbitri'] and (current_time - _cache['last_load_impegni']) < CACHE_TTL:
                impegni = _cache['impegni_arbitri'][cache_key]
                # Filtra escludendo la partita corrente
                if partita_id:
                    return [i for i in impegni if i['partita_id'] != partita_id]
                return impegni
            
            # Carica le designazioni dell'arbitro
            response = supabase.table('designazioni_arbitrali').select('*').eq('arbitro_id', arbitro_id).execute()
            designazioni = response.data
            
            # Filtra le designazioni per data
            impegni = []
            for designazione in designazioni:
                partita = get_partita(designazione.get('partita_id'))
                if partita and partita.get('data_partita') == data_partita:
                    # Esclude la partita corrente
                    if partita_id and partita.get('id') == partita_id:
                        continue
                    
                    impegni.append({
                        'partita_id': partita.get('id'),
                        'squadra_casa': partita.get('squadra_casa', ''),
                        'squadra_trasferta': partita.get('squadra_trasferta', ''),
                        'ora': partita.get('ora', ''),
                        'luogo': partita.get('luogo', ''),
                        'ruolo': designazione.get('ruolo', ''),
                        'data_formattata': format_date(data_partita)
                    })
            
            # Aggiorna la cache
            _cache['impegni_arbitri'][cache_key] = impegni
            _cache['last_load_impegni'] = current_time
            
            return impegni
        else:
            # Dati di esempio se Supabase non è configurato
            return []
    except Exception as e:
        print(f"Errore nella verifica degli impegni dell'arbitro: {e}")
        return []

def verifica_impegni_tutor(tutor_id: int, data_partita: str, partita_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Verifica se un tutor è già impegnato in una partita nella data specificata.
    
    Args:
        tutor_id: ID del tutor
        data_partita: Data della partita in formato ISO (YYYY-MM-DD)
        partita_id: ID della partita corrente (opzionale, per escluderla dalla verifica)
        
    Returns:
        Lista di partite in cui il tutor è già impegnato nella data specificata
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Verifica se i dati sono in cache e ancora validi
            cache_key = f'impegni_tutor_{tutor_id}_{data_partita}'
            current_time = time.time()
            
            if cache_key in _cache['impegni_tutor'] and (current_time - _cache['last_load_impegni']) < CACHE_TTL:
                impegni = _cache['impegni_tutor'][cache_key]
                # Filtra escludendo la partita corrente
                if partita_id:
                    return [i for i in impegni if i['partita_id'] != partita_id]
                return impegni
            
            # Carica le assegnazioni del tutor
            response = supabase.table('tutor_partite').select('*').eq('tutor_id', tutor_id).execute()
            assegnazioni = response.data
            
            # Filtra le assegnazioni per data
            impegni = []
            for assegnazione in assegnazioni:
                partita = get_partita(assegnazione.get('partita_id'))
                if partita and partita.get('data_partita') == data_partita:
                    # Esclude la partita corrente
                    if partita_id and partita.get('id') == partita_id:
                        continue
                    
                    impegni.append({
                        'partita_id': partita.get('id'),
                        'squadra_casa': partita.get('squadra_casa', ''),
                        'squadra_trasferta': partita.get('squadra_trasferta', ''),
                        'ora': partita.get('ora', ''),
                        'luogo': partita.get('luogo', ''),
                        'data_formattata': format_date(data_partita)
                    })
            
            # Aggiorna la cache
            _cache['impegni_tutor'][cache_key] = impegni
            _cache['last_load_impegni'] = current_time
            
            return impegni
        else:
            # Dati di esempio se Supabase non è configurato
            return []
    except Exception as e:
        print(f"Errore nella verifica degli impegni del tutor: {e}")
        return []

def formatta_impegni_arbitro(impegni: List[Dict[str, Any]]) -> str:
    """
    Formatta gli impegni di un arbitro in una stringa HTML.
    
    Args:
        impegni: Lista di impegni dell'arbitro
        
    Returns:
        Stringa HTML con gli impegni formattati
    """
    if not impegni:
        return ""
    
    html = "<ul class='list-unstyled'>"
    for impegno in impegni:
        ruolo_display = "Arbitro"
        if impegno.get('ruolo') == 'primo':
            ruolo_display = "Primo arbitro"
        elif impegno.get('ruolo') == 'secondo':
            ruolo_display = "Secondo arbitro"
        elif impegno.get('ruolo') == 'TMO':
            ruolo_display = "TMO"
        elif impegno.get('ruolo') == 'quarto_uomo':
            ruolo_display = "Quarto uomo"
        elif impegno.get('ruolo') == 'giudice_di_linea':
            ruolo_display = "Giudice di linea"
        
        ora = f" alle {impegno.get('ora')}" if impegno.get('ora') else ""
        luogo = f" a {impegno.get('luogo')}" if impegno.get('luogo') else ""
        
        html += f"<li><strong>{impegno.get('squadra_casa')} - {impegno.get('squadra_trasferta')}</strong>{ora}{luogo} ({ruolo_display})</li>"
    
    html += "</ul>"
    return html

def formatta_impegni_tutor(impegni: List[Dict[str, Any]]) -> str:
    """
    Formatta gli impegni di un tutor in una stringa HTML.
    
    Args:
        impegni: Lista di impegni del tutor
        
    Returns:
        Stringa HTML con gli impegni formattati
    """
    if not impegni:
        return ""
    
    html = "<ul class='list-unstyled'>"
    for impegno in impegni:
        ora = f" alle {impegno.get('ora')}" if impegno.get('ora') else ""
        luogo = f" a {impegno.get('luogo')}" if impegno.get('luogo') else ""
        
        html += f"<li><strong>{impegno.get('squadra_casa')} - {impegno.get('squadra_trasferta')}</strong>{ora}{luogo} (Tutor)</li>"
    
    html += "</ul>"
    return html