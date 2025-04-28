#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dotenv import load_dotenv

# Carica le variabili d'ambiente
load_dotenv()

# Configurazione Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Inizializza il client Supabase
try:
    import requests
    
    # Classe semplificata per interagire con Supabase tramite API REST
    class SupabaseClient:
        def __init__(self, url, key):
            self.url = url
            self.key = key
            self.headers = {
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
        
        def table(self, table_name):
            return SupabaseTable(self, table_name)
    
    # Classe per operazioni su tabelle Supabase
    class SupabaseTable:
        def __init__(self, client, table_name):
            self.client = client
            self.table_name = table_name
            self.base_url = f"{client.url}/rest/v1/{table_name}"
            self.filters = []
            self.select_columns = "*"
        
        def select(self, columns="*"):
            self.select_columns = columns
            return self
        
        def eq(self, column, value):
            self.filters.append(f"{column}=eq.{value}")
            return self
        
        def neq(self, column, value):
            self.filters.append(f"{column}=neq.{value}")
            return self
        
        def execute(self):
            # Se l'operazione è delete, esegui l'operazione di eliminazione
            if hasattr(self, 'operation') and self.operation == "delete":
                return self._execute_delete()
            
            # Altrimenti, esegui l'operazione di selezione (comportamento predefinito)
            url = f"{self.base_url}?select={self.select_columns}"
            if self.filters:
                url += "&" + "&".join(self.filters)
            
            response = requests.get(
                url,
                headers=self.client.headers
            )
            
            class Response:
                def __init__(self, data):
                    self.data = data
                
                def execute(self):
                    # Questo metodo è necessario per mantenere la compatibilità con il codice esistente
                    return self
                
                def neq(self, column, value):
                    # Questo metodo è necessario per mantenere la compatibilità con il codice esistente
                    return self
            
            if response.status_code == 200:
                return Response(response.json())
            return Response([])
        
        def insert(self, data):
            response = requests.post(
                self.base_url,
                headers=self.client.headers,
                json=data
            )
            
            class Response:
                def __init__(self, data):
                    self.data = data
                
                def execute(self):
                    # Questo metodo è necessario per mantenere la compatibilità con il codice esistente
                    return self
                
                def neq(self, column, value):
                    # Questo metodo è necessario per mantenere la compatibilità con il codice esistente
                    return self
            
            if response.status_code in [200, 201]:
                return Response(response.json())
            return Response(None)
        
        def delete(self):
            # Questo metodo è diverso dagli altri: invece di eseguire immediatamente la richiesta,
            # restituisce self per consentire di concatenare altri metodi come neq() ed execute()
            self.operation = "delete"
            return self
            
        def _execute_delete(self):
            url = self.base_url
            if self.filters:
                url += "?" + "&".join(self.filters)
            
            response = requests.delete(
                url,
                headers=self.client.headers
            )
            
            class Response:
                def __init__(self, data):
                    self.data = data
                
                def execute(self):
                    # Questo metodo è necessario per mantenere la compatibilità con il codice esistente
                    return self
                
                def neq(self, column, value):
                    # Questo metodo è necessario per mantenere la compatibilità con il codice esistente
                    return self
            
            return Response(response.status_code in [200, 204])
    
    # Inizializza il client Supabase
    supabase = SupabaseClient(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
except ImportError:
    print("Libreria requests non installata. Utilizzando i file JSON.")
    supabase = None

# Percorsi dei file JSON (per compatibilità e migrazione)
# In AWS Lambda, usa la directory /tmp per i file scrivibili
if os.environ.get('AWS_EXECUTION_ENV'):
    # Siamo in AWS Lambda, usa /tmp
    UTENTI_FILE = '/tmp/utenti.json'
    RISULTATI_FILE = '/tmp/risultati.json'
    SQUADRE_FILE = '/tmp/squadre.json'
    ADMIN_FILE = '/tmp/admin_users.json'
    
    # Copia i file dalla directory principale a /tmp se non esistono già
    for src, dest in [
        (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utenti.json'), UTENTI_FILE),
        (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'risultati.json'), RISULTATI_FILE),
        (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'squadre.json'), SQUADRE_FILE),
        (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'admin_users.json'), ADMIN_FILE)
    ]:
        if os.path.exists(src) and not os.path.exists(dest):
            try:
                import shutil
                shutil.copy2(src, dest)
                print(f"File copiato da {src} a {dest}")
            except Exception as e:
                print(f"Errore nel copiare il file {src} in {dest}: {e}")
