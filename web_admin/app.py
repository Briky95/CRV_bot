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
                              partite_recenti=partite_recenti)
    except Exception as e:
        app.logger.error(f"Errore nella dashboard: {e}")
        flash(f"Si è verificato un errore nel caricamento della dashboard: {str(e)}", "danger")
        # Renderizza una dashboard vuota in caso di errore
        return render_template('dashboard.html', 
                              num_partite=0,
                              num_utenti_autorizzati=0,
                              num_utenti_in_attesa=0,
                              partite_recenti=[])

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
    risultati = carica_risultati()
    
    # Ordina i risultati per data (più recenti prima)
    risultati.sort(key=lambda x: datetime.strptime(x.get('data_partita', '01/01/2000'), '%d/%m/%Y'), reverse=True)
    
    return render_template('matches.html', risultati=risultati)

# Rotta per aggiungere una nuova partita
@app.route('/match/add', methods=['GET', 'POST'])
@login_required
def add_match():
    if request.method == 'POST':
        # Ottieni i dati dal form
        categoria = request.form.get('categoria')
        genere = request.form.get('genere')
        data_partita_raw = request.form.get('data_partita')  # Formato YYYY-MM-DD
        squadra1 = request.form.get('squadra1')
        squadra2 = request.form.get('squadra2')
        punteggio1 = int(request.form.get('punteggio1'))
        punteggio2 = int(request.form.get('punteggio2'))
        mete1 = int(request.form.get('mete1'))
        mete2 = int(request.form.get('mete2'))
        arbitro = request.form.get('arbitro')
        
        # Converti la data nel formato DD/MM/YYYY
        data_partita = datetime.strptime(data_partita_raw, '%Y-%m-%d').strftime('%d/%m/%Y')
        
        # Carica i risultati esistenti
        risultati = carica_risultati()
        
        # Crea il nuovo risultato
        nuovo_risultato = {
            'categoria': categoria,
            'genere': genere,
            'data_partita': data_partita,
            'squadra1': squadra1,
            'squadra2': squadra2,
            'punteggio1': punteggio1,
            'punteggio2': punteggio2,
            'mete1': mete1,
            'mete2': mete2,
            'arbitro': arbitro,
            'inserito_da': current_user.username,
            'timestamp_inserimento': datetime.now().isoformat()
        }
        
        # Aggiungi il nuovo risultato
        risultati.append(nuovo_risultato)
        
        # Salva i risultati
        salva_risultati(risultati)
        
        flash('Partita aggiunta con successo!', 'success')
        return redirect(url_for('matches'))
    
    # Carica le squadre e le categorie per il form
    squadre = carica_squadre()
    categorie = ["Serie A Elite", "Serie A", "Serie B", "Serie C1", "U18 Nazionale", "U18", "U16", "U14"]
    
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
        squadre = carica_squadre()
        categorie = ["Serie A Elite", "Serie A", "Serie B", "Serie C1", "U18 Nazionale", "U18", "U16", "U14"]
        
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
    squadre = carica_squadre()
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
        squadre = carica_squadre()
        
        # Verifica se la squadra esiste già
        if team_name in squadre:
            return jsonify({"success": False, "message": "Squadra già esistente"}), 400
        
        # Aggiungi la nuova squadra
        squadre.append(team_name)
        
        # Salva le squadre
        salva_squadre(squadre)
        
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
        squadre = carica_squadre()
        
        if team_index < 0 or team_index >= len(squadre):
            return jsonify({"success": False, "message": "Indice squadra non valido"}), 400
        
        # Verifica se il nuovo nome esiste già (escludendo la squadra corrente)
        if new_team_name in [s for i, s in enumerate(squadre) if i != team_index]:
            return jsonify({"success": False, "message": "Esiste già una squadra con questo nome"}), 400
        
        # Aggiorna il nome della squadra
        squadre[team_index] = new_team_name
        
        # Salva le squadre
        salva_squadre(squadre)
        
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
        squadre = carica_squadre()
        
        if team_index < 0 or team_index >= len(squadre):
            return jsonify({"success": False, "message": "Indice squadra non valido"}), 400
        
        # Rimuovi la squadra
        squadra_rimossa = squadre.pop(team_index)
        
        # Salva le squadre
        salva_squadre(squadre)
        
        return jsonify({"success": True, "message": f"Squadra '{squadra_rimossa}' eliminata con successo"})
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

