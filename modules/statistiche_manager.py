#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter

from modules.campionati_manager import (
    carica_arbitri, get_arbitro, carica_campionati, get_campionato,
    carica_designazioni_partita, get_tutor, get_tutor_partita
)
from modules.db_manager import format_date

# Cache per i dati
_cache = {
    'statistiche_arbitri': None,
    'last_load_statistiche': 0
}

# Tempo di validità della cache in secondi (30 secondi)
CACHE_TTL = 30

def carica_statistiche_arbitri(stagione_id=None, categoria=None, force_reload=False) -> Dict[str, Any]:
    """
    Carica le statistiche degli arbitri.
    
    Args:
        stagione_id: ID della stagione per filtrare le statistiche (opzionale)
        categoria: Categoria per filtrare le statistiche (opzionale)
        force_reload: Se True, forza il ricaricamento anche se la cache è valida
        
    Returns:
        Dizionario con le statistiche degli arbitri
    """
    cache_key = f'statistiche_arbitri_{stagione_id}_{categoria}'
    current_time = time.time()
    
    # Usa la cache se disponibile e non scaduta
    if not force_reload and _cache.get(cache_key) is not None and (current_time - _cache.get(f'last_load_{cache_key}', 0)) < CACHE_TTL:
        return _cache[cache_key]
    
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Carica gli arbitri
            arbitri = carica_arbitri()
            
            # Prepara la query per le partite
            query = supabase.table('partite_campionato').select('*')
            
            # Applica i filtri
            if stagione_id:
                # Ottieni i campionati della stagione
                campionati = carica_campionati(stagione_id)
                campionati_ids = [c['id'] for c in campionati]
                if campionati_ids:
                    query = query.in_('campionato_id', campionati_ids)
            
            # Esegui la query
            response = query.execute()
            partite = response.data
            
            # Filtra per categoria se necessario
            if categoria:
                partite_filtrate = []
                for partita in partite:
                    campionato = get_campionato(partita['campionato_id'])
                    if campionato and campionato.get('categoria') == categoria:
                        partite_filtrate.append(partita)
                partite = partite_filtrate
            
            # Carica le designazioni per ogni partita
            designazioni = []
            for partita in partite:
                partita_designazioni = carica_designazioni_partita(partita['id'])
                for designazione in partita_designazioni:
                    designazione['partita'] = partita
                    designazioni.append(designazione)
            
            # Carica i tutor per ogni partita
            tutor_partite = {}
            for partita in partite:
                tutor_partita = get_tutor_partita(partita['id'])
                if tutor_partita:
                    tutor = get_tutor(tutor_partita['tutor_id'])
                    if tutor:
                        tutor_partita['tutor'] = tutor
                        tutor_partite[partita['id']] = tutor_partita
            
            # Calcola le statistiche per ogni arbitro
            statistiche_arbitri = []
            for arbitro in arbitri:
                if not arbitro.get('attivo', True):
                    continue
                
                # Filtra le designazioni per questo arbitro
                arbitro_designazioni = [d for d in designazioni if d.get('arbitro_id') == arbitro['id']]
                
                # Calcola le statistiche
                partite_totali = len(arbitro_designazioni)
                partite_primo = len([d for d in arbitro_designazioni if d.get('ruolo') == 'primo'])
                partite_secondo = len([d for d in arbitro_designazioni if d.get('ruolo') == 'secondo'])
                partite_altri_ruoli = partite_totali - partite_primo - partite_secondo
                
                # Conta le partite con tutor
                partite_con_tutor = 0
                tutor_assegnati = defaultdict(int)
                ultima_partita_tutor = {}
                
                for designazione in arbitro_designazioni:
                    partita_id = designazione['partita']['id']
                    if partita_id in tutor_partite:
                        partite_con_tutor += 1
                        tutor_id = tutor_partite[partita_id]['tutor_id']
                        tutor_assegnati[tutor_id] += 1
                        
                        # Aggiorna l'ultima partita per questo tutor
                        data_partita = designazione['partita'].get('data_partita')
                        if data_partita:
                            if tutor_id not in ultima_partita_tutor or data_partita > ultima_partita_tutor[tutor_id]:
                                ultima_partita_tutor[tutor_id] = data_partita
                
                # Formatta i dati dei tutor
                tutor_formattati = []
                for tutor_id, partite in tutor_assegnati.items():
                    tutor_info = get_tutor(tutor_id)
                    if tutor_info:
                        tutor_formattati.append({
                            'id': tutor_id,
                            'nome': tutor_info.get('nome', ''),
                            'cognome': tutor_info.get('cognome', ''),
                            'qualifica': tutor_info.get('qualifica', ''),
                            'partite': partite,
                            'ultima_partita': format_date(ultima_partita_tutor.get(tutor_id, ''))
                        })
                
                # Aggiungi le statistiche dell'arbitro
                statistiche_arbitri.append({
                    'id': arbitro['id'],
                    'nome': arbitro.get('nome', ''),
                    'cognome': arbitro.get('cognome', ''),
                    'qualifica': arbitro.get('qualifica', ''),
                    'partite_totali': partite_totali,
                    'partite_primo': partite_primo,
                    'partite_secondo': partite_secondo,
                    'partite_altri_ruoli': partite_altri_ruoli,
                    'partite_con_tutor': partite_con_tutor,
                    'tutor_assegnati': tutor_formattati
                })
            
            # Calcola le statistiche generali
            totale_arbitri = len([a for a in arbitri if a.get('attivo', True)])
            totale_partite = len(set([d['partita']['id'] for d in designazioni]))
            media_partite = totale_partite / totale_arbitri if totale_arbitri > 0 else 0
            partite_con_tutor = len(tutor_partite)
            
            # Calcola la distribuzione per categoria
            categorie_counter = Counter()
            for partita in partite:
                campionato = get_campionato(partita['campionato_id'])
                if campionato:
                    categorie_counter[campionato.get('categoria', 'Sconosciuta')] += 1
            
            # Calcola la distribuzione per ruolo
            ruoli_counter = Counter()
            for designazione in designazioni:
                ruolo = designazione.get('ruolo', 'altro')
                ruoli_counter[ruolo] += 1
            
            # Prepara i dati per i grafici
            categorie_labels = list(categorie_counter.keys())
            categorie_data = [categorie_counter[cat] for cat in categorie_labels]
            
            ruoli_mapping = {
                'primo': 'Primo arbitro',
                'secondo': 'Secondo arbitro',
                'TMO': 'TMO',
                'quarto_uomo': 'Quarto uomo',
                'giudice_di_linea': 'Giudice di linea'
            }
            ruoli_labels = [ruoli_mapping.get(ruolo, ruolo) for ruolo in ruoli_counter.keys()]
            ruoli_data = list(ruoli_counter.values())
            
            # Prepara il risultato
            result = {
                'statistiche_arbitri': statistiche_arbitri,
                'statistiche_generali': {
                    'totale_arbitri': totale_arbitri,
                    'totale_partite': totale_partite,
                    'media_partite': media_partite,
                    'partite_con_tutor': partite_con_tutor
                },
                'categorie_labels': categorie_labels,
                'categorie_data': categorie_data,
                'ruoli_labels': ruoli_labels,
                'ruoli_data': ruoli_data
            }
            
            # Aggiorna la cache
            _cache[cache_key] = result
            _cache[f'last_load_{cache_key}'] = current_time
            
            return result
        else:
            # Dati di esempio se Supabase non è configurato
            return {
                'statistiche_arbitri': [
                    {
                        'id': 1,
                        'nome': 'Mario',
                        'cognome': 'Rossi',
                        'qualifica': 'nazionale',
                        'partite_totali': 15,
                        'partite_primo': 10,
                        'partite_secondo': 5,
                        'partite_altri_ruoli': 0,
                        'partite_con_tutor': 8,
                        'tutor_assegnati': [
                            {
                                'id': 1,
                                'nome': 'Giuseppe',
                                'cognome': 'Verdi',
                                'qualifica': 'nazionale',
                                'partite': 5,
                                'ultima_partita': '15/04/2023'
                            },
                            {
                                'id': 2,
                                'nome': 'Luigi',
                                'cognome': 'Bianchi',
                                'qualifica': 'regionale',
                                'partite': 3,
                                'ultima_partita': '22/05/2023'
                            }
                        ]
                    },
                    {
                        'id': 2,
                        'nome': 'Paolo',
                        'cognome': 'Bianchi',
                        'qualifica': 'regionale',
                        'partite_totali': 8,
                        'partite_primo': 3,
                        'partite_secondo': 5,
                        'partite_altri_ruoli': 0,
                        'partite_con_tutor': 4,
                        'tutor_assegnati': [
                            {
                                'id': 1,
                                'nome': 'Giuseppe',
                                'cognome': 'Verdi',
                                'qualifica': 'nazionale',
                                'partite': 4,
                                'ultima_partita': '10/03/2023'
                            }
                        ]
                    }
                ],
                'statistiche_generali': {
                    'totale_arbitri': 10,
                    'totale_partite': 50,
                    'media_partite': 5.0,
                    'partite_con_tutor': 25
                },
                'categorie_labels': ['Seniores', 'Under 18', 'Under 16', 'Under 14'],
                'categorie_data': [20, 15, 10, 5],
                'ruoli_labels': ['Primo arbitro', 'Secondo arbitro', 'TMO', 'Quarto uomo'],
                'ruoli_data': [30, 25, 10, 5]
            }
    except Exception as e:
        print(f"Errore nel caricamento delle statistiche degli arbitri: {e}")
        return {
            'statistiche_arbitri': [],
            'statistiche_generali': {
                'totale_arbitri': 0,
                'totale_partite': 0,
                'media_partite': 0,
                'partite_con_tutor': 0
            },
            'categorie_labels': [],
            'categorie_data': [],
            'ruoli_labels': [],
            'ruoli_data': []
        }

