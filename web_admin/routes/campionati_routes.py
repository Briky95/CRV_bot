#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from datetime import datetime

from web_admin.app import app
from modules.config import CATEGORIE
from modules.campionati_manager import (
    carica_stagioni, get_stagione_attiva, crea_stagione, aggiorna_stagione, elimina_stagione,
    carica_campionati, get_campionato, crea_campionato, aggiorna_campionato, elimina_campionato,
    carica_squadre_campionato, aggiungi_squadra_campionato, rimuovi_squadra_campionato,
    carica_arbitri, get_arbitro, crea_arbitro, aggiorna_arbitro, elimina_arbitro,
    carica_partite_campionato, get_partita, crea_partita, aggiorna_partita, elimina_partita,
    carica_designazioni_partita, aggiungi_designazione, rimuovi_designazione,
    carica_classifica_campionato, ricalcola_classifica_campionato,
    get_prossime_partite, get_ultime_partite, genera_calendario_campionato,
    carica_tutor_arbitrali, get_tutor, crea_tutor, aggiorna_tutor, elimina_tutor,
    get_tutor_partita, assegna_tutor_partita, rimuovi_tutor_partita
)
from modules.db_manager import carica_squadre

# Pagina principale dei campionati
@app.route('/campionati')
@app.route('/campionati/<int:stagione_id>')
@login_required
def campionati(stagione_id=None):
    """Mostra la pagina principale dei campionati."""
    try:
        # Carica le stagioni
        stagioni = carica_stagioni()
        
        # Ottieni la stagione attiva o selezionata
        stagione_attiva = None
        if stagione_id:
            for stagione in stagioni:
                if stagione.get('id') == stagione_id:
                    stagione_attiva = stagione
                    break
        
        if not stagione_attiva:
            stagione_attiva = get_stagione_attiva()
        
        # Carica i campionati della stagione attiva
        campionati = []
        if stagione_attiva:
            campionati = carica_campionati(stagione_attiva.get('id'))
        
        # Carica le prossime partite e gli ultimi risultati
        prossime_partite = get_prossime_partite(7)  # Prossimi 7 giorni
        ultimi_risultati = get_ultime_partite(7)  # Ultimi 7 giorni
        
        # Aggiungi i nomi dei campionati alle partite
        for partita in prossime_partite:
            campionato = get_campionato(partita.get('campionato_id'))
            partita['campionato_nome'] = campionato.get('nome') if campionato else 'Sconosciuto'
            
            # Aggiungi le designazioni arbitrali
            designazioni = carica_designazioni_partita(partita.get('id'))
            arbitri = []
            for designazione in designazioni:
                arbitro = get_arbitro(designazione.get('arbitro_id'))
                if arbitro:
                    arbitri.append({
                        'nome_completo': f"{arbitro.get('cognome')} {arbitro.get('nome')}",
                        'ruolo': designazione.get('ruolo')
                    })
            partita['arbitri'] = arbitri
            
            # Aggiungi il tutor arbitrale
            tutor_partita = get_tutor_partita(partita.get('id'))
            if tutor_partita:
                tutor = get_tutor(tutor_partita.get('tutor_id'))
                if tutor:
                    partita['tutor'] = {
                        'nome_completo': f"{tutor.get('cognome')} {tutor.get('nome')}",
                        'note': tutor_partita.get('note')
                    }
        
        for partita in ultimi_risultati:
            campionato = get_campionato(partita.get('campionato_id'))
            partita['campionato_nome'] = campionato.get('nome') if campionato else 'Sconosciuto'
        
        return render_template('campionati.html',
                              stagioni=stagioni,
                              stagione_attiva=stagione_attiva,
                              campionati=campionati,
                              prossime_partite=prossime_partite,
                              ultimi_risultati=ultimi_risultati)
    except Exception as e:
        app.logger.error(f"Errore nella pagina dei campionati: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('dashboard'))

# Gestione delle stagioni
@app.route('/stagioni/nuova')
@login_required
def nuova_stagione():
    """Mostra il form per creare una nuova stagione."""
    try:
        return render_template('stagione_form.html', stagione=None)
    except Exception as e:
        app.logger.error(f"Errore nella pagina nuova stagione: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

@app.route('/stagioni/modifica/<int:stagione_id>')
@login_required
def modifica_stagione(stagione_id):
    """Mostra il form per modificare una stagione esistente."""
    try:
        # Carica le stagioni
        stagioni = carica_stagioni()
        
        # Trova la stagione
        stagione = None
        for s in stagioni:
            if s.get('id') == stagione_id:
                stagione = s
                break
        
        if not stagione:
            flash("Stagione non trovata!", "danger")
            return redirect(url_for('campionati'))
        
        return render_template('stagione_form.html', stagione=stagione)
    except Exception as e:
        app.logger.error(f"Errore nella pagina modifica stagione: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

@app.route('/stagioni/salva', methods=['POST'])
@app.route('/stagioni/salva/<int:stagione_id>', methods=['POST'])
@login_required
def salva_stagione(stagione_id=None):
    """Salva una stagione nuova o esistente."""
    try:
        # Ottieni i dati dal form
        nome = request.form.get('nome')
        data_inizio = request.form.get('data_inizio')
        data_fine = request.form.get('data_fine')
        attiva = 'attiva' in request.form
        
        if stagione_id:
            # Aggiorna la stagione esistente
            if aggiorna_stagione(stagione_id, nome, data_inizio, data_fine, attiva):
                flash("Stagione aggiornata con successo!", "success")
            else:
                flash("Si è verificato un errore durante l'aggiornamento della stagione.", "danger")
        else:
            # Crea una nuova stagione
            stagione = crea_stagione(nome, data_inizio, data_fine, attiva)
            if stagione:
                flash("Stagione creata con successo!", "success")
            else:
                flash("Si è verificato un errore durante la creazione della stagione.", "danger")
        
        return redirect(url_for('campionati'))
    except Exception as e:
        app.logger.error(f"Errore nel salvataggio della stagione: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

@app.route('/stagioni/elimina/<int:stagione_id>')
@login_required
def elimina_stagione_route(stagione_id):
    """Elimina una stagione."""
    try:
        if elimina_stagione(stagione_id):
            flash("Stagione eliminata con successo!", "success")
        else:
            flash("Si è verificato un errore durante l'eliminazione della stagione.", "danger")
        
        return redirect(url_for('campionati'))
    except Exception as e:
        app.logger.error(f"Errore nell'eliminazione della stagione: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

# Gestione dei campionati
@app.route('/campionati/nuovo')
@login_required
def nuovo_campionato():
    """Mostra il form per creare un nuovo campionato."""
    try:
        # Carica le stagioni
        stagioni = carica_stagioni()
        stagione_attiva = get_stagione_attiva()
        
        return render_template('campionato_form.html',
                              campionato=None,
                              stagioni=stagioni,
                              stagione_attiva=stagione_attiva,
                              categorie=CATEGORIE)
    except Exception as e:
        app.logger.error(f"Errore nella pagina nuovo campionato: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

@app.route('/campionati/modifica/<int:campionato_id>')
@login_required
def modifica_campionato(campionato_id):
    """Mostra il form per modificare un campionato esistente."""
    try:
        # Carica il campionato
        campionato = get_campionato(campionato_id)
        
        if not campionato:
            flash("Campionato non trovato!", "danger")
            return redirect(url_for('campionati'))
        
        return render_template('campionato_form.html',
                              campionato=campionato,
                              categorie=CATEGORIE)
    except Exception as e:
        app.logger.error(f"Errore nella pagina modifica campionato: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

@app.route('/campionati/salva', methods=['POST'])
@app.route('/campionati/salva/<int:campionato_id>', methods=['POST'])
@login_required
def salva_campionato(campionato_id=None):
    """Salva un campionato nuovo o esistente."""
    try:
        # Ottieni i dati dal form
        nome = request.form.get('nome')
        categoria = request.form.get('categoria')
        genere = request.form.get('genere')
        formato = request.form.get('formato')
        descrizione = request.form.get('descrizione', '')
        
        if campionato_id:
            # Aggiorna il campionato esistente
            if aggiorna_campionato(campionato_id, nome, categoria, genere, formato, descrizione):
                flash("Campionato aggiornato con successo!", "success")
            else:
                flash("Si è verificato un errore durante l'aggiornamento del campionato.", "danger")
        else:
            # Ottieni la stagione
            stagione_id = request.form.get('stagione_id')
            
            # Crea un nuovo campionato
            campionato = crea_campionato(int(stagione_id), nome, categoria, genere, formato, descrizione)
            if campionato:
                flash("Campionato creato con successo!", "success")
            else:
                flash("Si è verificato un errore durante la creazione del campionato.", "danger")
        
        return redirect(url_for('campionati'))
    except Exception as e:
        app.logger.error(f"Errore nel salvataggio del campionato: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

@app.route('/campionati/elimina/<int:campionato_id>')
@login_required
def elimina_campionato_route(campionato_id):
    """Elimina un campionato."""
    try:
        if elimina_campionato(campionato_id):
            flash("Campionato eliminato con successo!", "success")
        else:
            flash("Si è verificato un errore durante l'eliminazione del campionato.", "danger")
        
        return redirect(url_for('campionati'))
    except Exception as e:
        app.logger.error(f"Errore nell'eliminazione del campionato: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

# Gestione di un campionato specifico
@app.route('/campionati/gestione/<int:campionato_id>')
@login_required
def gestione_campionato(campionato_id):
    """Mostra la pagina di gestione di un campionato."""
    try:
        # Carica il campionato
        campionato = get_campionato(campionato_id)
        
        if not campionato:
            flash("Campionato non trovato!", "danger")
            return redirect(url_for('campionati'))
        
        # Carica la stagione
        stagioni = carica_stagioni()
        stagione = None
        for s in stagioni:
            if s.get('id') == campionato.get('stagione_id'):
                stagione = s
                break
        
        # Carica le squadre del campionato
        squadre_campionato = carica_squadre_campionato(campionato_id)
        
        # Carica tutte le squadre
        tutte_squadre = carica_squadre()
        
        # Carica le partite del campionato
        partite = carica_partite_campionato(campionato_id)
        
        # Aggiungi le designazioni arbitrali alle partite
        for partita in partite:
            designazioni = carica_designazioni_partita(partita.get('id'))
            arbitri = []
            for designazione in designazioni:
                arbitro = get_arbitro(designazione.get('arbitro_id'))
                if arbitro:
                    arbitri.append({
                        'nome_completo': f"{arbitro.get('cognome')} {arbitro.get('nome')}",
                        'ruolo': designazione.get('ruolo')
                    })
            partita['arbitri'] = arbitri
            
            # Aggiungi il tutor arbitrale
            tutor_partita = get_tutor_partita(partita.get('id'))
            if tutor_partita:
                tutor = get_tutor(tutor_partita.get('tutor_id'))
                if tutor:
                    partita['tutor'] = {
                        'nome_completo': f"{tutor.get('cognome')} {tutor.get('nome')}",
                        'note': tutor_partita.get('note')
                    }
        
        # Carica la classifica
        classifica_raw = carica_classifica_campionato(campionato_id)
        
        # Ordina la classifica per punti (decrescente)
        classifica_raw.sort(key=lambda x: x.get('punti', 0), reverse=True)
        
        # Aggiungi la posizione
        classifica = [(i+1, riga) for i, riga in enumerate(classifica_raw)]
        
        return render_template('gestione_campionato.html',
                              campionato=campionato,
                              stagione=stagione,
                              squadre_campionato=squadre_campionato,
                              tutte_squadre=tutte_squadre,
                              partite=partite,
                              classifica=classifica)
    except Exception as e:
        app.logger.error(f"Errore nella pagina gestione campionato: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

@app.route('/campionati/<int:campionato_id>/aggiungi_squadra', methods=['POST'])
@login_required
def aggiungi_squadra_campionato_route(campionato_id):
    """Aggiunge una squadra a un campionato."""
    try:
        # Ottieni i dati dal form
        squadra = request.form.get('squadra')
        
        if aggiungi_squadra_campionato(campionato_id, squadra):
            flash(f"Squadra '{squadra}' aggiunta con successo!", "success")
        else:
            flash(f"Si è verificato un errore durante l'aggiunta della squadra '{squadra}'.", "danger")
        
        return redirect(url_for('gestione_campionato', campionato_id=campionato_id))
    except Exception as e:
        app.logger.error(f"Errore nell'aggiunta della squadra al campionato: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('gestione_campionato', campionato_id=campionato_id))

@app.route('/campionati/<int:campionato_id>/rimuovi_squadra/<squadra>')
@login_required
def rimuovi_squadra_campionato_route(campionato_id, squadra):
    """Rimuove una squadra da un campionato."""
    try:
        if rimuovi_squadra_campionato(campionato_id, squadra):
            flash(f"Squadra '{squadra}' rimossa con successo!", "success")
        else:
            flash(f"Si è verificato un errore durante la rimozione della squadra '{squadra}'.", "danger")
        
        return redirect(url_for('gestione_campionato', campionato_id=campionato_id))
    except Exception as e:
        app.logger.error(f"Errore nella rimozione della squadra dal campionato: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('gestione_campionato', campionato_id=campionato_id))

@app.route('/campionati/<int:campionato_id>/genera_calendario')
@login_required
def genera_calendario(campionato_id):
    """Genera il calendario di un campionato."""
    try:
        # Ottieni la data di oggi
        oggi = datetime.now().strftime('%Y-%m-%d')
        
        if genera_calendario_campionato(campionato_id, oggi):
            flash("Calendario generato con successo!", "success")
        else:
            flash("Si è verificato un errore durante la generazione del calendario.", "danger")
        
        return redirect(url_for('gestione_campionato', campionato_id=campionato_id))
    except Exception as e:
        app.logger.error(f"Errore nella generazione del calendario: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('gestione_campionato', campionato_id=campionato_id))

@app.route('/campionati/<int:campionato_id>/ricalcola_classifica')
@login_required
def ricalcola_classifica(campionato_id):
    """Ricalcola la classifica di un campionato."""
    try:
        if ricalcola_classifica_campionato(campionato_id):
            flash("Classifica ricalcolata con successo!", "success")
        else:
            flash("Si è verificato un errore durante il ricalcolo della classifica.", "danger")
        
        return redirect(url_for('gestione_campionato', campionato_id=campionato_id))
    except Exception as e:
        app.logger.error(f"Errore nel ricalcolo della classifica: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('gestione_campionato', campionato_id=campionato_id))

# Gestione delle partite
@app.route('/partite/nuova/<int:campionato_id>')
@login_required
def nuova_partita(campionato_id):
    """Mostra il form per creare una nuova partita."""
    try:
        # Carica il campionato
        campionato = get_campionato(campionato_id)
        
        if not campionato:
            flash("Campionato non trovato!", "danger")
            return redirect(url_for('campionati'))
        
        # Crea una partita vuota
        partita = {
            'id': None,
            'campionato_id': campionato_id,
            'data_partita': datetime.now().strftime('%Y-%m-%d'),
            'squadra_casa': '',
            'squadra_trasferta': '',
            'stato': 'programmata'
        }
        
        # Carica le squadre del campionato
        squadre_campionato = carica_squadre_campionato(campionato_id)
        
        # Non carichiamo più tutti gli arbitri qui, verranno caricati tramite API
        
        return render_template('gestione_partita.html',
                              partita=partita,
                              squadre_campionato=squadre_campionato,
                              designazioni=[])
    except Exception as e:
        app.logger.error(f"Errore nella pagina nuova partita: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('gestione_campionato', campionato_id=campionato_id))

@app.route('/partite/gestione/<int:partita_id>')
@login_required
def gestione_partita(partita_id):
    """Mostra la pagina di gestione di una partita."""
    try:
        # Carica la partita
        partita = get_partita(partita_id)
        
        if not partita:
            flash("Partita non trovata!", "danger")
            return redirect(url_for('campionati'))
        
        # Carica le squadre del campionato
        squadre_campionato = carica_squadre_campionato(partita.get('campionato_id'))
        
        # Non carichiamo più tutti gli arbitri qui, verranno caricati tramite API
        
        # Carica le designazioni arbitrali
        designazioni_raw = carica_designazioni_partita(partita_id)
        
        # Aggiungi i dati degli arbitri alle designazioni
        designazioni = []
        for designazione in designazioni_raw:
            arbitro = get_arbitro(designazione.get('arbitro_id'))
            if arbitro:
                designazione['arbitro'] = arbitro
                designazioni.append(designazione)
        
        # Non carichiamo più tutti i tutor qui, verranno caricati tramite API
        
        # Carica il tutor assegnato alla partita
        tutor_partita = get_tutor_partita(partita_id)
        tutor_assegnato = None
        
        if tutor_partita:
            tutor = get_tutor(tutor_partita.get('tutor_id'))
            if tutor:
                tutor_partita['tutor'] = tutor
                tutor_assegnato = tutor_partita
        
        return render_template('gestione_partita.html',
                              partita=partita,
                              squadre_campionato=squadre_campionato,
                              designazioni=designazioni,
                              tutor_assegnato=tutor_assegnato)
    except Exception as e:
        app.logger.error(f"Errore nella pagina gestione partita: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

@app.route('/partite/aggiorna/<int:partita_id>', methods=['POST'])
@login_required
def aggiorna_partita_route(partita_id):
    """Aggiorna una partita."""
    try:
        # Carica la partita esistente
        partita_esistente = get_partita(partita_id)
        
        if not partita_esistente:
            flash("Partita non trovata!", "danger")
            return redirect(url_for('campionati'))
        
        # Ottieni i dati dal form
        data_partita = request.form.get('data_partita')
        squadra_casa = request.form.get('squadra_casa')
        squadra_trasferta = request.form.get('squadra_trasferta')
        giornata = request.form.get('giornata')
        ora = request.form.get('ora')
        luogo = request.form.get('luogo', '')
        note = request.form.get('note', '')
        stato = request.form.get('stato')
        punteggio_casa = request.form.get('punteggio_casa')
        punteggio_trasferta = request.form.get('punteggio_trasferta')
        mete_casa = request.form.get('mete_casa')
        mete_trasferta = request.form.get('mete_trasferta')
        
        # Converti i valori numerici
        giornata = int(giornata) if giornata else None
        punteggio_casa = int(punteggio_casa) if punteggio_casa else None
        punteggio_trasferta = int(punteggio_trasferta) if punteggio_trasferta else None
        mete_casa = int(mete_casa) if mete_casa else None
        mete_trasferta = int(mete_trasferta) if mete_trasferta else None
        
        # Aggiorna la partita
        if aggiorna_partita(
            partita_id, data_partita, squadra_casa, squadra_trasferta,
            giornata, ora, luogo, note, stato, punteggio_casa,
            punteggio_trasferta, mete_casa, mete_trasferta
        ):
            flash("Partita aggiornata con successo!", "success")
        else:
            flash("Si è verificato un errore durante l'aggiornamento della partita.", "danger")
        
        return redirect(url_for('gestione_partita', partita_id=partita_id))
    except Exception as e:
        app.logger.error(f"Errore nell'aggiornamento della partita: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('gestione_partita', partita_id=partita_id))

@app.route('/partite/elimina/<int:partita_id>')
@login_required
def elimina_partita_route(partita_id):
    """Elimina una partita."""
    try:
        # Carica la partita
        partita = get_partita(partita_id)
        
        if not partita:
            flash("Partita non trovata!", "danger")
            return redirect(url_for('campionati'))
        
        campionato_id = partita.get('campionato_id')
        
        if elimina_partita(partita_id):
            flash("Partita eliminata con successo!", "success")
        else:
            flash("Si è verificato un errore durante l'eliminazione della partita.", "danger")
        
        return redirect(url_for('gestione_campionato', campionato_id=campionato_id))
    except Exception as e:
        app.logger.error(f"Errore nell'eliminazione della partita: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

# Gestione delle designazioni arbitrali
@app.route('/designazioni/aggiungi/<int:partita_id>', methods=['POST'])
@login_required
def aggiungi_designazione_route(partita_id):
    """Aggiunge una designazione arbitrale."""
    try:
        # Ottieni i dati dal form
        arbitro_id = int(request.form.get('arbitro_id'))
        ruolo = request.form.get('ruolo')
        confermata = 'confermata' in request.form
        note = request.form.get('note', '')
        
        if aggiungi_designazione(partita_id, arbitro_id, ruolo, confermata, note):
            flash("Designazione arbitrale aggiunta con successo!", "success")
        else:
            flash("Si è verificato un errore durante l'aggiunta della designazione arbitrale.", "danger")
        
        return redirect(url_for('gestione_partita', partita_id=partita_id))
    except Exception as e:
        app.logger.error(f"Errore nell'aggiunta della designazione arbitrale: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('gestione_partita', partita_id=partita_id))

@app.route('/designazioni/rimuovi/<int:designazione_id>/<int:partita_id>')
@login_required
def rimuovi_designazione_route(designazione_id, partita_id):
    """Rimuove una designazione arbitrale."""
    try:
        if rimuovi_designazione(designazione_id):
            flash("Designazione arbitrale rimossa con successo!", "success")
        else:
            flash("Si è verificato un errore durante la rimozione della designazione arbitrale.", "danger")
        
        return redirect(url_for('gestione_partita', partita_id=partita_id))
    except Exception as e:
        app.logger.error(f"Errore nella rimozione della designazione arbitrale: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('gestione_partita', partita_id=partita_id))

# Gestione dei tutor arbitrali
@app.route('/tutor_arbitrali')
@login_required
def tutor_arbitrali():
    """Mostra la pagina di gestione dei tutor arbitrali."""
    try:
        # Carica i tutor
        tutors_list = carica_tutor_arbitrali()
        
        return render_template('tutor_arbitrali.html', tutors=tutors_list)
    except Exception as e:
        app.logger.error(f"Errore nella pagina dei tutor arbitrali: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

@app.route('/tutor/nuovo')
@login_required
def nuovo_tutor():
    """Mostra il form per creare un nuovo tutor."""
    try:
        return render_template('tutor_form.html', tutor=None)
    except Exception as e:
        app.logger.error(f"Errore nella pagina nuovo tutor: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('tutor_arbitrali'))

@app.route('/tutor/modifica/<int:tutor_id>')
@login_required
def modifica_tutor(tutor_id):
    """Mostra il form per modificare un tutor esistente."""
    try:
        # Carica il tutor
        tutor = get_tutor(tutor_id)
        
        if not tutor:
            flash("Tutor non trovato!", "danger")
            return redirect(url_for('tutor_arbitrali'))
        
        return render_template('tutor_form.html', tutor=tutor)
    except Exception as e:
        app.logger.error(f"Errore nella pagina modifica tutor: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('tutor_arbitrali'))

@app.route('/tutor/salva', methods=['POST'])
@app.route('/tutor/salva/<int:tutor_id>', methods=['POST'])
@login_required
def salva_tutor(tutor_id=None):
    """Salva un tutor nuovo o esistente."""
    try:
        # Ottieni i dati dal form
        nome = request.form.get('nome')
        cognome = request.form.get('cognome')
        email = request.form.get('email', '')
        telefono = request.form.get('telefono', '')
        qualifica = request.form.get('qualifica', '')
        attivo = 'attivo' in request.form
        note = request.form.get('note', '')
        
        if tutor_id:
            # Aggiorna il tutor esistente
            if aggiorna_tutor(tutor_id, nome, cognome, email, telefono, qualifica, attivo, note):
                flash("Tutor aggiornato con successo!", "success")
            else:
                flash("Si è verificato un errore durante l'aggiornamento del tutor.", "danger")
        else:
            # Crea un nuovo tutor
            tutor = crea_tutor(nome, cognome, email, telefono, qualifica, attivo, note)
            if tutor:
                flash("Tutor creato con successo!", "success")
            else:
                flash("Si è verificato un errore durante la creazione del tutor.", "danger")
        
        return redirect(url_for('tutor_arbitrali'))
    except Exception as e:
        app.logger.error(f"Errore nel salvataggio del tutor: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('tutor_arbitrali'))

@app.route('/tutor/elimina/<int:tutor_id>')
@login_required
def elimina_tutor(tutor_id):
    """Elimina un tutor."""
    try:
        if elimina_tutor(tutor_id):
            flash("Tutor eliminato con successo!", "success")
        else:
            flash("Si è verificato un errore durante l'eliminazione del tutor.", "danger")
        
        return redirect(url_for('tutor_arbitrali'))
    except Exception as e:
        app.logger.error(f"Errore nell'eliminazione del tutor: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('tutor_arbitrali'))

@app.route('/partite/<int:partita_id>/assegna_tutor', methods=['POST'])
@login_required
def assegna_tutor(partita_id):
    """Assegna un tutor a una partita."""
    try:
        # Ottieni i dati dal form
        tutor_id = int(request.form.get('tutor_id'))
        note = request.form.get('note', '')
        
        # Verifica se esiste già un tutor per questa partita
        tutor_esistente = get_tutor_partita(partita_id)
        if tutor_esistente:
            # Rimuovi il tutor esistente
            rimuovi_tutor_partita(tutor_esistente.get('id'))
        
        # Assegna il nuovo tutor
        if assegna_tutor_partita(partita_id, tutor_id, note):
            flash("Tutor assegnato con successo!", "success")
        else:
            flash("Si è verificato un errore durante l'assegnazione del tutor.", "danger")
        
        return redirect(url_for('gestione_partita', partita_id=partita_id))
    except Exception as e:
        app.logger.error(f"Errore nell'assegnazione del tutor: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('gestione_partita', partita_id=partita_id))

@app.route('/partite/<int:partita_id>/rimuovi_tutor/<int:tutor_partita_id>')
@login_required
def rimuovi_tutor(partita_id, tutor_partita_id):
    """Rimuove un tutor da una partita."""
    try:
        if rimuovi_tutor_partita(tutor_partita_id):
            flash("Tutor rimosso con successo!", "success")
        else:
            flash("Si è verificato un errore durante la rimozione del tutor.", "danger")
        
        return redirect(url_for('gestione_partita', partita_id=partita_id))
    except Exception as e:
        app.logger.error(f"Errore nella rimozione del tutor: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('gestione_partita', partita_id=partita_id))

# Gestione degli arbitri
@app.route('/arbitri')
@login_required
def arbitri():
    """Mostra la pagina di gestione degli arbitri."""
    try:
        # Carica gli arbitri
        arbitri_list = carica_arbitri()
        
        return render_template('arbitri.html', arbitri=arbitri_list)
    except Exception as e:
        app.logger.error(f"Errore nella pagina degli arbitri: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('campionati'))

@app.route('/arbitri/nuovo')
@login_required
def nuovo_arbitro():
    """Mostra il form per creare un nuovo arbitro."""
    try:
        return render_template('arbitro_form.html', arbitro=None)
    except Exception as e:
        app.logger.error(f"Errore nella pagina nuovo arbitro: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('arbitri'))

@app.route('/arbitri/modifica/<int:arbitro_id>')
@login_required
def modifica_arbitro(arbitro_id):
    """Mostra il form per modificare un arbitro esistente."""
    try:
        # Carica l'arbitro
        arbitro = get_arbitro(arbitro_id)
        
        if not arbitro:
            flash("Arbitro non trovato!", "danger")
            return redirect(url_for('arbitri'))
        
        return render_template('arbitro_form.html', arbitro=arbitro)
    except Exception as e:
        app.logger.error(f"Errore nella pagina modifica arbitro: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('arbitri'))

@app.route('/arbitri/salva', methods=['POST'])
@app.route('/arbitri/salva/<int:arbitro_id>', methods=['POST'])
@login_required
def salva_arbitro(arbitro_id=None):
    """Salva un arbitro nuovo o esistente."""
    try:
        # Ottieni i dati dal form
        nome = request.form.get('nome')
        cognome = request.form.get('cognome')
        email = request.form.get('email', '')
        telefono = request.form.get('telefono', '')
        livello = request.form.get('livello', '')
        attivo = 'attivo' in request.form
        note = request.form.get('note', '')
        
        if arbitro_id:
            # Aggiorna l'arbitro esistente
            if aggiorna_arbitro(arbitro_id, nome, cognome, email, telefono, livello, attivo, note):
                flash("Arbitro aggiornato con successo!", "success")
            else:
                flash("Si è verificato un errore durante l'aggiornamento dell'arbitro.", "danger")
        else:
            # Crea un nuovo arbitro
            arbitro = crea_arbitro(nome, cognome, email, telefono, livello, attivo, note)
            if arbitro:
                flash("Arbitro creato con successo!", "success")
            else:
                flash("Si è verificato un errore durante la creazione dell'arbitro.", "danger")
        
        return redirect(url_for('arbitri'))
    except Exception as e:
        app.logger.error(f"Errore nel salvataggio dell'arbitro: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('arbitri'))

@app.route('/arbitri/elimina/<int:arbitro_id>')
@login_required
def elimina_arbitro_route(arbitro_id):
    """Elimina un arbitro."""
    try:
        if elimina_arbitro(arbitro_id):
            flash("Arbitro eliminato con successo!", "success")
        else:
            flash("Si è verificato un errore durante l'eliminazione dell'arbitro.", "danger")
        
        return redirect(url_for('arbitri'))
    except Exception as e:
        app.logger.error(f"Errore nell'eliminazione dell'arbitro: {e}")
        flash(f"Si è verificato un errore: {e}", "danger")
        return redirect(url_for('arbitri'))