# Funzione per generare il riepilogo del weekend
def genera_riepilogo_weekend():
    """Genera un riepilogo delle partite del weekend."""
    # Ottieni i risultati del weekend
    risultati_weekend = ottieni_risultati_weekend()
    
    if not risultati_weekend:
        # Se non ci sono risultati, restituisci solo le date
        oggi = datetime.now()
        # Trova il venerdì precedente
        inizio_weekend = oggi - timedelta(days=(oggi.weekday() + 3) % 7)
        # Trova la domenica successiva
        fine_weekend = inizio_weekend + timedelta(days=2)
        
        inizio_weekend_str = inizio_weekend.strftime("%d/%m/%Y")
        fine_weekend_str = fine_weekend.strftime("%d/%m/%Y")
        
        return inizio_weekend_str, fine_weekend_str, "", []
    
    # Ottieni le date del weekend
    inizio_weekend_str = risultati_weekend[0]["data_partita"]
    fine_weekend_str = risultati_weekend[-1]["data_partita"]
    
    # Crea il messaggio di riepilogo
    messaggio = f"📊 *RIEPILOGO WEEKEND {inizio_weekend_str} - {fine_weekend_str}*\n\n"
    
    # Raggruppa i risultati per categoria
    risultati_per_categoria = {}
    for risultato in risultati_weekend:
        categoria = risultato["categoria"]
        if categoria not in risultati_per_categoria:
            risultati_per_categoria[categoria] = []
        risultati_per_categoria[categoria].append(risultato)
    
    # Aggiungi i risultati al messaggio, raggruppati per categoria
    for categoria, risultati in risultati_per_categoria.items():
        messaggio += f"🏆 *{categoria}*\n"
        for risultato in risultati:
            messaggio += f"• {risultato['squadra1']} {risultato['punteggio1']} - {risultato['punteggio2']} {risultato['squadra2']}\n"
        messaggio += "\n"
    
    return inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend

# Rotta per la pagina del riepilogo del weekend
@app.route('/weekend_summary')
@login_required
def weekend_summary():
    # Genera il riepilogo del weekend
    inizio_weekend_str, fine_weekend_str, messaggio, risultati_weekend = genera_riepilogo_weekend()
    
    if not messaggio:
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
    inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
    fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
    
    return render_template('weekend_summary.html',
                          inizio_weekend=inizio_weekend,
                          fine_weekend=fine_weekend,
                          risultati_per_categoria=risultati_per_categoria,
                          totale_partite=totale_partite,
                          totale_punti=totale_punti,
                          totale_mete=totale_mete,
                          media_punti=media_punti,
                          media_mete=media_mete)

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
        
        # Invia il file al canale Telegram
        success, message = asyncio.run(invia_file_telegram(excel_buffer, filename, caption))
        
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
        
        # Funzione per inviare un file al canale Telegram
        async def invia_file_telegram(file_buffer, filename, caption):
            try:
                # Usa il token dell'interfaccia web se disponibile, altrimenti usa il token del bot principale
                token = TOKEN_WEB or os.environ.get('BOT_TOKEN', '')
                channel = CHANNEL_ID_WEB or CHANNEL_ID
                
                # Crea un'istanza del bot con un client HTTP separato per evitare conflitti
                bot = telegram.Bot(token=token)
                
                # Invia il file al canale con timeout più brevi
                file_buffer.seek(0)
                message = await bot.send_document(
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
        
        # Invia il file al canale Telegram
        success, message = asyncio.run(invia_file_telegram(pdf_buffer, filename, caption))
        
        if success:
            flash('File PDF inviato con successo al canale Telegram.', 'success')
        else:
            flash(f'Errore durante l\'invio del file al canale Telegram: {message}', 'danger')
        
        return redirect(url_for('weekend_summary'))
    except Exception as e:
        flash(f'Errore durante l\'invio del file PDF: {str(e)}', 'danger')
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