def carica_statistiche_arbitro(arbitro_id: int, stagione_id=None) -> Dict[str, Any]:
    """
    Carica le statistiche dettagliate di un arbitro.
    
    Args:
        arbitro_id: ID dell'arbitro
        stagione_id: ID della stagione per filtrare le statistiche (opzionale)
        
    Returns:
        Dizionario con le statistiche dell'arbitro
    """
    try:
        from modules.db_manager import is_supabase_configured
        
        if is_supabase_configured():
            from modules.db_manager import supabase
            
            # Carica l'arbitro
            arbitro = get_arbitro(arbitro_id)
            if not arbitro:
                return None
            
            # Prepara la query per le partite
            query = supabase.table('partite_campionato').select('*')
            
            # Applica i filtri per stagione
            if stagione_id:
                # Ottieni i campionati della stagione
                campionati = carica_campionati(stagione_id)
                campionati_ids = [c['id'] for c in campionati]
                if campionati_ids:
                    query = query.in_('campionato_id', campionati_ids)
            
            # Esegui la query
            response = query.execute()
            partite = response.data
            
            # Carica le designazioni per ogni partita
            designazioni = []
            for partita in partite:
                partita_designazioni = carica_designazioni_partita(partita['id'])
                for designazione in partita_designazioni:
                    if designazione.get('arbitro_id') == arbitro_id:
                        designazione['partita'] = partita
                        designazioni.append(designazione)
            
            # Carica i tutor per ogni partita
            tutor_partite = {}
            for designazione in designazioni:
                partita_id = designazione['partita']['id']
                tutor_partita = get_tutor_partita(partita_id)
                if tutor_partita:
                    tutor = get_tutor(tutor_partita['tutor_id'])
                    if tutor:
                        tutor_partita['tutor'] = tutor
                        tutor_partite[partita_id] = tutor_partita
            
            # Calcola le statistiche
            partite_totali = len(designazioni)
            partite_primo = len([d for d in designazioni if d.get('ruolo') == 'primo'])
            partite_secondo = len([d for d in designazioni if d.get('ruolo') == 'secondo'])
            partite_altri_ruoli = partite_totali - partite_primo - partite_secondo
            
            # Conta le partite con tutor
            partite_con_tutor = len(tutor_partite)
            
            # Raggruppa per tutor
            tutor_stats = defaultdict(lambda: {'partite': 0, 'prima_partita': None, 'ultima_partita': None, 'note': ''})
            for partita_id, tutor_partita in tutor_partite.items():
                tutor_id = tutor_partita['tutor_id']
                tutor_stats[tutor_id]['partite'] += 1
                
                # Trova la partita corrispondente
                for designazione in designazioni:
                    if designazione['partita']['id'] == partita_id:
                        data_partita = designazione['partita'].get('data_partita')
                        if data_partita:
                            if tutor_stats[tutor_id]['prima_partita'] is None or data_partita < tutor_stats[tutor_id]['prima_partita']:
                                tutor_stats[tutor_id]['prima_partita'] = data_partita
                            if tutor_stats[tutor_id]['ultima_partita'] is None or data_partita > tutor_stats[tutor_id]['ultima_partita']:
                                tutor_stats[tutor_id]['ultima_partita'] = data_partita
                        
                        # Aggiungi le note (prendiamo solo l'ultima)
                        tutor_stats[tutor_id]['note'] = tutor_partita.get('note', '')
            
            # Formatta i dati dei tutor
            tutor_assegnati = []
            for tutor_id, stats in tutor_stats.items():
                tutor_info = get_tutor(tutor_id)
                if tutor_info:
                    tutor_assegnati.append({
                        'id': tutor_id,
                        'nome': tutor_info.get('nome', ''),
                        'cognome': tutor_info.get('cognome', ''),
                        'qualifica': tutor_info.get('qualifica', ''),
                        'partite': stats['partite'],
                        'prima_partita': format_date(stats['prima_partita']),
                        'ultima_partita': format_date(stats['ultima_partita']),
                        'note': stats['note']
                    })
            
            # Prepara i dati delle partite
            partite_info = []
            for designazione in sorted(designazioni, key=lambda d: d['partita'].get('data_partita', ''), reverse=True):
                partita = designazione['partita']
                campionato = get_campionato(partita.get('campionato_id'))
                
                partita_info = {
                    'id': partita['id'],
                    'data_partita': format_date(partita.get('data_partita')),
                    'campionato_nome': campionato.get('nome', 'Sconosciuto') if campionato else 'Sconosciuto',
                    'squadra_casa': partita.get('squadra_casa', ''),
                    'squadra_trasferta': partita.get('squadra_trasferta', ''),
                    'ruolo': designazione.get('ruolo', ''),
                    'stato': partita.get('stato', 'programmata')
                }
                
                # Aggiungi il tutor se presente
                if partita['id'] in tutor_partite:
                    tutor_partita = tutor_partite[partita['id']]
                    tutor = tutor_partita.get('tutor')
                    if tutor:
                        partita_info['tutor'] = {
                            'nome_completo': f"{tutor.get('cognome', '')} {tutor.get('nome', '')}",
                            'note': tutor_partita.get('note', '')
                        }
                
                partite_info.append(partita_info)
            
            # Calcola la distribuzione per categoria
            categorie_counter = Counter()
            for designazione in designazioni:
                campionato = get_campionato(designazione['partita'].get('campionato_id'))
                if campionato:
                    categorie_counter[campionato.get('categoria', 'Sconosciuta')] += 1
            
            # Calcola la distribuzione per mese
            mesi_counter = defaultdict(int)
            for designazione in designazioni:
                data_partita = designazione['partita'].get('data_partita')
                if data_partita:
                    try:
                        data = datetime.strptime(data_partita, '%Y-%m-%d')
                        mese = data.strftime('%m/%Y')
                        mesi_counter[mese] += 1
                    except:
                        pass
            
            # Ordina i mesi cronologicamente
            mesi_ordinati = sorted(mesi_counter.keys(), key=lambda m: datetime.strptime(m, '%m/%Y'))
            
            # Prepara i dati per i grafici
            categorie_labels = list(categorie_counter.keys())
            categorie_data = [categorie_counter[cat] for cat in categorie_labels]
            
            mesi_labels = mesi_ordinati
            mesi_data = [mesi_counter[mese] for mese in mesi_ordinati]
            
            # Prepara il risultato
            result = {
                'arbitro': arbitro,
                'statistiche': {
                    'partite_totali': partite_totali,
                    'partite_primo': partite_primo,
                    'partite_secondo': partite_secondo,
                    'partite_altri_ruoli': partite_altri_ruoli,
                    'partite_con_tutor': partite_con_tutor,
                    'tutor_assegnati': tutor_assegnati,
                    'partite': partite_info
                },
                'categorie_labels': categorie_labels,
                'categorie_data': categorie_data,
                'mesi_labels': mesi_labels,
                'mesi_data': mesi_data
            }
            
            return result
        else:
            # Dati di esempio se Supabase non è configurato
            return {
                'arbitro': {
                    'id': arbitro_id,
                    'nome': 'Mario',
                    'cognome': 'Rossi',
                    'email': 'mario.rossi@example.com',
                    'telefono': '3331234567',
                    'qualifica': 'nazionale',
                    'attivo': True,
                    'note': 'Arbitro esperto'
                },
                'statistiche': {
                    'partite_totali': 15,
                    'partite_primo': 10,
                    'partite_secondo': 5,
                    'partite_altri_ruoli': 0,
                    'partite_con_tutor': 8,
                    'tutor_assegnati': [
                        {
                            'id': 1,
                            'nome': 'Giuseppe',
                            'cognome': 'Verdi',
                            'qualifica': 'nazionale',
                            'partite': 5,
                            'prima_partita': '10/01/2023',
                            'ultima_partita': '15/04/2023',
                            'note': 'Ottimo lavoro'
                        },
                        {
                            'id': 2,
                            'nome': 'Luigi',
                            'cognome': 'Bianchi',
                            'qualifica': 'regionale',
                            'partite': 3,
                            'prima_partita': '05/03/2023',
                            'ultima_partita': '22/05/2023',
                            'note': 'Da migliorare la gestione del gioco'
                        }
                    ],
                    'partite': [
                        {
                            'id': 1,
                            'data_partita': '22/05/2023',
                            'campionato_nome': 'Serie A',
                            'squadra_casa': 'Squadra A',
                            'squadra_trasferta': 'Squadra B',
                            'ruolo': 'primo',
                            'stato': 'completata',
                            'tutor': {
                                'nome_completo': 'Bianchi Luigi',
                                'note': 'Da migliorare la gestione del gioco'
                            }
                        },
                        {
                            'id': 2,
                            'data_partita': '15/04/2023',
                            'campionato_nome': 'Serie A',
                            'squadra_casa': 'Squadra C',
                            'squadra_trasferta': 'Squadra D',
                            'ruolo': 'primo',
                            'stato': 'completata',
                            'tutor': {
                                'nome_completo': 'Verdi Giuseppe',
                                'note': 'Ottimo lavoro'
                            }
                        }
                    ]
                },
                'categorie_labels': ['Seniores', 'Under 18', 'Under 16'],
                'categorie_data': [8, 5, 2],
                'mesi_labels': ['01/2023', '02/2023', '03/2023', '04/2023', '05/2023'],
                'mesi_data': [2, 3, 4, 3, 3]
            }
    except Exception as e:
        print(f"Errore nel caricamento delle statistiche dell'arbitro: {e}")
        return None