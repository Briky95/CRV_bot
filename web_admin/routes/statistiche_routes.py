#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required

from web_admin.app import app
from modules.config import CATEGORIE
from modules.campionati_manager import carica_stagioni, get_stagione_attiva
from modules.statistiche_manager import carica_statistiche_arbitri, carica_statistiche_arbitro

@app.route('/statistiche/arbitri')
@login_required
def statistiche_arbitri():
    """Mostra la pagina delle statistiche degli arbitri."""
    try:
        # Ottieni i parametri di filtro
        stagione_id = request.args.get('stagione_id', type=int)
        categoria = request.args.get('categoria')
        
        # Carica le stagioni per il filtro
        stagioni = carica_stagioni()
        
        # Se non è specificata una stagione, usa quella attiva
        if not stagione_id and stagioni:
            stagione_attiva = get_stagione_attiva()
            if stagione_attiva:
                stagione_id = stagione_attiva.get('id')
        
        # Carica le statistiche
        statistiche = carica_statistiche_arbitri(stagione_id, categoria)
        
        return render_template('statistiche_arbitri.html',
                              stagioni=stagioni,
                              stagione_id=stagione_id,
                              categorie=CATEGORIE,
                              categoria=categoria,
                              statistiche_arbitri=statistiche['statistiche_arbitri'],
                              statistiche_generali=statistiche['statistiche_generali'],
                              categorie_labels=statistiche['categorie_labels'],
                              categorie_data=statistiche['categorie_data'],
                              ruoli_labels=statistiche['ruoli_labels'],
                              ruoli_data=statistiche['ruoli_data'])
    except Exception as e:
        app.logger.error(f"Errore nella pagina delle statistiche degli arbitri: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('arbitri'))

@app.route('/statistiche/arbitri/<int:arbitro_id>')
@login_required
def dettaglio_statistiche_arbitro(arbitro_id):
    """Mostra la pagina delle statistiche dettagliate di un arbitro."""
    try:
        # Ottieni i parametri di filtro
        stagione_id = request.args.get('stagione_id', type=int)
        
        # Carica le stagioni per il filtro
        stagioni = carica_stagioni()
        
        # Se non è specificata una stagione, usa quella attiva
        if not stagione_id and stagioni:
            stagione_attiva = get_stagione_attiva()
            if stagione_attiva:
                stagione_id = stagione_attiva.get('id')
        
        # Carica le statistiche dell'arbitro
        statistiche = carica_statistiche_arbitro(arbitro_id, stagione_id)
        
        if not statistiche:
            flash("Arbitro non trovato!", "danger")
            return redirect(url_for('statistiche_arbitri'))
        
        return render_template('dettaglio_statistiche_arbitro.html',
                              arbitro=statistiche['arbitro'],
                              statistiche=statistiche['statistiche'],
                              categorie_labels=statistiche['categorie_labels'],
                              categorie_data=statistiche['categorie_data'],
                              mesi_labels=statistiche['mesi_labels'],
                              mesi_data=statistiche['mesi_data'])
    except Exception as e:
        app.logger.error(f"Errore nella pagina delle statistiche dell'arbitro: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('statistiche_arbitri'))