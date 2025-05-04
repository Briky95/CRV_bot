#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sys

# Funzioni personalizzate per l'hashing delle password
def custom_generate_password_hash(password):
    """Genera un hash sicuro della password usando SHA-256"""
    salt = secrets.token_hex(8)
    pwdhash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"sha256${salt}${pwdhash}"

def custom_check_password_hash(pwhash, password):
    """Verifica se la password corrisponde all'hash"""
    if not pwhash or not password:
        return False
    try:
        algorithm, salt, hashval = pwhash.split('$', 2)
        if algorithm != 'sha256':
            # Fallback al metodo di Werkzeug se l'algoritmo è diverso
            return check_password_hash(pwhash, password)
        return hashlib.sha256((password + salt).encode()).hexdigest() == hashval
    except (ValueError, TypeError):
        # In caso di errore, ritorna False
        return False

# Aggiungi la directory principale al path per importare i moduli del bot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importa le funzioni di utilità dai moduli
from modules.config import CHANNEL_ID
try:
    # Prova a importare il token dell'interfaccia web
    from modules.config_web import TOKEN_WEB, CHANNEL_ID as CHANNEL_ID_WEB
except ImportError:
    # Se non esiste, usa il token del bot principale
    TOKEN_WEB = None
    CHANNEL_ID_WEB = CHANNEL_ID

from modules.export_manager import genera_excel_riepilogo_weekend, genera_pdf_riepilogo_weekend
from modules.db_manager import carica_utenti, salva_utenti, carica_risultati, salva_risultati, carica_squadre, salva_squadre, carica_admin_users, salva_admin_users, is_supabase_configured, migra_dati_a_supabase
from modules.data_manager import ottieni_risultati_weekend
from modules.quiz_manager import carica_quiz, salva_quiz, carica_statistiche_quiz, invia_quiz_al_canale
from modules.quiz_generator import load_pending_quizzes, save_pending_quizzes, generate_multiple_quizzes, approve_pending_quiz, reject_pending_quiz
import asyncio
import telegram

# Importa pandas
import pandas as pd

# Funzione per migrare gli utenti dal vecchio formato al nuovo
def migra_utenti_vecchio_formato():
    utenti_data = carica_utenti()
    modificato = False
    
    # Migra gli utenti autorizzati
    for i, utente in enumerate(utenti_data["autorizzati"]):
        if not isinstance(utente, dict):
            # Converti il vecchio formato (solo ID) in un dizionario
            utenti_data["autorizzati"][i] = {
                "id": utente,
                "nome": f"Utente {utente}",
                "username": None,
                "data_registrazione": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "ruolo": "utente"  # Ruolo predefinito
            }
            modificato = True
        elif isinstance(utente, dict) and "ruolo" not in utente:
            # Aggiungi il campo ruolo se non esiste
            utenti_data["autorizzati"][i]["ruolo"] = "utente"
            modificato = True
    
    # Migra gli utenti in attesa
    for i, utente in enumerate(utenti_data["in_attesa"]):
        if not isinstance(utente, dict):
            # Converti il vecchio formato (solo ID) in un dizionario
            utenti_data["in_attesa"][i] = {
                "id": utente,
                "nome": f"Utente {utente}",
                "username": None,
                "data_registrazione": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "ruolo": "utente"  # Ruolo predefinito
            }
            modificato = True
        elif isinstance(utente, dict) and "ruolo" not in utente:
            # Aggiungi il campo ruolo se non esiste
            utenti_data["in_attesa"][i]["ruolo"] = "utente"
            modificato = True
    
    # Salva le modifiche se necessario
    if modificato:
        salva_utenti(utenti_data)
        print("Migrazione utenti completata: vecchio formato -> nuovo formato")
    
    return utenti_data

# Inizializza l'app Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Carica il token del bot Telegram
try:
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'token.txt'), 'r') as f:
        BOT_TOKEN = f.read().strip()
except FileNotFoundError:
    BOT_TOKEN = os.environ.get('BOT_TOKEN', '')

# Inizializza Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Percorsi dei file dati
ADMIN_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'admin_users.json')
RISULTATI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'risultati.json')
UTENTI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utenti.json')

# Classe User per Flask-Login
class User(UserMixin):
    def __init__(self, id, username, is_admin=False):
        self.id = id
        self.username = username
        self.is_admin = is_admin

# Funzione per caricare gli admin dell'interfaccia web
def carica_admin_users():
    if os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []
    else:
        # Crea il file con un admin di default se non esiste
        admin_default = [{
            "id": "1",
            "username": "admin",
            "password": custom_generate_password_hash("admin123"),
            "is_admin": True
        }]
        with open(ADMIN_FILE, 'w', encoding='utf-8') as file:
            json.dump(admin_default, file, indent=2)
        return admin_default

# Funzione per salvare gli admin dell'interfaccia web
def salva_admin_users(admin_users):
    with open(ADMIN_FILE, 'w', encoding='utf-8') as file:
        json.dump(admin_users, file, indent=2, ensure_ascii=False)

# Callback per caricare l'utente
@login_manager.user_loader
def load_user(user_id):
    admin_users = carica_admin_users()
    for admin in admin_users:
        if admin['id'] == user_id:
            return User(admin['id'], admin['username'], admin['is_admin'])
    return None

# Rotte per l'autenticazione
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_users = carica_admin_users()
        for admin in admin_users:
            if admin['username'] == username and custom_check_password_hash(admin['password'], password):
                user = User(admin['id'], admin['username'], admin['is_admin'])
                login_user(user)
                flash('Login effettuato con successo!', 'success')
                return redirect(url_for('dashboard'))
        
        flash('Username o password non validi!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout effettuato con successo!', 'success')
    return redirect(url_for('login'))

# Rotta per la dashboard
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    try:
        # Carica i dati per la dashboard
        try:
            risultati = carica_risultati()
        except Exception as e:
            app.logger.error(f"Errore nel caricamento dei risultati: {e}")
            risultati = []
        
        try:
            utenti_data = carica_utenti()
        except Exception as e:
            app.logger.error(f"Errore nel caricamento degli utenti: {e}")
            utenti_data = {"autorizzati": [], "in_attesa": []}
        
        # Calcola alcune statistiche
        num_partite = len(risultati)
        num_utenti_autorizzati = len(utenti_data.get("autorizzati", []))
        num_utenti_in_attesa = len(utenti_data.get("in_attesa", []))
        
        # Carica i dati dei quiz
        try:
            quiz_data = carica_quiz()
            stats_quiz = carica_statistiche_quiz()
            pending_data = load_pending_quizzes()
            
            # Statistiche quiz
            total_quizzes = sum(len(cat.get("quiz", [])) for cat in quiz_data.get("categorie", []))
            pending_quizzes = len(pending_data.get("quiz_pending", []))
            total_participants = len(stats_quiz.get("partecipanti", {}))
            
            # Calcola il numero totale di risposte e risposte corrette
            total_responses = 0
            correct_responses = 0
            for quiz in stats_quiz.get("quiz_giornalieri", []):
                for risposta in quiz.get("risposte", []):
                    total_responses += 1
                    if risposta.get("corretta", False):
                        correct_responses += 1
            
            # Calcola la percentuale di risposte corrette
            correct_percentage = (correct_responses / total_responses * 100) if total_responses > 0 else 0
        except Exception as e:
            app.logger.error(f"Errore nel caricamento dei dati dei quiz: {e}")
            total_quizzes = 0
            pending_quizzes = 0
            total_participants = 0
            total_responses = 0
            correct_responses = 0
            correct_percentage = 0
        
        # Calcola le partite recenti (ultimi 7 giorni)
        oggi = datetime.now()
        sette_giorni_fa = oggi - timedelta(days=7)
        partite_recenti = []
        
        for risultato in risultati:
            try:
                data_partita = datetime.strptime(risultato.get('data_partita', '01/01/2000'), '%d/%m/%Y')
                if data_partita >= sette_giorni_fa:
                    partite_recenti.append(risultato)
            except (ValueError, TypeError) as e:
                app.logger.warning(f"Errore nella conversione della data: {e}")
                continue
        
        # Ordina le partite recenti per data (più recenti prima)
        try:
            partite_recenti.sort(key=lambda x: datetime.strptime(x.get('data_partita', '01/01/2000'), '%d/%m/%Y'), reverse=True)
        except Exception as e:
            app.logger.error(f"Errore nell'ordinamento delle partite: {e}")
        
        # Limita a 5 partite
        partite_recenti = partite_recenti[:5]
        
        return render_template('dashboard.html', 
                              num_partite=num_partite,
                              num_utenti_autorizzati=num_utenti_autorizzati,
                              num_utenti_in_attesa=num_utenti_in_attesa,
                              partite_recenti=partite_recenti,
                              total_quizzes=total_quizzes,
                              pending_quizzes=pending_quizzes,
                              total_participants=total_participants,
                              total_responses=total_responses,
                              correct_responses=correct_responses,
                              correct_percentage=correct_percentage)
    except Exception as e:
        app.logger.error(f"Errore nella dashboard: {e}")
        flash(f"Si è verificato un errore nel caricamento della dashboard: {str(e)}", "danger")
        # Renderizza una dashboard vuota in caso di errore
        return render_template('dashboard.html', 
                              num_partite=0,
                              num_utenti_autorizzati=0,
                              num_utenti_in_attesa=0,
                              partite_recenti=[],
                              total_quizzes=0,
                              pending_quizzes=0,
                              total_participants=0,
                              total_responses=0,
                              correct_responses=0,
                              correct_percentage=0)

# Rotta per la gestione utenti
@app.route('/users')
@login_required
def users():
    utenti_data = carica_utenti()
    
    # Converti gli utenti autorizzati nel formato corretto per il template
    utenti_autorizzati = []
    for utente in utenti_data["autorizzati"]:
        if isinstance(utente, dict):
            utenti_autorizzati.append(utente)
        else:
            # Converti il vecchio formato (solo ID) in un dizionario
            utenti_autorizzati.append({
                "id": utente,
                "nome": f"Utente {utente}",
                "username": None,
                "data_registrazione": None
            })
    
    # Converti gli utenti in attesa nel formato corretto per il template
    utenti_in_attesa = []
    for utente in utenti_data["in_attesa"]:
        if isinstance(utente, dict):
            utenti_in_attesa.append(utente)
        else:
            # Converti il vecchio formato (solo ID) in un dizionario
            utenti_in_attesa.append({
                "id": utente,
                "nome": f"Utente {utente}",
                "username": None,
                "data_registrazione": None
            })
    
    return render_template('users.html', 
                          utenti_autorizzati=utenti_autorizzati,
                          utenti_in_attesa=utenti_in_attesa)

