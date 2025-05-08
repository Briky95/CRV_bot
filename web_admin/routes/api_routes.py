#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import jsonify, request
from flask_login import login_required

from web_admin.app import app
from modules.campionati_manager import carica_arbitri, get_partita
from modules.tutor_manager import carica_tutor_arbitrali
from modules.disponibilita_manager import (
    verifica_impegni_arbitro, verifica_impegni_tutor,
    formatta_impegni_arbitro, formatta_impegni_tutor
)

@app.route('/api/arbitri/search')
@login_required
def api_search_arbitri():
    """API per la ricerca di arbitri."""
    try:
        # Ottieni il termine di ricerca
        query = request.args.get('q', '').lower()
        
        # Carica tutti gli arbitri
        arbitri = carica_arbitri()
        
        # Filtra gli arbitri in base al termine di ricerca
        if query:
            risultati = []
            for arbitro in arbitri:
                nome_completo = f"{arbitro.get('cognome', '')} {arbitro.get('nome', '')}".lower()
                if query in nome_completo:
                    risultati.append({
                        'id': arbitro.get('id'),
                        'text': f"{arbitro.get('cognome', '')} {arbitro.get('nome', '')}",
                        'qualifica': arbitro.get('qualifica', ''),
                        'attivo': arbitro.get('attivo', True)
                    })
        else:
            # Se non c'è un termine di ricerca, restituisci tutti gli arbitri attivi
            risultati = [
                {
                    'id': arbitro.get('id'),
                    'text': f"{arbitro.get('cognome', '')} {arbitro.get('nome', '')}",
                    'qualifica': arbitro.get('qualifica', ''),
                    'attivo': arbitro.get('attivo', True)
                }
                for arbitro in arbitri if arbitro.get('attivo', True)
            ]
        
        # Ordina i risultati per cognome
        risultati.sort(key=lambda x: x['text'])
        
        return jsonify({
            'results': risultati
        })
    except Exception as e:
        app.logger.error(f"Errore nella ricerca degli arbitri: {e}")
        return jsonify({
            'error': str(e),
            'results': []
        }), 500

@app.route('/api/tutor/search')
@login_required
def api_search_tutor():
    """API per la ricerca di tutor arbitrali."""
    try:
        # Ottieni il termine di ricerca
        query = request.args.get('q', '').lower()
        
        # Carica tutti i tutor
        tutor = carica_tutor_arbitrali()
        
        # Filtra i tutor in base al termine di ricerca
        if query:
            risultati = []
            for t in tutor:
                nome_completo = f"{t.get('cognome', '')} {t.get('nome', '')}".lower()
                if query in nome_completo:
                    risultati.append({
                        'id': t.get('id'),
                        'text': f"{t.get('cognome', '')} {t.get('nome', '')}",
                        'qualifica': t.get('qualifica', ''),
                        'attivo': t.get('attivo', True)
                    })
        else:
            # Se non c'è un termine di ricerca, restituisci tutti i tutor attivi
            risultati = [
                {
                    'id': t.get('id'),
                    'text': f"{t.get('cognome', '')} {t.get('nome', '')}",
                    'qualifica': t.get('qualifica', ''),
                    'attivo': t.get('attivo', True)
                }
                for t in tutor if t.get('attivo', True)
            ]
        
        # Ordina i risultati per cognome
        risultati.sort(key=lambda x: x['text'])
        
        return jsonify({
            'results': risultati
        })
    except Exception as e:
        app.logger.error(f"Errore nella ricerca dei tutor: {e}")
        return jsonify({
            'error': str(e),
            'results': []
        }), 500
        
@app.route('/api/arbitri/verifica-disponibilita')
@login_required
def api_verifica_disponibilita_arbitro():
    """API per verificare la disponibilità di un arbitro in una data."""
    try:
        # Ottieni i parametri
        arbitro_id = request.args.get('arbitro_id', type=int)
        data_partita = request.args.get('data_partita')
        partita_id = request.args.get('partita_id', type=int)
        
        if not arbitro_id or not data_partita:
            return jsonify({
                'error': 'Parametri mancanti',
                'disponibile': True,
                'impegni_html': ''
            }), 400
        
        # Verifica gli impegni dell'arbitro
        impegni = verifica_impegni_arbitro(arbitro_id, data_partita, partita_id)
        
        # Formatta gli impegni in HTML
        impegni_html = formatta_impegni_arbitro(impegni)
        
        return jsonify({
            'disponibile': len(impegni) == 0,
            'impegni': impegni,
            'impegni_html': impegni_html
        })
    except Exception as e:
        app.logger.error(f"Errore nella verifica della disponibilità dell'arbitro: {e}")
        return jsonify({
            'error': str(e),
            'disponibile': True,
            'impegni_html': ''
        }), 500
        
@app.route('/api/tutor/verifica-disponibilita')
@login_required
def api_verifica_disponibilita_tutor():
    """API per verificare la disponibilità di un tutor in una data."""
    try:
        # Ottieni i parametri
        tutor_id = request.args.get('tutor_id', type=int)
        data_partita = request.args.get('data_partita')
        partita_id = request.args.get('partita_id', type=int)
        
        if not tutor_id or not data_partita:
            return jsonify({
                'error': 'Parametri mancanti',
                'disponibile': True,
                'impegni_html': ''
            }), 400
        
        # Verifica gli impegni del tutor
        impegni = verifica_impegni_tutor(tutor_id, data_partita, partita_id)
        
        # Formatta gli impegni in HTML
        impegni_html = formatta_impegni_tutor(impegni)
        
        return jsonify({
            'disponibile': len(impegni) == 0,
            'impegni': impegni,
            'impegni_html': impegni_html
        })
    except Exception as e:
        app.logger.error(f"Errore nella verifica della disponibilità del tutor: {e}")
        return jsonify({
            'error': str(e),
            'disponibile': True,
            'impegni_html': ''
        }), 500