else:
    # Ambiente normale, usa i percorsi standard
    UTENTI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utenti.json')
    RISULTATI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'risultati.json')
    SQUADRE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'squadre.json')
    ADMIN_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'admin_users.json')

# Funzione per verificare se Supabase è configurato
def is_supabase_configured() -> bool:
    """Verifica se Supabase è configurato correttamente."""
    return supabase is not None

# Funzioni per la gestione degli utenti
def carica_utenti() -> Dict[str, List]:
    """Carica gli utenti dal database o dal file JSON."""
    if is_supabase_configured():
        try:
            # Carica gli utenti autorizzati
            autorizzati = supabase.table('utenti').select('*').eq('stato', 'autorizzato').execute().data
            
            # Carica gli utenti in attesa
            in_attesa = supabase.table('utenti').select('*').eq('stato', 'in_attesa').execute().data
            
            return {
                "autorizzati": autorizzati,
                "in_attesa": in_attesa
            }
        except Exception as e:
            print(f"Errore nel caricamento degli utenti da Supabase: {e}")
            # Fallback al file JSON
            return _carica_utenti_da_file()
    else:
        return _carica_utenti_da_file()

def _carica_utenti_da_file() -> Dict[str, List]:
    """Carica gli utenti dal file JSON."""
    if os.path.exists(UTENTI_FILE):
        with open(UTENTI_FILE, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {"autorizzati": [], "in_attesa": []}
    else:
        return {"autorizzati": [], "in_attesa": []}

def salva_utenti(utenti_data: Dict[str, List]) -> bool:
    """Salva gli utenti nel database e nel file JSON."""
    # Salva sempre nel file JSON per compatibilità
    with open(UTENTI_FILE, 'w', encoding='utf-8') as file:
        json.dump(utenti_data, file, indent=2, ensure_ascii=False)
    
    if is_supabase_configured():
        try:
            # Elimina tutti gli utenti esistenti
            supabase.table('utenti').delete().neq('id', 0).execute()
            
            # Inserisci gli utenti autorizzati
            for utente in utenti_data["autorizzati"]:
                if isinstance(utente, dict):
                    # Crea una copia dell'utente per non modificare l'originale
                    utente_db = utente.copy()
                    
                    # Converti l'ID in intero se è una stringa
                    if isinstance(utente_db.get('id'), str) and utente_db['id'].isdigit():
                        utente_db['id'] = int(utente_db['id'])
                    
                    # Aggiungi lo stato
                    utente_db['stato'] = 'autorizzato'
                    
                    # Rimuovi il campo data_registrazione e lascia che il database usi il valore predefinito
                    if 'data_registrazione' in utente_db:
                        del utente_db['data_registrazione']
                    
                    # Inserisci l'utente
                    supabase.table('utenti').insert(utente_db).execute()
                else:
                    # Gestisci il vecchio formato (solo ID)
                    supabase.table('utenti').insert({
                        'id': int(utente) if isinstance(utente, str) and utente.isdigit() else utente,
                        'nome': f'Utente {utente}',
                        'username': None,
                        'data_registrazione': datetime.now().isoformat(),
                        'ruolo': 'utente',
                        'stato': 'autorizzato'
                    }).execute()
            
            # Inserisci gli utenti in attesa
            for utente in utenti_data["in_attesa"]:
                if isinstance(utente, dict):
                    # Crea una copia dell'utente per non modificare l'originale
                    utente_db = utente.copy()
                    
                    # Converti l'ID in intero se è una stringa
                    if isinstance(utente_db.get('id'), str) and utente_db['id'].isdigit():
                        utente_db['id'] = int(utente_db['id'])
                    
                    # Aggiungi lo stato
                    utente_db['stato'] = 'in_attesa'
                    
                    # Rimuovi il campo data_registrazione e lascia che il database usi il valore predefinito
                    if 'data_registrazione' in utente_db:
                        del utente_db['data_registrazione']
                    
                    # Inserisci l'utente
                    supabase.table('utenti').insert(utente_db).execute()
                else:
                    # Gestisci il vecchio formato (solo ID)
                    supabase.table('utenti').insert({
                        'id': int(utente) if isinstance(utente, str) and utente.isdigit() else utente,
                        'nome': f'Utente {utente}',
                        'username': None,
                        'data_registrazione': datetime.now().isoformat(),
                        'ruolo': 'utente',
                        'stato': 'in_attesa'
                    }).execute()
            
            return True
        except Exception as e:
            print(f"Errore nel salvataggio degli utenti su Supabase: {e}")
            return False
    
    return True

# Funzioni per la gestione dei risultati
def carica_risultati() -> List[Dict[str, Any]]:
    """Carica i risultati dal database o dal file JSON."""
    if is_supabase_configured():
        try:
            risultati = supabase.table('risultati').select('*').execute().data
            return risultati
        except Exception as e:
            print(f"Errore nel caricamento dei risultati da Supabase: {e}")
            # Fallback al file JSON
            return _carica_risultati_da_file()
    else:
        return _carica_risultati_da_file()

def _carica_risultati_da_file() -> List[Dict[str, Any]]:
    """Carica i risultati dal file JSON."""
    if os.path.exists(RISULTATI_FILE):
        with open(RISULTATI_FILE, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []
    else:
        return []

def salva_risultati(risultati: List[Dict[str, Any]]) -> bool:
    """Salva i risultati nel database e nel file JSON."""
    # Salva sempre nel file JSON per compatibilità
    with open(RISULTATI_FILE, 'w', encoding='utf-8') as file:
        json.dump(risultati, file, indent=2, ensure_ascii=False)
    
    if is_supabase_configured():
        try:
            # Per semplicità, non eliminiamo i risultati esistenti
            
            # Inserisci i nuovi risultati
            for i, risultato in enumerate(risultati):
                # Crea una copia del risultato per non modificare l'originale
                risultato_db = risultato.copy()
                
                # Aggiungi un ID se non esiste
                if 'id' not in risultato_db:
                    risultato_db['id'] = i + 1
                
                # Converti le date nel formato ISO
                if 'data_partita' in risultato_db and risultato_db['data_partita']:
                    try:
                        data = datetime.strptime(risultato_db['data_partita'], '%d/%m/%Y')
                        risultato_db['data_partita_iso'] = data.isoformat()
                    except ValueError:
                        risultato_db['data_partita_iso'] = None
                
                # Rimuovi il campo timestamp_modifica e lascia che il database usi il valore predefinito
                if 'timestamp_modifica' in risultato_db:
                    del risultato_db['timestamp_modifica']
                
                # Mantieni solo i campi che sappiamo esistere nella tabella
                campi_validi = ['id', 'categoria', 'squadra1', 'squadra2', 'punteggio1', 'punteggio2', 
                               'mete1', 'mete2', 'arbitro', 'inserito_da', 'genere', 'data_partita', 
                               'data_partita_iso', 'modificato_da', 'message_id']
                
                # Crea un nuovo dizionario con solo i campi validi
                risultato_filtrato = {}
                for campo in campi_validi:
                    if campo in risultato_db:
                        risultato_filtrato[campo] = risultato_db[campo]
                
                # Usa il dizionario filtrato
                risultato_db = risultato_filtrato
                
                # Inserisci il risultato
                supabase.table('risultati').insert(risultato_db).execute()
            
            return True
        except Exception as e:
            print(f"Errore nel salvataggio dei risultati su Supabase: {e}")
            return False
    
    return True

# Funzioni per la gestione delle squadre
def carica_squadre() -> Dict[str, List[str]]:
    """Carica le squadre dal database o dal file JSON."""
    if is_supabase_configured():
        try:
            squadre = supabase.table('squadre').select('*').execute().data
            
            # Organizza le squadre per categoria
            squadre_per_categoria = {}
            for squadra in squadre:
                categoria = squadra.get('categoria', 'Altra categoria')
                if categoria not in squadre_per_categoria:
                    squadre_per_categoria[categoria] = []
                
                squadre_per_categoria[categoria].append(squadra.get('nome'))
            
            return squadre_per_categoria
        except Exception as e:
            print(f"Errore nel caricamento delle squadre da Supabase: {e}")
            # Fallback al file JSON
            return _carica_squadre_da_file()
    else:
        return _carica_squadre_da_file()

def _carica_squadre_da_file() -> Dict[str, List[str]]:
    """Carica le squadre dal file JSON."""
    if os.path.exists(SQUADRE_FILE):
        with open(SQUADRE_FILE, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    else:
        return {}

def salva_squadre(squadre: Dict[str, List[str]]) -> bool:
    """Salva le squadre nel database e nel file JSON."""
    # Salva sempre nel file JSON per compatibilità
    with open(SQUADRE_FILE, 'w', encoding='utf-8') as file:
        json.dump(squadre, file, indent=2, ensure_ascii=False)
    
    if is_supabase_configured():
        try:
            # Elimina tutte le squadre esistenti
            supabase.table('squadre').delete().neq('id', 0).execute()
            
            # Inserisci le nuove squadre
            for categoria, nomi_squadre in squadre.items():
                for nome in nomi_squadre:
                    supabase.table('squadre').insert({
                        'nome': nome,
                        'categoria': categoria
                    }).execute()
            
            return True
        except Exception as e:
            print(f"Errore nel salvataggio delle squadre su Supabase: {e}")
            return False
    
    return True

# Funzioni per la gestione degli amministratori
def carica_admin_users() -> List[Dict[str, Any]]:
    """Carica gli amministratori dal database o dal file JSON."""
    if is_supabase_configured():
        try:
            response = supabase.table('admin_users').select('*').execute()
            return response.data
        except Exception as e:
            print(f"Errore nel caricamento degli amministratori da Supabase: {e}")
            # Fallback al file JSON
            return _carica_admin_users_da_file()
    else:
        return _carica_admin_users_da_file()

def _carica_admin_users_da_file() -> List[Dict[str, Any]]:
    """Carica gli amministratori dal file JSON."""
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
            "password": "sha256$16e893a4c1c6c3a8$6a4b9e29a6a9a2f8e2a9e6a4b9e29a6a9a2f8e2a9e6a4b9e29a6a9a2f8e2a9e",  # admin123
            "is_admin": True
        }]
        with open(ADMIN_FILE, 'w', encoding='utf-8') as file:
            json.dump(admin_default, file, indent=2)
        return admin_default

def salva_admin_users(admin_users: List[Dict[str, Any]]) -> bool:
    """Salva gli amministratori nel database e nel file JSON."""
    # Salva sempre nel file JSON per compatibilità
    with open(ADMIN_FILE, 'w', encoding='utf-8') as file:
        json.dump(admin_users, file, indent=2, ensure_ascii=False)
    
    if is_supabase_configured():
        try:
            # Elimina tutti gli amministratori esistenti
            supabase.table('admin_users').delete().neq('id', 0).execute()
            
            # Inserisci i nuovi amministratori
            for admin in admin_users:
                supabase.table('admin_users').insert(admin).execute()
            
            return True
        except Exception as e:
            print(f"Errore nel salvataggio degli amministratori su Supabase: {e}")
            return False
    
    return True

# Funzione per migrare tutti i dati dai file JSON a Supabase
def migra_dati_a_supabase() -> bool:
    """Migra tutti i dati dai file JSON a Supabase."""
    if not is_supabase_configured():
        print("Supabase non è configurato. Impossibile migrare i dati.")
        return False
    
    try:
        # Migra gli utenti
        utenti = _carica_utenti_da_file()
        salva_utenti(utenti)
        
        # Migra i risultati
        risultati = _carica_risultati_da_file()
        salva_risultati(risultati)
        
        # Migra le squadre
        squadre = _carica_squadre_da_file()
        salva_squadre(squadre)
        
        # Migra gli amministratori
        admin_users = _carica_admin_users_da_file()
        salva_admin_users(admin_users)
        
        print("Migrazione dei dati a Supabase completata con successo.")
        return True
    except Exception as e:
        print(f"Errore durante la migrazione dei dati a Supabase: {e}")
        return False

# Funzione principale per testare il modulo
if __name__ == "__main__":
    # Verifica se Supabase è configurato
    if is_supabase_configured():
        print("Supabase è configurato correttamente.")
        
        # Migra i dati a Supabase
        migra_dati_a_supabase()
    else:
        print("Supabase non è configurato. Utilizzando i file JSON.")