# API per approvare un utente
@app.route('/api/approve_user/<int:user_id>', methods=['POST'])
@login_required
def approve_user(user_id):
    utenti_data = carica_utenti()
    
    # Trova l'utente in attesa
    utente_da_approvare = None
    indice_da_rimuovere = None
    
    for i, utente in enumerate(utenti_data["in_attesa"]):
        if isinstance(utente, dict) and utente.get("id") == user_id:
            utente_da_approvare = utente
            indice_da_rimuovere = i
            break
        elif not isinstance(utente, dict) and utente == user_id:
            # Vecchio formato (solo ID)
            utente_da_approvare = {
                "id": user_id,
                "nome": f"Utente {user_id}",
                "username": None,
                "data_registrazione": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }
            indice_da_rimuovere = i
            break
    
    if utente_da_approvare is not None and indice_da_rimuovere is not None:
        # Rimuovi l'utente dalla lista in attesa
        utenti_data["in_attesa"].pop(indice_da_rimuovere)
        
        # Aggiungi l'utente alla lista degli autorizzati
        utenti_data["autorizzati"].append(utente_da_approvare)
        
        # Salva le modifiche
        salva_utenti(utenti_data)
        
        return jsonify({"success": True, "message": "Utente approvato con successo"})
    
    return jsonify({"success": False, "message": "Utente non trovato"}), 404

# API per rifiutare un utente
@app.route('/api/reject_user/<int:user_id>', methods=['POST'])
@login_required
def reject_user(user_id):
    utenti_data = carica_utenti()
    
    # Cerca l'utente nella lista in attesa
    trovato = False
    for i, utente in enumerate(utenti_data["in_attesa"]):
        if (isinstance(utente, dict) and utente.get("id") == user_id) or (not isinstance(utente, dict) and utente == user_id):
            utenti_data["in_attesa"].pop(i)
            trovato = True
            break
    
    if trovato:
        # Salva le modifiche
        salva_utenti(utenti_data)
        return jsonify({"success": True, "message": "Utente rifiutato con successo"})
    else:
        return jsonify({"success": False, "message": "Utente non trovato"}), 404

# API per revocare l'autorizzazione a un utente
@app.route('/api/revoke_user/<int:user_id>', methods=['POST'])
@login_required
def revoke_user(user_id):
    utenti_data = carica_utenti()
    
    # Cerca l'utente nella lista degli autorizzati
    trovato = False
    for i, utente in enumerate(utenti_data["autorizzati"]):
        if (isinstance(utente, dict) and utente.get("id") == user_id) or (not isinstance(utente, dict) and utente == user_id):
            utenti_data["autorizzati"].pop(i)
            trovato = True
            break
    
    if trovato:
        # Salva le modifiche
        salva_utenti(utenti_data)
        return jsonify({"success": True, "message": "Autorizzazione revocata con successo"})
    else:
        return jsonify({"success": False, "message": "Utente non trovato"}), 404

# API per promuovere un utente a admin
@app.route('/api/promote_user/<int:user_id>', methods=['POST'])
@login_required
def promote_user(user_id):
    # Verifica che l'utente corrente sia un admin
    if not current_user.is_admin:
        return jsonify({"success": False, "message": "Non hai i permessi per eseguire questa operazione"}), 403
    
    utenti_data = carica_utenti()
    
    # Cerca l'utente nella lista degli autorizzati
    trovato = False
    for i, utente in enumerate(utenti_data["autorizzati"]):
        if isinstance(utente, dict) and utente.get("id") == user_id:
            # Promuovi l'utente a admin
            utenti_data["autorizzati"][i]["ruolo"] = "admin"
            trovato = True
            break
        elif not isinstance(utente, dict) and utente == user_id:
            # Converti il vecchio formato e promuovi a admin
            utenti_data["autorizzati"][i] = {
                "id": user_id,
                "nome": f"Utente {user_id}",
                "username": None,
                "data_registrazione": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "ruolo": "admin"
            }
            trovato = True
            break
    
    if trovato:
        # Salva le modifiche
        salva_utenti(utenti_data)
        return jsonify({"success": True, "message": "Utente promosso ad amministratore con successo"})
    else:
        return jsonify({"success": False, "message": "Utente non trovato"}), 404

# API per declassare un utente da admin
@app.route('/api/demote_user/<int:user_id>', methods=['POST'])
@login_required
def demote_user(user_id):
    # Verifica che l'utente corrente sia un admin
    if not current_user.is_admin:
        return jsonify({"success": False, "message": "Non hai i permessi per eseguire questa operazione"}), 403
    
    utenti_data = carica_utenti()
    
    # Cerca l'utente nella lista degli autorizzati
    trovato = False
    for i, utente in enumerate(utenti_data["autorizzati"]):
        if isinstance(utente, dict) and utente.get("id") == user_id:
            # Declassa l'utente a utente normale
            utenti_data["autorizzati"][i]["ruolo"] = "utente"
            trovato = True
            break
    
    if trovato:
        # Salva le modifiche
        salva_utenti(utenti_data)
        return jsonify({"success": True, "message": "Privilegi di amministratore rimossi con successo"})
    else:
        return jsonify({"success": False, "message": "Utente non trovato"}), 404

# Rotta per la gestione delle partite
@app.route('/matches')
@login_required
def matches():
    try:
        risultati = carica_risultati()
        
        # Funzione sicura per convertire la data
        def safe_date_convert(match):
            try:
                data = match.get('data_partita')
                if data is None or data == '':
                    return datetime.strptime('01/01/2000', '%d/%m/%Y')
                return datetime.strptime(data, '%d/%m/%Y')
            except (ValueError, TypeError) as e:
                app.logger.warning(f"Errore nella conversione della data: {e}, match: {match}")
                return datetime.strptime('01/01/2000', '%d/%m/%Y')
        
        # Ordina i risultati per data (più recenti prima)
        try:
            risultati.sort(key=safe_date_convert, reverse=True)
        except Exception as e:
            app.logger.error(f"Errore nell'ordinamento delle partite: {e}")
        
        return render_template('matches.html', risultati=risultati)
    except Exception as e:
        app.logger.error(f"Errore nella pagina matches: {e}")
        flash(f"Si è verificato un errore nel caricamento delle partite: {str(e)}", "danger")
        return render_template('matches.html', risultati=[])

# Rotta per aggiungere una nuova partita
@app.route('/match/add', methods=['GET', 'POST'])
@login_required
def add_match():
    if request.method == 'POST':
        # Ottieni i dati dal form
        categoria = request.form.get('categoria')
        genere = request.form.get('genere')
        tipo_partita = request.form.get('tipo_partita', 'normale')
        data_partita_raw = request.form.get('data_partita')  # Formato YYYY-MM-DD
        squadra1 = request.form.get('squadra1')
        squadra2 = request.form.get('squadra2')
        arbitro = request.form.get('arbitro')
        
        # Converti la data nel formato DD/MM/YYYY
        data_partita = datetime.strptime(data_partita_raw, '%Y-%m-%d').strftime('%d/%m/%Y')
        
        # Carica i risultati esistenti
        risultati = carica_risultati()
        
        # Crea il nuovo risultato con i campi comuni
        nuovo_risultato = {
            'categoria': categoria,
            'genere': genere,
            'tipo_partita': tipo_partita,
            'data_partita': data_partita,
            'squadra1': squadra1,
            'squadra2': squadra2,
            'arbitro': arbitro,
            'inserito_da': current_user.username,
            'timestamp_inserimento': datetime.now().isoformat()
        }
        
        # Gestione diversa per partite normali e triangolari
        if tipo_partita == 'triangolare':
            # Aggiungi la terza squadra
            squadra3 = request.form.get('squadra3')
            nuovo_risultato['squadra3'] = squadra3
            
            # Aggiungi i punteggi e le mete per ogni partita del triangolare
            # Partita 1: squadra1 vs squadra2
            partita1_punteggio1 = int(request.form.get('partita1_punteggio1', 0))
            partita1_punteggio2 = int(request.form.get('partita1_punteggio2', 0))
            partita1_mete1 = int(request.form.get('partita1_mete1', 0))
            partita1_mete2 = int(request.form.get('partita1_mete2', 0))
            
            # Partita 2: squadra1 vs squadra3
            partita2_punteggio1 = int(request.form.get('partita2_punteggio1', 0))
            partita2_punteggio2 = int(request.form.get('partita2_punteggio2', 0))
            partita2_mete1 = int(request.form.get('partita2_mete1', 0))
            partita2_mete2 = int(request.form.get('partita2_mete2', 0))
            
            # Partita 3: squadra2 vs squadra3
            partita3_punteggio1 = int(request.form.get('partita3_punteggio1', 0))
            partita3_punteggio2 = int(request.form.get('partita3_punteggio2', 0))
            partita3_mete1 = int(request.form.get('partita3_mete1', 0))
            partita3_mete2 = int(request.form.get('partita3_mete2', 0))
            
            # Aggiungi i dati delle partite al risultato
            nuovo_risultato.update({
                'partita1_punteggio1': partita1_punteggio1,
                'partita1_punteggio2': partita1_punteggio2,
                'partita1_mete1': partita1_mete1,
                'partita1_mete2': partita1_mete2,
                
                'partita2_punteggio1': partita2_punteggio1,
                'partita2_punteggio2': partita2_punteggio2,
                'partita2_mete1': partita2_mete1,
                'partita2_mete2': partita2_mete2,
                
                'partita3_punteggio1': partita3_punteggio1,
                'partita3_punteggio2': partita3_punteggio2,
                'partita3_mete1': partita3_mete1,
                'partita3_mete2': partita3_mete2
            })
            
            # Calcola i totali per ogni squadra
            nuovo_risultato['punteggio1'] = partita1_punteggio1 + partita2_punteggio1
            nuovo_risultato['punteggio2'] = partita1_punteggio2 + partita3_punteggio1
            nuovo_risultato['punteggio3'] = partita2_punteggio2 + partita3_punteggio2
            
            nuovo_risultato['mete1'] = partita1_mete1 + partita2_mete1
            nuovo_risultato['mete2'] = partita1_mete2 + partita3_mete1
            nuovo_risultato['mete3'] = partita2_mete2 + partita3_mete2
            
            app.logger.info(f"Aggiunta partita triangolare: {squadra1} vs {squadra2} vs {squadra3}")
        else:
            # Per le partite normali, aggiungi i punteggi e le mete standard
            punteggio1 = int(request.form.get('punteggio1', 0))
            punteggio2 = int(request.form.get('punteggio2', 0))
            mete1 = int(request.form.get('mete1', 0))
            mete2 = int(request.form.get('mete2', 0))
            
            nuovo_risultato.update({
                'punteggio1': punteggio1,
                'punteggio2': punteggio2,
                'mete1': mete1,
                'mete2': mete2
            })
            
            app.logger.info(f"Aggiunta partita normale: {squadra1} vs {squadra2}")
        
        # Aggiungi il nuovo risultato
        risultati.append(nuovo_risultato)
        
        # Salva i risultati
        salva_risultati(risultati)
        
        flash('Partita aggiunta con successo!', 'success')
        return redirect(url_for('matches'))
    
    # Carica le squadre e le categorie per il form
    squadre_raw = carica_squadre()
    categorie = ["Serie A Elite", "Serie A", "Serie B", "Serie C1", "U18 Nazionale", "U18", "U16", "U14"]
    
    # Verifica se squadre_raw è già un dizionario
    if isinstance(squadre_raw, dict):
        squadre = squadre_raw
    else:
        # Se è una lista, crea un dizionario con una sola categoria "Tutte le squadre"
        squadre = {"Tutte le squadre": sorted(squadre_raw)}
    
    return render_template('add_match.html', squadre=squadre, categorie=categorie)

# Funzione per caricare le reazioni dal bot
def carica_reazioni():
    REAZIONI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reazioni.json')
    if os.path.exists(REAZIONI_FILE):
        with open(REAZIONI_FILE, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    return {}

# Rotta per visualizzare i dettagli di una partita
@app.route('/match/<int:match_id>')
@login_required
def match_details(match_id):
    risultati = carica_risultati()
    
    if 0 <= match_id < len(risultati):
        partita = risultati[match_id]
        
        # Carica le reazioni se esistono
        reazioni = carica_reazioni()
        
        # Cerca le reazioni per questa partita
        # Nota: nel bot, le reazioni sono associate all'ID del messaggio Telegram
        # Qui dobbiamo fare una ricerca basata su altri criteri
        partita_reazioni = {
            "like": [],
            "love": [],
            "fire": [],
            "clap": [],
            "rugby": []
        }
        
        # Se la partita ha un campo message_id, possiamo usarlo per cercare le reazioni
        if 'message_id' in partita and str(partita['message_id']) in reazioni:
            partita_reazioni = reazioni[str(partita['message_id'])]
        
        return render_template('match_details.html', 
                              partita=partita, 
                              match_id=match_id,
                              reazioni=partita_reazioni)
    
    flash('Partita non trovata!', 'danger')
    return redirect(url_for('matches'))

# Rotta per modificare una partita
@app.route('/match/edit/<int:match_id>', methods=['GET', 'POST'])
@login_required
def edit_match(match_id):
    risultati = carica_risultati()
    
    if 0 <= match_id < len(risultati):
        if request.method == 'POST':
            # Aggiorna i dati della partita
            risultati[match_id]['categoria'] = request.form.get('categoria')
            risultati[match_id]['genere'] = request.form.get('genere')
            risultati[match_id]['data_partita'] = request.form.get('data_partita')
            risultati[match_id]['squadra1'] = request.form.get('squadra1')
            risultati[match_id]['squadra2'] = request.form.get('squadra2')
            risultati[match_id]['punteggio1'] = int(request.form.get('punteggio1'))
            risultati[match_id]['punteggio2'] = int(request.form.get('punteggio2'))
            risultati[match_id]['mete1'] = int(request.form.get('mete1'))
            risultati[match_id]['mete2'] = int(request.form.get('mete2'))
            risultati[match_id]['arbitro'] = request.form.get('arbitro')
            risultati[match_id]['modificato_da'] = current_user.username
            risultati[match_id]['timestamp_modifica'] = datetime.now().isoformat()
            
            # Salva le modifiche
            salva_risultati(risultati)
            
            flash('Partita aggiornata con successo!', 'success')
            return redirect(url_for('match_details', match_id=match_id))
        
        # Carica le squadre per il form
        squadre_raw = carica_squadre()
        categorie = ["Serie A Elite", "Serie A", "Serie B", "Serie C1", "U18 Nazionale", "U18", "U16", "U14"]
        
        # Verifica se squadre_raw è già un dizionario
        if isinstance(squadre_raw, dict):
            squadre = squadre_raw
        else:
            # Se è una lista, crea un dizionario con una sola categoria "Tutte le squadre"
            squadre = {"Tutte le squadre": sorted(squadre_raw)}
        
        return render_template('edit_match.html', 
                              partita=risultati[match_id], 
                              match_id=match_id,
                              squadre=squadre,
                              categorie=categorie)
    
    flash('Partita non trovata!', 'danger')
    return redirect(url_for('matches'))

# Rotta per eliminare una partita
@app.route('/match/delete/<int:match_id>', methods=['POST'])
@login_required
def delete_match(match_id):
    risultati = carica_risultati()
    
    if 0 <= match_id < len(risultati):
        # Rimuovi la partita
        del risultati[match_id]
        
        # Salva le modifiche
        salva_risultati(risultati)
        
        flash('Partita eliminata con successo!', 'success')
    else:
        flash('Partita non trovata!', 'danger')
    
    return redirect(url_for('matches'))

# Rotta per la gestione delle squadre
@app.route('/teams')
@login_required
def teams():
    squadre_per_categoria = carica_squadre()
    
    # Estrai tutte le squadre in una lista unica
    squadre = []
    
    # Verifica se squadre_per_categoria è un dizionario o una lista
    if isinstance(squadre_per_categoria, dict):
        # Se è un dizionario, estrai le squadre da ogni categoria
        for categoria, squadre_categoria in squadre_per_categoria.items():
            squadre.extend(squadre_categoria)
    else:
        # Se è già una lista, usala direttamente
        squadre = squadre_per_categoria
    
    # Rimuovi eventuali duplicati e ordina alfabeticamente
    squadre = sorted(list(set(squadre)))
    
    return render_template('teams.html', squadre=squadre)

# API per aggiungere una squadra
@app.route('/api/teams/add', methods=['POST'])
@login_required
def add_team():
    team_name = request.form.get('team_name')
    if not team_name:
        return jsonify({"success": False, "message": "Nome squadra mancante"}), 400
    
    try:
        # Carica le squadre esistenti
        squadre_per_categoria = carica_squadre()
        
        # Estrai tutte le squadre in una lista unica per verificare duplicati
        tutte_le_squadre = []
        
        # Verifica se squadre_per_categoria è un dizionario o una lista
        if isinstance(squadre_per_categoria, dict):
            # Se è un dizionario, estrai le squadre da ogni categoria
            for categoria, squadre_categoria in squadre_per_categoria.items():
                tutte_le_squadre.extend(squadre_categoria)
        else:
            # Se è già una lista, usala direttamente
            tutte_le_squadre = squadre_per_categoria
        
        # Verifica se la squadra esiste già
        if team_name in tutte_le_squadre:
            return jsonify({"success": False, "message": "Squadra già esistente"}), 400
        
        # Se squadre_per_categoria è una lista, convertila in un dizionario
        if not isinstance(squadre_per_categoria, dict):
            squadre_per_categoria = {"Generale": list(squadre_per_categoria)}
        
        # Aggiungi la nuova squadra alla categoria "Generale" (o crea la categoria se non esiste)
        if "Generale" not in squadre_per_categoria:
            squadre_per_categoria["Generale"] = []
        
        squadre_per_categoria["Generale"].append(team_name)
        
        # Salva le squadre
        salva_squadre(squadre_per_categoria)
        
        return jsonify({"success": True, "message": "Squadra aggiunta con successo"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Errore: {str(e)}"}), 500

# API per aggiornare una squadra
@app.route('/api/teams/update', methods=['POST'])
@login_required
def update_team():
    team_index = request.form.get('team_index')
    new_team_name = request.form.get('team_name')
    
    if not team_index or not new_team_name:
        return jsonify({"success": False, "message": "Dati mancanti"}), 400
    
    try:
        team_index = int(team_index)
        squadre_per_categoria = carica_squadre()
        
        # Estrai tutte le squadre in una lista unica
        tutte_le_squadre = []
        
        # Verifica se squadre_per_categoria è un dizionario o una lista
        if isinstance(squadre_per_categoria, dict):
            # Se è un dizionario, estrai le squadre da ogni categoria
            for categoria, squadre_categoria in squadre_per_categoria.items():
                tutte_le_squadre.extend(squadre_categoria)
        else:
            # Se è già una lista, usala direttamente
            tutte_le_squadre = squadre_per_categoria
        
        # Ordina alfabeticamente (come nella route teams())
        tutte_le_squadre = sorted(list(set(tutte_le_squadre)))
        
        if team_index < 0 or team_index >= len(tutte_le_squadre):
            return jsonify({"success": False, "message": "Indice squadra non valido"}), 400
        
        # Ottieni il nome della squadra da aggiornare
        old_team_name = tutte_le_squadre[team_index]
        
        # Verifica se il nuovo nome esiste già (escludendo la squadra corrente)
        if new_team_name in tutte_le_squadre and new_team_name != old_team_name:
            return jsonify({"success": False, "message": "Esiste già una squadra con questo nome"}), 400
        
        # Se squadre_per_categoria è una lista, convertila in un dizionario
        if not isinstance(squadre_per_categoria, dict):
            squadre_per_categoria = {"Generale": list(squadre_per_categoria)}
            
        # Aggiorna il nome della squadra in tutte le categorie
        for categoria, squadre_categoria in squadre_per_categoria.items():
            if old_team_name in squadre_categoria:
                # Trova l'indice della squadra nella categoria
                idx = squadre_categoria.index(old_team_name)
                # Aggiorna il nome
                squadre_categoria[idx] = new_team_name
        
        # Salva le squadre
        salva_squadre(squadre_per_categoria)
        
        return jsonify({"success": True, "message": "Squadra aggiornata con successo"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Errore: {str(e)}"}), 500

# API per eliminare una squadra
@app.route('/api/teams/delete', methods=['POST'])
@login_required
def delete_team():
    team_index = request.form.get('team_index')
    
    if not team_index:
        return jsonify({"success": False, "message": "Indice squadra mancante"}), 400
    
    try:
        team_index = int(team_index)
        squadre_per_categoria = carica_squadre()
        
        # Estrai tutte le squadre in una lista unica
        tutte_le_squadre = []
        
        # Verifica se squadre_per_categoria è un dizionario o una lista
        if isinstance(squadre_per_categoria, dict):
            # Se è un dizionario, estrai le squadre da ogni categoria
            for categoria, squadre_categoria in squadre_per_categoria.items():
                tutte_le_squadre.extend(squadre_categoria)
        else:
            # Se è già una lista, usala direttamente
            tutte_le_squadre = squadre_per_categoria
        
        # Ordina alfabeticamente (come nella route teams())
        tutte_le_squadre = sorted(list(set(tutte_le_squadre)))
        
        if team_index < 0 or team_index >= len(tutte_le_squadre):
            return jsonify({"success": False, "message": "Indice squadra non valido"}), 400
        
        # Ottieni il nome della squadra da eliminare
        team_name = tutte_le_squadre[team_index]
        
        # Se squadre_per_categoria è una lista, convertila in un dizionario
        if not isinstance(squadre_per_categoria, dict):
            squadre_per_categoria = {"Generale": list(squadre_per_categoria)}
            
        # Rimuovi la squadra da tutte le categorie
        for categoria, squadre_categoria in list(squadre_per_categoria.items()):
            if team_name in squadre_categoria:
                squadre_categoria.remove(team_name)
                # Se la categoria è vuota, rimuovila
                if not squadre_categoria:
                    del squadre_per_categoria[categoria]
        
        # Salva le squadre
        salva_squadre(squadre_per_categoria)
        
        return jsonify({"success": True, "message": f"Squadra '{team_name}' eliminata con successo"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Errore: {str(e)}"}), 500

# Rotta per le statistiche
@app.route('/stats')
@login_required
def stats():
    risultati = carica_risultati()
    
    # Statistiche per categoria
    stats_categoria = {}
    for risultato in risultati:
        categoria = risultato.get('categoria')
        if categoria not in stats_categoria:
            stats_categoria[categoria] = 0
        stats_categoria[categoria] += 1
    
    # Statistiche per squadra
    stats_squadre = {}
    for risultato in risultati:
        squadra1 = risultato.get('squadra1')
        squadra2 = risultato.get('squadra2')
        
        if squadra1 not in stats_squadre:
            stats_squadre[squadra1] = {'partite': 0, 'vittorie': 0, 'pareggi': 0, 'sconfitte': 0, 'punti_fatti': 0, 'punti_subiti': 0}
        if squadra2 not in stats_squadre:
            stats_squadre[squadra2] = {'partite': 0, 'vittorie': 0, 'pareggi': 0, 'sconfitte': 0, 'punti_fatti': 0, 'punti_subiti': 0}
        
        # Aggiorna le statistiche
        stats_squadre[squadra1]['partite'] += 1
        stats_squadre[squadra2]['partite'] += 1
        
        punteggio1 = risultato.get('punteggio1', 0)
        punteggio2 = risultato.get('punteggio2', 0)
        
        stats_squadre[squadra1]['punti_fatti'] += punteggio1
        stats_squadre[squadra1]['punti_subiti'] += punteggio2
        stats_squadre[squadra2]['punti_fatti'] += punteggio2
        stats_squadre[squadra2]['punti_subiti'] += punteggio1
        
        if punteggio1 > punteggio2:
            stats_squadre[squadra1]['vittorie'] += 1
            stats_squadre[squadra2]['sconfitte'] += 1
        elif punteggio1 < punteggio2:
            stats_squadre[squadra1]['sconfitte'] += 1
            stats_squadre[squadra2]['vittorie'] += 1
        else:
            stats_squadre[squadra1]['pareggi'] += 1
            stats_squadre[squadra2]['pareggi'] += 1
    
    # Ordina le squadre per numero di vittorie
    stats_squadre = {k: v for k, v in sorted(stats_squadre.items(), key=lambda item: item[1]['vittorie'], reverse=True)}
    
    return render_template('stats.html', 
                          stats_categoria=stats_categoria,
                          stats_squadre=stats_squadre)

# Rotta per la pagina di monitoraggio del bot
@app.route('/monitor')
@login_required
def monitor():
    try:
        # Verifica che l'utente sia un amministratore
        if not current_user.is_admin:
            flash('Solo gli amministratori possono accedere alla pagina di monitoraggio.', 'danger')
            return redirect(url_for('dashboard'))
        
        # Ottieni informazioni sul sistema
        import platform
        import psutil
        import time
        from datetime import datetime, timedelta
        
        # Informazioni sul sistema
        system_info = {
            'sistema_operativo': platform.system(),
            'versione_os': platform.version(),
            'architettura': platform.machine(),
            'processore': platform.processor(),
            'python_version': platform.python_version(),
            'uptime': str(timedelta(seconds=int(time.time() - psutil.boot_time())))
        }
        
        # Informazioni sulle risorse
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        resources_info = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used': f"{memory.used / (1024 * 1024 * 1024):.2f} GB",
            'memory_total': f"{memory.total / (1024 * 1024 * 1024):.2f} GB",
            'disk_percent': disk.percent,
            'disk_used': f"{disk.used / (1024 * 1024 * 1024):.2f} GB",
            'disk_total': f"{disk.total / (1024 * 1024 * 1024):.2f} GB"
        }
        
        # Informazioni sul bot
        bot_info = {
            'token_configurato': bool(BOT_TOKEN),
            'token_web_configurato': bool(TOKEN_WEB),
            'channel_id': CHANNEL_ID,
            'channel_id_web': CHANNEL_ID_WEB,
            'supabase_configurato': is_supabase_configured()
        }
        
        # Statistiche di utilizzo
        utenti_data = carica_utenti()
        risultati = carica_risultati()
        
        usage_stats = {
            'utenti_autorizzati': len(utenti_data.get("autorizzati", [])),
            'utenti_in_attesa': len(utenti_data.get("in_attesa", [])),
            'partite_registrate': len(risultati),
            'admin_web': len(carica_admin_users())
        }
        
        # Ottieni i log recenti (ultimi 100 eventi)
        log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bot.log')
        recent_logs = []
        
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    # Leggi le ultime 100 righe
                    lines = f.readlines()[-100:]
                    for line in lines:
                        line = line.strip()
                        if line:
                            # Estrai il livello di log (INFO, WARNING, ERROR, ecc.)
                            level = "INFO"
                            if "WARNING" in line:
                                level = "WARNING"
                            elif "ERROR" in line:
                                level = "ERROR"
                            elif "CRITICAL" in line:
                                level = "CRITICAL"
                            elif "DEBUG" in line:
                                level = "DEBUG"
                            
                            recent_logs.append({
                                'timestamp': line.split(' - ')[0] if ' - ' in line else "",
                                'level': level,
                                'message': line
                            })
            except Exception as e:
                app.logger.error(f"Errore nella lettura del file di log: {e}")
                recent_logs.append({
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'level': "ERROR",
                    'message': f"Errore nella lettura del file di log: {str(e)}"
                })
        
        return render_template('monitor.html',
                              system_info=system_info,
                              resources_info=resources_info,
                              bot_info=bot_info,
                              usage_stats=usage_stats,
                              recent_logs=recent_logs)
    except Exception as e:
        app.logger.error(f"Errore nella pagina di monitoraggio: {e}")
        flash(f'Si è verificato un errore durante il caricamento della pagina di monitoraggio: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# Rotte per la gestione dei quiz
@app.route('/quizzes')
@login_required
def quizzes():
    """Pagina principale per la gestione dei quiz."""
    try:
        # Carica i quiz
        quiz_data = carica_quiz()
        
        # Carica le statistiche
        stats = carica_statistiche_quiz()
        
        # Carica i quiz in attesa
        pending_data = load_pending_quizzes()
        pending_quizzes = pending_data.get("quiz_pending", [])
        pending_count = len(pending_quizzes)
        
        # Calcola il numero totale di quiz
        total_quizzes = sum(len(cat.get("quiz", [])) for cat in quiz_data.get("categorie", []))
        
        # Calcola il numero totale di risposte e risposte corrette
        total_responses = 0
        correct_responses = 0
        for quiz in stats.get("quiz_giornalieri", []):
            for risposta in quiz.get("risposte", []):
                total_responses += 1
                if risposta.get("corretta", False):
                    correct_responses += 1
        
        # Crea la classifica
        leaderboard = []
        for user_id, user_data in stats.get("partecipanti", {}).items():
            leaderboard.append({
                "id": user_id,
                "nome": user_data.get("nome", "Utente"),
                "username": user_data.get("username", ""),
                "punti": user_data.get("punti", 0),
                "risposte_corrette": user_data.get("risposte_corrette", 0),
                "risposte_totali": user_data.get("risposte_totali", 0)
            })
        
        # Ordina la classifica per punti
        leaderboard.sort(key=lambda x: x["punti"], reverse=True)
        
        return render_template('quizzes.html',
                              quiz_data=quiz_data,
                              categories=quiz_data.get("categorie", []),
                              stats=stats,
                              pending_quizzes=pending_quizzes,
                              pending_count=pending_count,
                              total_quizzes=total_quizzes,
                              total_responses=total_responses,
                              correct_responses=correct_responses,
                              leaderboard=leaderboard[:10])  # Mostra solo i primi 10
    except Exception as e:
        app.logger.error(f"Errore nella pagina dei quiz: {e}")
        flash(f'Si è verificato un errore durante il caricamento della pagina dei quiz: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/quizzes/add', methods=['GET', 'POST'])
@login_required
def add_quiz():
    """Pagina per aggiungere un nuovo quiz."""
    try:
        # Carica i quiz per ottenere le categorie
        quiz_data = carica_quiz()
        categories = quiz_data.get("categorie", [])
        
        if request.method == 'POST':
            # Ottieni i dati dal form
            category = request.form.get('category')
            question = request.form.get('question')
            options = [
                request.form.get('option0'),
                request.form.get('option1'),
                request.form.get('option2'),
                request.form.get('option3')
            ]
            correct_answer = int(request.form.get('correct_answer', 0))
            explanation = request.form.get('explanation')
            
            # Trova la categoria
            category_found = False
            for cat in categories:
                if cat["nome"] == category:
                    # Aggiungi il quiz alla categoria
                    cat["quiz"].append({
                        "domanda": question,
                        "opzioni": options,
                        "risposta_corretta": correct_answer,
                        "spiegazione": explanation
                    })
                    category_found = True
                    break
            
            # Se la categoria non esiste, creala
            if not category_found:
                quiz_data["categorie"].append({
                    "nome": category,
                    "descrizione": f"Domande su {category}",
                    "quiz": [{
                        "domanda": question,
                        "opzioni": options,
                        "risposta_corretta": correct_answer,
                        "spiegazione": explanation
                    }]
                })
            
            # Salva i quiz
            salva_quiz(quiz_data)
            
            flash('Quiz aggiunto con successo!', 'success')
            return redirect(url_for('quizzes'))
        
        return render_template('add_quiz.html', categories=categories)
    except Exception as e:
        app.logger.error(f"Errore nell'aggiunta di un quiz: {e}")
        flash(f'Si è verificato un errore durante l\'aggiunta del quiz: {str(e)}', 'danger')
        return redirect(url_for('quizzes'))

@app.route('/quizzes/edit/<category>/<int:index>', methods=['GET', 'POST'])
@login_required
def edit_quiz(category, index):
    """Pagina per modificare un quiz esistente."""
    try:
        # Carica i quiz
        quiz_data = carica_quiz()
        categories = quiz_data.get("categorie", [])
        
        # Trova la categoria e il quiz
        quiz = None
        for cat in categories:
            if cat["nome"] == category and len(cat.get("quiz", [])) > index:
                quiz = cat["quiz"][index]
                break
        
        if not quiz:
            flash('Quiz non trovato!', 'danger')
            return redirect(url_for('quizzes'))
        
        if request.method == 'POST':
            # Ottieni i dati dal form
            new_category = request.form.get('category')
            question = request.form.get('question')
            options = [
                request.form.get('option0'),
                request.form.get('option1'),
                request.form.get('option2'),
                request.form.get('option3')
            ]
            correct_answer = int(request.form.get('correct_answer', 0))
            explanation = request.form.get('explanation')
            
            # Se la categoria è cambiata, rimuovi il quiz dalla vecchia categoria e aggiungilo alla nuova
            if new_category != category:
                # Rimuovi dalla vecchia categoria
                for cat in categories:
                    if cat["nome"] == category and len(cat.get("quiz", [])) > index:
                        cat["quiz"].pop(index)
                        break
                
                # Aggiungi alla nuova categoria
                category_found = False
                for cat in categories:
                    if cat["nome"] == new_category:
                        cat["quiz"].append({
                            "domanda": question,
                            "opzioni": options,
                            "risposta_corretta": correct_answer,
                            "spiegazione": explanation
                        })
                        category_found = True
                        break
                
                # Se la nuova categoria non esiste, creala
                if not category_found:
                    quiz_data["categorie"].append({
                        "nome": new_category,
                        "descrizione": f"Domande su {new_category}",
                        "quiz": [{
                            "domanda": question,
                            "opzioni": options,
                            "risposta_corretta": correct_answer,
                            "spiegazione": explanation
                        }]
                    })
            else:
                # Aggiorna il quiz nella stessa categoria
                for cat in categories:
                    if cat["nome"] == category and len(cat.get("quiz", [])) > index:
                        cat["quiz"][index] = {
                            "domanda": question,
                            "opzioni": options,
                            "risposta_corretta": correct_answer,
                            "spiegazione": explanation
                        }
                        break
            
            # Salva i quiz
            salva_quiz(quiz_data)
            
            flash('Quiz modificato con successo!', 'success')
            return redirect(url_for('quizzes'))
        
        return render_template('edit_quiz.html', quiz=quiz, category=category, index=index, categories=categories)
    except Exception as e:
        app.logger.error(f"Errore nella modifica di un quiz: {e}")
        flash(f'Si è verificato un errore durante la modifica del quiz: {str(e)}', 'danger')
        return redirect(url_for('quizzes'))

@app.route('/quizzes/view/<category>/<int:index>')
@login_required
def view_quiz(category, index):
    """Pagina per visualizzare un quiz."""
    try:
        # Carica i quiz
        quiz_data = carica_quiz()
        
        # Trova la categoria e il quiz
        quiz = None
        for cat in quiz_data.get("categorie", []):
            if cat["nome"] == category and len(cat.get("quiz", [])) > index:
                quiz = cat["quiz"][index]
                break
        
        if not quiz:
            flash('Quiz non trovato!', 'danger')
            return redirect(url_for('quizzes'))
        
        return render_template('view_quiz.html', quiz=quiz, category=category, index=index)
    except Exception as e:
        app.logger.error(f"Errore nella visualizzazione di un quiz: {e}")
        flash(f'Si è verificato un errore durante la visualizzazione del quiz: {str(e)}', 'danger')
        return redirect(url_for('quizzes'))

@app.route('/quizzes/delete', methods=['POST'])
@login_required
def delete_quiz():
    """Elimina un quiz."""
    try:
        category = request.form.get('category')
        index = int(request.form.get('index', 0))
        
        # Carica i quiz
        quiz_data = carica_quiz()
        
        # Trova la categoria e rimuovi il quiz
        for cat in quiz_data.get("categorie", []):
            if cat["nome"] == category and len(cat.get("quiz", [])) > index:
                cat["quiz"].pop(index)
                break
        
        # Salva i quiz
        salva_quiz(quiz_data)
        
        flash('Quiz eliminato con successo!', 'success')
        return redirect(url_for('quizzes'))
    except Exception as e:
        app.logger.error(f"Errore nell'eliminazione di un quiz: {e}")
        flash(f'Si è verificato un errore durante l\'eliminazione del quiz: {str(e)}', 'danger')
        return redirect(url_for('quizzes'))

@app.route('/quizzes/add_category', methods=['POST'])
@login_required
def add_category():
    """Aggiunge una nuova categoria di quiz."""
    try:
        name = request.form.get('name')
        description = request.form.get('description')
        
        # Carica i quiz
        quiz_data = carica_quiz()
        
        # Verifica se la categoria esiste già
        for cat in quiz_data.get("categorie", []):
            if cat["nome"] == name:
                flash('Questa categoria esiste già!', 'warning')
                return redirect(url_for('quizzes'))
        
        # Aggiungi la nuova categoria
        quiz_data["categorie"].append({
            "nome": name,
            "descrizione": description,
            "quiz": []
        })
        
        # Salva i quiz
        salva_quiz(quiz_data)
        
        flash('Categoria aggiunta con successo!', 'success')
        return redirect(url_for('quizzes'))
    except Exception as e:
        app.logger.error(f"Errore nell'aggiunta di una categoria: {e}")
        flash(f'Si è verificato un errore durante l\'aggiunta della categoria: {str(e)}', 'danger')
        return redirect(url_for('quizzes'))

@app.route('/quizzes/generate', methods=['GET', 'POST'])
@login_required
def generate_quizzes():
    """Pagina per generare quiz con l'IA."""
    try:
        # Carica i quiz per ottenere le categorie
        quiz_data = carica_quiz()
        categories = quiz_data.get("categorie", [])
        
        # Carica i quiz in attesa
        pending_data = load_pending_quizzes()
        pending_count = len(pending_data.get("quiz_pending", []))
        
        generated_quizzes = []
        
        if request.method == 'POST':
            # Ottieni i dati dal form
            num_quizzes = int(request.form.get('num_quizzes', 3))
            category = request.form.get('category', '')
            
            # Genera i quiz
            generated_quizzes = generate_multiple_quizzes(num_quizzes, category if category else None)
            
            if generated_quizzes:
                flash(f'Generati {len(generated_quizzes)} nuovi quiz con successo!', 'success')
            else:
                flash('Non è stato possibile generare i quiz. Verifica la configurazione dell\'API OpenAI.', 'danger')
            
            # Aggiorna il conteggio dei quiz in attesa
            pending_data = load_pending_quizzes()
            pending_count = len(pending_data.get("quiz_pending", []))
        
        return render_template('generate_quizzes.html', 
                              categories=categories, 
                              pending_count=pending_count,
                              generated_quizzes=generated_quizzes)
    except Exception as e:
        app.logger.error(f"Errore nella generazione di quiz: {e}")
        flash(f'Si è verificato un errore durante la generazione dei quiz: {str(e)}', 'danger')
        return redirect(url_for('quizzes'))

@app.route('/quizzes/approve_pending', methods=['POST'])
@login_required
def approve_pending_quiz_route():
    """Approva un quiz in attesa."""
    try:
        data = request.get_json()
        index = int(data.get('index', 0))
        
        success = approve_pending_quiz(index)
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Errore nell'approvazione del quiz"})
    except Exception as e:
        app.logger.error(f"Errore nell'approvazione di un quiz in attesa: {e}")
        return jsonify({"success": False, "message": str(e)})

@app.route('/quizzes/reject_pending', methods=['POST'])
@login_required
def reject_pending_quiz_route():
    """Rifiuta un quiz in attesa."""
    try:
        data = request.get_json()
        index = int(data.get('index', 0))
        
        success = reject_pending_quiz(index)
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Errore nel rifiuto del quiz"})
    except Exception as e:
        app.logger.error(f"Errore nel rifiuto di un quiz in attesa: {e}")
        return jsonify({"success": False, "message": str(e)})

@app.route('/quizzes/send_test/<category>/<int:index>')
@login_required
def send_test_quiz(category, index):
    """Invia un quiz direttamente al canale principale."""
    try:
        # Carica i quiz
        quiz_data = carica_quiz()
        
        # Trova la categoria e il quiz
        quiz_obj = None
        for cat in quiz_data.get("categorie", []):
            if cat["nome"] == category and len(cat.get("quiz", [])) > index:
                quiz_obj = {
                    "quiz": cat["quiz"][index],
                    "categoria": cat["nome"]
                }
                break
        
        if not quiz_obj:
            flash('Quiz non trovato!', 'danger')
            return redirect(url_for('view_quiz', category=category, index=index))
        
        # Ottieni l'ID del canale principale
        from modules.config import CHANNEL_ID
        
        # Crea un bot Telegram
        bot = telegram.Bot(token=BOT_TOKEN)
        
        # Crea un contesto fittizio
        class FakeContext:
            def __init__(self, bot):
                self.bot = bot
        
        # Chiedi conferma prima di inviare al canale principale
        if request.args.get('confirm') != 'true':
            flash('Stai per inviare questo quiz al canale principale. Questa azione non può essere annullata.', 'warning')
            return render_template('confirm_send_quiz.html', 
                                  quiz=quiz_obj["quiz"], 
                                  category=category, 
                                  index=index,
                                  channel_id=CHANNEL_ID)
        
        # Invia il quiz al canale principale
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(invia_quiz_al_canale(FakeContext(bot), CHANNEL_ID, quiz_obj))
        loop.close()
        
        if success:
            flash('Quiz inviato con successo al canale!', 'success')
        else:
            flash('Errore nell\'invio del quiz al canale.', 'danger')
        
        return redirect(url_for('view_quiz', category=category, index=index))
    except Exception as e:
        app.logger.error(f"Errore nell'invio di un quiz: {e}")
        flash(f'Si è verificato un errore durante l\'invio del quiz: {str(e)}', 'danger')
        return redirect(url_for('view_quiz', category=category, index=index))

# Rotta per riavviare il bot
@app.route('/maintenance/restart_bot', methods=['POST'])
@login_required
def restart_bot():
    try:
        # Verifica che l'utente sia un amministratore
        if not current_user.is_admin:
            flash('Solo gli amministratori possono riavviare il bot.', 'danger')
            return redirect(url_for('monitor'))
        
        # Ottieni il percorso del file principale del bot
        bot_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bot.py')
        
        if not os.path.exists(bot_file):
            flash('File principale del bot non trovato.', 'danger')
            return redirect(url_for('monitor'))
        
        # Esegui il comando per riavviare il bot in background
        import subprocess
        import sys
        
        # Termina eventuali processi esistenti del bot
        try:
            subprocess.run(['pkill', '-f', 'python.*bot\.py'], check=False)
        except Exception as e:
            app.logger.warning(f"Errore durante la terminazione dei processi esistenti: {e}")
        
        # Avvia il bot in background
        try:
            subprocess.Popen([sys.executable, bot_file], 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE, 
                            start_new_session=True)
            
            flash('Bot riavviato con successo.', 'success')
        except Exception as e:
            flash(f'Errore durante il riavvio del bot: {str(e)}', 'danger')
        
        return redirect(url_for('monitor'))
    except Exception as e:
        app.logger.error(f"Errore durante il riavvio del bot: {e}")
        flash(f'Si è verificato un errore durante il riavvio del bot: {str(e)}', 'danger')
        return redirect(url_for('monitor'))

# Rotta per pulire i log
@app.route('/maintenance/clean_logs', methods=['POST'])
@login_required
def clean_logs():
    try:
        # Verifica che l'utente sia un amministratore
        if not current_user.is_admin:
            flash('Solo gli amministratori possono pulire i log.', 'danger')
            return redirect(url_for('monitor'))
        
        # Ottieni il percorso del file di log
        log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bot.log')
        
        if not os.path.exists(log_file):
            flash('File di log non trovato.', 'warning')
            return redirect(url_for('monitor'))
        
        # Crea un backup del file di log
        import shutil
        from datetime import datetime
        
        backup_file = f"{log_file}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
        shutil.copy2(log_file, backup_file)
        
        # Pulisci il file di log
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"--- Log pulito il {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        
        flash('Log puliti con successo. È stato creato un backup del file di log originale.', 'success')
        return redirect(url_for('monitor'))
    except Exception as e:
        app.logger.error(f"Errore durante la pulizia dei log: {e}")
        flash(f'Si è verificato un errore durante la pulizia dei log: {str(e)}', 'danger')
        return redirect(url_for('monitor'))

# Rotta per eseguire il backup dei dati
@app.route('/maintenance/backup_data', methods=['POST'])
@login_required
def backup_data():
    try:
        # Verifica che l'utente sia un amministratore
        if not current_user.is_admin:
            flash('Solo gli amministratori possono eseguire il backup dei dati.', 'danger')
            return redirect(url_for('monitor'))
        
        # Ottieni il percorso della directory principale
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Crea una directory per i backup se non esiste
        backup_dir = os.path.join(root_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Crea un nome per il file di backup
        from datetime import datetime
        import zipfile
        
        backup_file = os.path.join(backup_dir, f"backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip")
        
        # Crea un file zip con i dati
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Aggiungi i file JSON
            for file in ['utenti.json', 'risultati.json', 'squadre.json', 'admin_users.json', 'reazioni.json']:
                file_path = os.path.join(root_dir, file)
                if os.path.exists(file_path):
                    zipf.write(file_path, file)
            
            # Aggiungi il file di configurazione
            config_file = os.path.join(root_dir, 'modules', 'config.py')
            if os.path.exists(config_file):
                zipf.write(config_file, os.path.join('modules', 'config.py'))
            
            # Aggiungi il file di configurazione web
            config_web_file = os.path.join(root_dir, 'modules', 'config_web.py')
            if os.path.exists(config_web_file):
                zipf.write(config_web_file, os.path.join('modules', 'config_web.py'))
            
            # Aggiungi il file di token
            token_file = os.path.join(root_dir, 'token.txt')
            if os.path.exists(token_file):
                zipf.write(token_file, 'token.txt')
        
        flash(f'Backup dei dati eseguito con successo. File salvato in: {backup_file}', 'success')
        return redirect(url_for('monitor'))
    except Exception as e:
        app.logger.error(f"Errore durante il backup dei dati: {e}")
        flash(f'Si è verificato un errore durante il backup dei dati: {str(e)}', 'danger')
        return redirect(url_for('monitor'))

        # Ottieni informazioni sul sistema
        import platform
        import psutil
        import time
        from datetime import datetime, timedelta
        
        # Informazioni sul sistema
        system_info = {
            'sistema_operativo': platform.system(),
            'versione_os': platform.version(),
            'architettura': platform.machine(),
            'processore': platform.processor(),
            'python_version': platform.python_version(),
            'uptime': str(timedelta(seconds=int(time.time() - psutil.boot_time())))
        }
        
        # Informazioni sulle risorse
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        resources_info = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used': f"{memory.used / (1024 * 1024 * 1024):.2f} GB",
            'memory_total': f"{memory.total / (1024 * 1024 * 1024):.2f} GB",
            'disk_percent': disk.percent,
            'disk_used': f"{disk.used / (1024 * 1024 * 1024):.2f} GB",
            'disk_total': f"{disk.total / (1024 * 1024 * 1024):.2f} GB"
        }
        
        # Informazioni sul bot
        bot_info = {
            'token_configurato': bool(BOT_TOKEN),
            'token_web_configurato': bool(TOKEN_WEB),
            'channel_id': CHANNEL_ID,
            'channel_id_web': CHANNEL_ID_WEB,
            'supabase_configurato': is_supabase_configured()
        }
        
        # Statistiche di utilizzo
        utenti_data = carica_utenti()
        risultati = carica_risultati()
        
        usage_stats = {
            'utenti_autorizzati': len(utenti_data.get("autorizzati", [])),
            'utenti_in_attesa': len(utenti_data.get("in_attesa", [])),
            'partite_registrate': len(risultati),
            'admin_web': len(carica_admin_users())
        }
        
        # Ottieni i log recenti (ultimi 100 eventi)
        log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bot.log')
        recent_logs = []
        
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    # Leggi le ultime 100 righe
                    lines = f.readlines()[-100:]
                    for line in lines:
                        line = line.strip()
                        if line:
                            # Estrai il livello di log (INFO, WARNING, ERROR, ecc.)
                            level = "INFO"
                            if "WARNING" in line:
                                level = "WARNING"
                            elif "ERROR" in line:
                                level = "ERROR"
                            elif "CRITICAL" in line:
                                level = "CRITICAL"
                            elif "DEBUG" in line:
                                level = "DEBUG"
                            
                            recent_logs.append({
                                'timestamp': line.split(' - ')[0] if ' - ' in line else "",
                                'level': level,
                                'message': line
                            })
            except Exception as e:
                app.logger.error(f"Errore nella lettura del file di log: {e}")
                recent_logs.append({
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'level': "ERROR",
                    'message': f"Errore nella lettura del file di log: {str(e)}"
                })
        
        return render_template('monitor.html',
                              system_info=system_info,
                              resources_info=resources_info,
                              bot_info=bot_info,
                              usage_stats=usage_stats,
                              recent_logs=recent_logs)
    except Exception as e:
        app.logger.error(f"Errore nella pagina di monitoraggio: {e}")
        flash(f'Si è verificato un errore durante il caricamento della pagina di monitoraggio: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# Funzione per generare il riepilogo del weekend
def genera_riepilogo_weekend():
    """Genera un riepilogo delle partite del weekend."""
    try:
        # Ottieni i risultati del weekend
        risultati_weekend = ottieni_risultati_weekend()
        
        # Calcola le date del weekend corrente
        oggi = datetime.now()
        # Trova il venerdì precedente
        inizio_weekend = oggi - timedelta(days=(oggi.weekday() + 3) % 7)
        # Trova la domenica successiva
        fine_weekend = inizio_weekend + timedelta(days=2)
        
        inizio_weekend_str = inizio_weekend.strftime("%d/%m/%Y")
        fine_weekend_str = fine_weekend.strftime("%d/%m/%Y")
        
        if not risultati_weekend:
            # Se non ci sono risultati, restituisci solo le date
            app.logger.warning(f"Nessun risultato trovato per il weekend {inizio_weekend_str} - {fine_weekend_str}")
            return inizio_weekend_str, fine_weekend_str, "", []
        
        # Crea il messaggio di riepilogo
        messaggio = f"📊 *RIEPILOGO WEEKEND {inizio_weekend_str} - {fine_weekend_str}*\n\n"
            
        # Raggruppa i risultati per categoria
        risultati_per_categoria = {}
        
        for risultato in risultati_weekend:
            categoria = risultato.get('categoria', 'Altra categoria')
            genere = risultato.get('genere', '')
            chiave = f"{categoria} {genere}".strip()
            
            if chiave not in risultati_per_categoria:
                risultati_per_categoria[chiave] = []
                
            risultati_per_categoria[chiave].append(risultato)
        
        # Aggiungi i risultati al messaggio, raggruppati per categoria
        for categoria, risultati in risultati_per_categoria.items():
            messaggio += f"🏆 *{categoria}*\n"
            for risultato in risultati:
                messaggio += f"• {risultato.get('squadra1', 'N/D')} {risultato.get('punteggio1', 0)} - {risultato.get('punteggio2', 0)} {risultato.get('squadra2', 'N/D')} ({risultato.get('data_partita', 'N/D')})\n"
            messaggio += "\n"
        
        return inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend
    except Exception as e:
        app.logger.error(f"Errore nella generazione del riepilogo weekend: {e}")
        
        # Calcola le date del weekend corrente come fallback
        oggi = datetime.now()
        inizio_weekend = oggi - timedelta(days=(oggi.weekday() + 3) % 7)
        fine_weekend = inizio_weekend + timedelta(days=2)
        
        inizio_weekend_str = inizio_weekend.strftime("%d/%m/%Y")
        fine_weekend_str = fine_weekend.strftime("%d/%m/%Y")
        
        return inizio_weekend_str, fine_weekend_str, "", []

# Rotta per la pagina del riepilogo del weekend
@app.route('/weekend_summary')
@login_required
def weekend_summary():
    try:
        # Genera il riepilogo del weekend
        inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
        
        if not risultati_weekend:
            flash(f'Non ci sono risultati per il weekend {inizio_weekend_str} - {fine_weekend_str}.', 'warning')
            return redirect(url_for('dashboard'))
        
        # Raggruppa i risultati per categoria
        risultati_per_categoria = {}
        for r in risultati_weekend:
            categoria = r.get('categoria', 'Altra categoria')
            genere = r.get('genere', '')
            key = f"{categoria} {genere}".strip()
            
            if key not in risultati_per_categoria:
                risultati_per_categoria[key] = []
              
            risultati_per_categoria[key].append(r)
        
        # Calcola le statistiche
        totale_partite = len(risultati_weekend)
        totale_punti = sum(int(r.get('punteggio1', 0)) + int(r.get('punteggio2', 0)) for r in risultati_weekend)
        totale_mete = sum(int(r.get('mete1', 0)) + int(r.get('mete2', 0)) for r in risultati_weekend)
          
        # Calcola la media di punti e mete per partita
        media_punti = round(totale_punti / totale_partite, 1) if totale_partite > 0 else 0
        media_mete = round(totale_mete / totale_partite, 1) if totale_partite > 0 else 0
          
        # Converti le date in oggetti datetime per la formattazione
        try:
            inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
            fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
        except ValueError as e:
            app.logger.error(f"Errore nella conversione delle date: {e}")
            # Usa date di fallback
            oggi = datetime.now()
            inizio_weekend = oggi - timedelta(days=(oggi.weekday() + 3) % 7)
            fine_weekend = inizio_weekend + timedelta(days=2)
        
        return render_template('weekend_summary.html',
                            inizio_weekend=inizio_weekend,
                            fine_weekend=fine_weekend,
                            risultati_per_categoria=risultati_per_categoria,
                            totale_partite=totale_partite,
                            totale_punti=totale_punti,
                            totale_mete=totale_mete,
                            media_punti=media_punti,
                            media_mete=media_mete)
    except Exception as e:
        app.logger.error(f"Errore nella pagina del riepilogo weekend: {e}")
        flash(f'Si è verificato un errore durante la generazione del riepilogo weekend: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# Funzione asincrona per inviare un file al canale Telegram
async def invia_file_telegram(file_buffer, filename, caption):
    """Invia un file al canale Telegram."""
    # Usa il token dell'interfaccia web se disponibile, altrimenti usa il token del bot principale
    token = TOKEN_WEB or BOT_TOKEN
    channel = CHANNEL_ID_WEB or CHANNEL_ID
    
    if not token:
        return False, "Token del bot Telegram non configurato"
    
    try:
        # Crea un'istanza del bot con un client HTTP separato per evitare conflitti
        bot = telegram.Bot(token=token)
        # Imposta un timeout più breve per evitare blocchi
        await bot.send_document(
            chat_id=channel,
            document=file_buffer,
            filename=filename,
            caption=caption,
            read_timeout=5,
            write_timeout=5,
            connect_timeout=5
        )
        return True, "File inviato con successo"
    except Exception as e:
        return False, str(e)

# Funzione asincrona per inviare un messaggio di testo al canale Telegram
async def invia_messaggio_telegram(messaggio, parse_mode="Markdown"):
    """Invia un messaggio di testo al canale Telegram."""
    # Usa il token dell'interfaccia web se disponibile, altrimenti usa il token del bot principale
    token = TOKEN_WEB or BOT_TOKEN
    channel = CHANNEL_ID_WEB or CHANNEL_ID
    
    if not token:
        return False, "Token del bot Telegram non configurato"
    
    try:
        # Crea un'istanza del bot con un client HTTP separato per evitare conflitti
        bot = telegram.Bot(token=token)
        # Imposta un timeout più breve per evitare blocchi
        await bot.send_message(
            chat_id=channel,
            text=messaggio,
            parse_mode=parse_mode,
            read_timeout=5,
            write_timeout=5,
            connect_timeout=5
        )
        return True, "Messaggio inviato con successo"
    except Exception as e:
        return False, str(e)

# Rotta per esportare il riepilogo del weekend in Excel
@app.route('/export/weekend_excel')
@login_required
def export_weekend_excel():
    try:
        # Genera il riepilogo del weekend
        inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
        
        if not messaggio or not risultati_weekend:
            flash(f'Non ci sono risultati per il weekend {inizio_weekend_str} - {fine_weekend_str}.', 'warning')
            return redirect(url_for('weekend_summary'))
        
        # Genera il file Excel
        excel_buffer = genera_excel_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
        
        # Crea un nome per il file
        inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
        fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
        filename = f"Riepilogo_Rugby_{inizio_weekend.strftime('%d-%m-%Y')}_{fine_weekend.strftime('%d-%m-%Y')}.xlsx"
        
        # Invia il file come risposta
        return send_file(excel_buffer,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name=filename)
    except Exception as e:
        flash(f'Errore durante l\'esportazione in Excel: {str(e)}', 'danger')
        return redirect(url_for('weekend_summary'))

# Rotta per inviare il riepilogo del weekend in Excel al canale Telegram
@app.route('/send/weekend_excel')
@login_required
def send_weekend_excel():
    try:
        # Verifica che l'utente sia un amministratore
        if not current_user.is_admin:
            flash('Solo gli amministratori possono inviare file al canale Telegram.', 'danger')
            return redirect(url_for('weekend_summary'))
        
        # Genera il riepilogo del weekend
        inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
        
        if not messaggio or not risultati_weekend:
            flash(f'Non ci sono risultati per il weekend {inizio_weekend_str} - {fine_weekend_str}.', 'warning')
            return redirect(url_for('weekend_summary'))
        
        # Genera il file Excel
        excel_buffer = genera_excel_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
        
        # Crea un nome per il file
        inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
        fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
        filename = f"Riepilogo_Rugby_{inizio_weekend.strftime('%d-%m-%Y')}_{fine_weekend.strftime('%d-%m-%Y')}.xlsx"
        
        # Crea la didascalia per il file
        caption = f"📊 Riepilogo weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')} in formato Excel"
        
        # Assicurati che il puntatore sia all'inizio del buffer
        excel_buffer.seek(0)
        
        # Leggi il contenuto del buffer
        file_content = excel_buffer.read()
        
        # Crea un nuovo buffer con il contenuto
        from io import BytesIO
        telegram_buffer = BytesIO(file_content)
        
        # Invia il file al canale Telegram
        success, message = asyncio.run(invia_file_telegram(telegram_buffer, filename, caption))
        
        if success:
            flash('File Excel inviato con successo al canale Telegram.', 'success')
        else:
            flash(f'Errore durante l\'invio del file al canale Telegram: {message}', 'danger')
        
        return redirect(url_for('weekend_summary'))
    except Exception as e:
        flash(f'Errore durante l\'invio del file Excel: {str(e)}', 'danger')
        return redirect(url_for('weekend_summary'))

# Rotta per esportare il riepilogo del weekend in PDF
@app.route('/export/weekend_pdf')
@login_required
def export_weekend_pdf():
    try:
        # Genera il riepilogo del weekend
        inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
        
        if not messaggio or not risultati_weekend:
            flash(f'Non ci sono risultati per il weekend {inizio_weekend_str} - {fine_weekend_str}.', 'warning')
            return redirect(url_for('weekend_summary'))
        
        # Genera il file PDF
        pdf_buffer = genera_pdf_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
        
        # Crea un nome per il file
        inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
        fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
        filename = f"Riepilogo_Rugby_{inizio_weekend.strftime('%d-%m-%Y')}_{fine_weekend.strftime('%d-%m-%Y')}.pdf"
        
        # Invia il file come risposta
        return send_file(pdf_buffer,
                         mimetype='application/pdf',
                         as_attachment=True,
                         download_name=filename)
    except Exception as e:
        flash(f'Errore durante l\'esportazione in PDF: {str(e)}', 'danger')
        return redirect(url_for('weekend_summary'))

# Rotta per inviare il riepilogo del weekend in PDF al canale Telegram
@app.route('/send/weekend_pdf')
@login_required
def send_weekend_pdf():
    try:
        # Verifica che l'utente sia un amministratore
        if not current_user.is_admin:
            flash('Solo gli amministratori possono inviare file al canale Telegram.', 'danger')
            return redirect(url_for('weekend_summary'))
        
        # Genera il riepilogo del weekend
        inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
        
        if not messaggio or not risultati_weekend:
            flash(f'Non ci sono risultati per il weekend {inizio_weekend_str} - {fine_weekend_str}.', 'warning')
            return redirect(url_for('weekend_summary'))
        
        # Genera il file PDF
        pdf_buffer = genera_pdf_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
        
        # Crea un nome per il file
        inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
        fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
        filename = f"Riepilogo_Rugby_{inizio_weekend.strftime('%d-%m-%Y')}_{fine_weekend.strftime('%d-%m-%Y')}.pdf"
        
        # Crea la didascalia per il file
        caption = f"📄 Riepilogo weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')} in formato PDF"
        
        # Assicurati che il puntatore sia all'inizio del buffer
        pdf_buffer.seek(0)
        
        # Leggi il contenuto del buffer
        file_content = pdf_buffer.read()
        
        # Crea un nuovo buffer con il contenuto
        from io import BytesIO
        telegram_buffer = BytesIO(file_content)
        
        # Invia il file al canale Telegram
        success, message = asyncio.run(invia_file_telegram(telegram_buffer, filename, caption))
        
        if success:
            flash('File PDF inviato con successo al canale Telegram.', 'success')
        else:
            flash(f'Errore durante l\'invio del file al canale Telegram: {message}', 'danger')
        
        return redirect(url_for('weekend_summary'))
    except Exception as e:
        flash(f'Errore durante l\'invio del file PDF: {str(e)}', 'danger')
        return redirect(url_for('weekend_summary'))

# Rotta per inviare il riepilogo testuale del weekend al canale Telegram
@app.route('/send/weekend_text')
@login_required
def send_weekend_text():
    try:
        # Verifica che l'utente sia un amministratore
        if not current_user.is_admin:
            flash('Solo gli amministratori possono inviare messaggi al canale Telegram.', 'danger')
            return redirect(url_for('weekend_summary'))
        
        # Genera il riepilogo del weekend
        inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
        
        if not messaggio or not risultati_weekend:
            flash(f'Non ci sono risultati per il weekend {inizio_weekend_str} - {fine_weekend_str}.', 'warning')
            return redirect(url_for('weekend_summary'))
        
        # Invia il messaggio al canale Telegram
        success, message = asyncio.run(invia_messaggio_telegram(messaggio))
        
        if success:
            flash('Riepilogo testuale inviato con successo al canale Telegram.', 'success')
        else:
            flash(f'Errore durante l\'invio del messaggio al canale Telegram: {message}', 'danger')
        
        return redirect(url_for('weekend_summary'))
    except Exception as e:
        flash(f'Errore durante l\'invio del riepilogo testuale: {str(e)}', 'danger')
        return redirect(url_for('weekend_summary'))

# Rotta per esportare i dati in Excel
@app.route('/export/excel')
@login_required
def export_excel():
    try:
        # Carica i dati
        risultati = carica_risultati()
        utenti_data = carica_utenti()
        
        # Crea un writer Excel con pandas
        output = pd.ExcelWriter('export_data.xlsx', engine='xlsxwriter')
        
        # Converti i risultati in DataFrame
        df_risultati = pd.DataFrame(risultati)
        
        # Converti gli utenti in DataFrame
        df_utenti_autorizzati = pd.DataFrame(utenti_data["autorizzati"])
        df_utenti_in_attesa = pd.DataFrame(utenti_data["in_attesa"])
        
        # Salva i DataFrame nei fogli Excel
        df_risultati.to_excel(output, sheet_name='Partite', index=False)
        df_utenti_autorizzati.to_excel(output, sheet_name='Utenti Autorizzati', index=False)
        df_utenti_in_attesa.to_excel(output, sheet_name='Utenti in Attesa', index=False)
        
        # Chiudi il writer
        output.close()
        
        # Invia il file come risposta
        return send_file('export_data.xlsx', 
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name='rugby_bot_data.xlsx')
    except Exception as e:
        flash(f'Errore durante l\'esportazione: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# API per ripubblicare una partita su Telegram
@app.route('/api/republish/<int:match_id>', methods=['POST'])
@login_required
def republish_match(match_id):
    try:
        # Carica i risultati
        risultati = carica_risultati()
        
        if 0 <= match_id < len(risultati):
            partita = risultati[match_id]
            
            # Importa le funzioni necessarie
            from telegram import Bot
            import asyncio
            
            # Ottieni il token del bot dal file di configurazione
            from modules.config import TOKEN
            
            # Funzione per inviare il risultato della partita
            async def invia_risultato_partita(bot, dati_partita):
                """Invia il risultato di una partita al canale Telegram."""
                try:
                    # Formatta il messaggio
                    messaggio = f"🏉 *RISULTATO PARTITA*\n\n"
                    messaggio += f"📅 *Data*: {dati_partita.get('data_partita', '')}\n"
                    messaggio += f"🏆 *Categoria*: {dati_partita.get('categoria', '')}\n"
                    if dati_partita.get('genere'):
                        messaggio += f"👥 *Genere*: {dati_partita.get('genere', '')}\n"
                    messaggio += f"\n"
                    messaggio += f"*{dati_partita.get('squadra1', '')}* {dati_partita.get('punteggio1', 0)} - {dati_partita.get('punteggio2', 0)} *{dati_partita.get('squadra2', '')}*\n"
                    messaggio += f"\n"
                    messaggio += f"🏉 *Mete*: {dati_partita.get('mete1', 0)} - {dati_partita.get('mete2', 0)}\n"
                    if dati_partita.get('arbitro'):
                        messaggio += f"👨‍⚖️ *Arbitro*: {dati_partita.get('arbitro', '')}\n"
                    messaggio += f"\n"
                    messaggio += f"👤 Inserito da: {dati_partita.get('inserito_da', '')}"
                    
                    # Invia il messaggio al canale
                    message = await bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=messaggio,
                        parse_mode='Markdown'
                    )
                    return message
                except Exception as e:
                    print(f"Errore nell'invio del risultato: {e}")
                    return None
            
            # Crea un'istanza del bot
            bot = Bot(token=TOKEN)
            
            # Prepara i dati della partita nel formato atteso dalla funzione del bot
            dati_partita = {
                'categoria': partita.get('categoria', ''),
                'genere': partita.get('genere', ''),
                'data_partita': partita.get('data_partita', ''),
                'squadra1': partita.get('squadra1', ''),
                'squadra2': partita.get('squadra2', ''),
                'punteggio1': partita.get('punteggio1', 0),
                'punteggio2': partita.get('punteggio2', 0),
                'mete1': partita.get('mete1', 0),
                'mete2': partita.get('mete2', 0),
                'arbitro': partita.get('arbitro', ''),
                'inserito_da': current_user.username,
                'timestamp': datetime.now().isoformat()
            }
            
            # Crea una funzione asincrona per inviare il messaggio
            async def send_message():
                # Invia il risultato al canale Telegram
                return await invia_risultato_partita(bot, dati_partita)
            
            # Esegui la funzione asincrona
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            message = loop.run_until_complete(send_message())
            loop.close()
            
            # Se l'invio è riuscito, aggiorna il message_id nella partita
            if message:
                # Salva il message_id nella partita
                partita['message_id'] = message.message_id
                salva_risultati(risultati)
                
                # Assicurati che le reazioni siano inizializzate per questo messaggio
                from modules.data_manager import carica_reazioni, salva_reazioni
                
                reazioni = carica_reazioni()
                message_id_str = str(message.message_id)
                if message_id_str not in reazioni:
                    reazioni[message_id_str] = {
                        "like": [],
                        "love": [],
                        "fire": [],
                        "clap": [],
                        "rugby": []
                    }
                    salva_reazioni(reazioni)
                
                return jsonify({"success": True, "message": "Partita ripubblicata con successo sul canale Telegram"})
            else:
                return jsonify({"success": False, "message": "Errore durante l'invio al canale Telegram"}), 500
        else:
            return jsonify({"success": False, "message": "Partita non trovata"}), 404
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        return jsonify({
            "success": False, 
            "message": f"Errore: {str(e)}", 
            "traceback": error_traceback
        }), 500

# API per generare un'immagine condivisibile della partita
@app.route('/api/generate_image/<int:match_id>', methods=['POST'])
@login_required
def generate_match_image(match_id):
    try:
        # Carica i risultati
        risultati = carica_risultati()
        
        if 0 <= match_id < len(risultati):
            partita = risultati[match_id]
            
            # Importa le librerie necessarie per generare l'immagine
            from PIL import Image, ImageDraw, ImageFont
            import io
            import base64
            
            # Crea un'immagine con sfondo bianco
            width, height = 800, 600
            image = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(image)
            
            # Usa i font di default
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            normal_font = ImageFont.load_default()
            big_font = ImageFont.load_default()
            
            # Funzione per centrare il testo
            def draw_centered_text(x, y, text, font, fill="black"):
                try:
                    # Per versioni più recenti di Pillow
                    left, top, right, bottom = font.getbbox(text)
                    text_width = right - left
                    text_height = bottom - top
                except AttributeError:
                    try:
                        # Per versioni intermedie di Pillow
                        text_width, text_height = font.getsize(text)
                    except AttributeError:
                        # Per versioni più vecchie di Pillow
                        text_width, text_height = draw.textsize(text, font=font)
                
                position = (x - text_width // 2, y - text_height // 2)
                draw.text(position, text, font=font, fill=fill)
            
            # Disegna il titolo
            draw_centered_text(width // 2, 40, "Risultato Partita", title_font)
            
            # Disegna la categoria e la data
            categoria_text = f"{partita.get('categoria', '')} {partita.get('genere', '')}"
            draw_centered_text(width // 2, 90, categoria_text, header_font)
            draw_centered_text(width // 2, 130, partita.get('data_partita', ''), normal_font)
            
            # Disegna una linea separatrice
            draw.line([(50, 160), (width-50, 160)], fill="black", width=2)
            
            # Disegna i nomi delle squadre
            draw_centered_text(width // 4, 200, partita.get('squadra1', ''), header_font)
            draw_centered_text(3 * width // 4, 200, partita.get('squadra2', ''), header_font)
            
            # Disegna i punteggi
            draw_centered_text(width // 4, 280, str(partita.get('punteggio1', 0)), big_font)
            draw_centered_text(3 * width // 4, 280, str(partita.get('punteggio2', 0)), big_font)
            
            # Disegna il numero di mete
            draw_centered_text(width // 4, 350, f"Mete: {partita.get('mete1', 0)}", normal_font)
            draw_centered_text(3 * width // 4, 350, f"Mete: {partita.get('mete2', 0)}", normal_font)
            
            # Disegna una linea separatrice
            draw.line([(50, 400), (width-50, 400)], fill="black", width=2)
            
            # Disegna l'arbitro
            draw_centered_text(width // 2, 440, f"Arbitro: {partita.get('arbitro', '')}", normal_font)
            
            # Disegna il footer
            draw_centered_text(width // 2, 500, "Rugby Bot - Risultati in tempo reale", normal_font)
            draw_centered_text(width // 2, 540, "t.me/rugbyresultsbot", normal_font, fill="blue")
            
            # Salva l'immagine in un buffer
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # Converti l'immagine in base64 per inviarla al frontend
            img_str = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            return jsonify({
                "success": True, 
                "message": "Immagine generata con successo",
                "image": img_str
            })
        else:
            return jsonify({"success": False, "message": "Partita non trovata"}), 404
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        return jsonify({
            "success": False, 
            "message": f"Errore: {str(e)}", 
            "traceback": error_traceback
        }), 500

# Rotta per la gestione degli amministratori web
@app.route('/admin_users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Non hai i permessi per accedere a questa pagina!', 'danger')
        return redirect(url_for('dashboard'))
    
    admin_users = carica_admin_users()
    return render_template('admin_users.html', admin_users=admin_users)

# Rotta per aggiungere un nuovo amministratore web
@app.route('/admin_users/add', methods=['GET', 'POST'])
@login_required
def add_admin_user():
    if not current_user.is_admin:
        flash('Non hai i permessi per accedere a questa pagina!', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        is_admin = request.form.get('is_admin') == 'on'
        
        admin_users = carica_admin_users()
        
        # Verifica se l'username è già in uso
        if any(admin['username'] == username for admin in admin_users):
            flash('Username già in uso!', 'danger')
            return render_template('add_admin_user.html')
        
        # Genera un nuovo ID
        new_id = str(max(int(admin['id']) for admin in admin_users) + 1)
        
        # Aggiungi il nuovo admin
        admin_users.append({
            "id": new_id,
            "username": username,
            "password": custom_generate_password_hash(password),
            "is_admin": is_admin
        })
        
        # Salva le modifiche
        salva_admin_users(admin_users)
        
        flash('Amministratore aggiunto con successo!', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('add_admin_user.html')

# Rotta per modificare un amministratore web
@app.route('/admin_users/edit/<string:admin_id>', methods=['GET', 'POST'])
@login_required
def edit_admin_user(admin_id):
    if not current_user.is_admin:
        flash('Non hai i permessi per accedere a questa pagina!', 'danger')
        return redirect(url_for('dashboard'))
    
    admin_users = carica_admin_users()
    admin_to_edit = None
    
    for admin in admin_users:
        if admin['id'] == admin_id:
            admin_to_edit = admin
            break
    
    if not admin_to_edit:
        flash('Amministratore non trovato!', 'danger')
        return redirect(url_for('admin_users'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        is_admin = request.form.get('is_admin') == 'on'
        
        # Verifica se l'username è già in uso da un altro admin
        if any(admin['username'] == username and admin['id'] != admin_id for admin in admin_users):
            flash('Username già in uso!', 'danger')
            return render_template('edit_admin_user.html', admin=admin_to_edit)
        
        # Aggiorna i dati dell'admin
        admin_to_edit['username'] = username
        if password:  # Aggiorna la password solo se fornita
            admin_to_edit['password'] = custom_generate_password_hash(password)
        admin_to_edit['is_admin'] = is_admin
        
        # Salva le modifiche
        salva_admin_users(admin_users)
        
        flash('Amministratore aggiornato con successo!', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('edit_admin_user.html', admin=admin_to_edit)

# Rotta per eliminare un amministratore web
@app.route('/admin_users/delete/<string:admin_id>', methods=['POST'])
@login_required
def delete_admin_user(admin_id):
    if not current_user.is_admin:
        flash('Non hai i permessi per accedere a questa pagina!', 'danger')
        return redirect(url_for('dashboard'))
    
    # Non permettere di eliminare se stesso
    if admin_id == current_user.id:
        flash('Non puoi eliminare il tuo account!', 'danger')
        return redirect(url_for('admin_users'))
    
    admin_users = carica_admin_users()
    
    # Rimuovi l'admin
    admin_users = [admin for admin in admin_users if admin['id'] != admin_id]
    
    # Salva le modifiche
    salva_admin_users(admin_users)
    
    flash('Amministratore eliminato con successo!', 'success')
    return redirect(url_for('admin_users'))

# Rotta per la configurazione di Supabase
@app.route('/supabase_config', methods=['GET', 'POST'])
@login_required
def supabase_config():
    # Verifica che l'utente sia un amministratore
    if not current_user.is_admin:
        flash('Solo gli amministratori possono accedere alla configurazione di Supabase.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Carica le variabili d'ambiente attuali
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    
    # Valori predefiniti
    supabase_url = os.getenv('SUPABASE_URL', '')
    supabase_key = os.getenv('SUPABASE_KEY', '')
    
    if request.method == 'POST':
        # Ottieni i valori dal form
        supabase_url = request.form.get('supabase_url', '')
        supabase_key = request.form.get('supabase_key', '')
        
        # Aggiorna il file .env
        with open(dotenv_path, 'r') as file:
            lines = file.readlines()
        
        with open(dotenv_path, 'w') as file:
            for line in lines:
                if line.startswith('SUPABASE_URL='):
                    file.write(f'SUPABASE_URL={supabase_url}\n')
                elif line.startswith('SUPABASE_KEY='):
                    file.write(f'SUPABASE_KEY={supabase_key}\n')
                else:
                    file.write(line)
        
        # Esegui la migrazione se richiesto
        if 'migrate' in request.form:
            try:
                # Ricarica le variabili d'ambiente
                from dotenv import load_dotenv
                load_dotenv(dotenv_path, override=True)
                
                # Esegui la migrazione
                success = migra_dati_a_supabase()
                
                if success:
                    flash('Configurazione Supabase aggiornata e migrazione completata con successo!', 'success')
                else:
                    flash('Configurazione Supabase aggiornata, ma si è verificato un errore durante la migrazione.', 'warning')
            except Exception as e:
                flash(f'Errore durante la migrazione: {str(e)}', 'danger')
        else:
            flash('Configurazione Supabase aggiornata con successo!', 'success')
        
        return redirect(url_for('supabase_config'))
    
    # Verifica se Supabase è configurato correttamente
    supabase_configured = is_supabase_configured()
    
    return render_template('supabase_config.html', 
                          supabase_url=supabase_url,
                          supabase_key=supabase_key,
                          supabase_configured=supabase_configured)

# Configurazione per l'ambiente serverless
def configure_app_for_lambda():
    """Configura l'app per l'ambiente AWS Lambda."""
    # Imposta il percorso base per le risorse statiche
    if os.environ.get('AWS_EXECUTION_ENV'):
        app.config['APPLICATION_ROOT'] = '/prod'
        app.config['PREFERRED_URL_SCHEME'] = 'https'

# Esegui la configurazione per Lambda
configure_app_for_lambda()

# Migra gli utenti dal vecchio formato al nuovo all'avvio dell'app
migra_utenti_vecchio_formato()

# Configurazione per l'ambiente di produzione
def configure_app_for_production():
    """Configura l'app per l'ambiente di produzione (Render, Heroku, ecc.)."""
    if os.environ.get('RENDER') or os.environ.get('HEROKU_APP_NAME'):
        app.config['APPLICATION_ROOT'] = '/'
        app.config['PREFERRED_URL_SCHEME'] = 'https'

# Esegui la configurazione per l'ambiente di produzione
configure_app_for_production()

# Avvio dell'applicazione
if __name__ == '__main__':
    # Determina la porta da utilizzare (per compatibilità con Render e Heroku)
    port = int(os.environ.get('PORT', 5050))
    
    # Determina l'host da utilizzare
    host = '0.0.0.0' if os.environ.get('RENDER') or os.environ.get('HEROKU_APP_NAME') else 'localhost'
    
    # Avvia l'app
    print(f"Avvio del server web su http://{host}:{port}")
    app.run(debug=False, host=host, port=port, threaded=True)