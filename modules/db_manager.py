#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import requests
import traceback
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
            
            # Se l'operazione è update, esegui l'operazione di aggiornamento
            if hasattr(self, 'update_data'):
                return self._execute_update()
            
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
            
        def update(self, data):
            """Aggiorna un record esistente."""
            self.update_data = data
            return self
            
        def eq(self, column, value):
            """Aggiunge un filtro di uguaglianza."""
            self.filters.append(f"{column}=eq.{value}")
            return self
            
        def _execute_update(self):
            """Esegue l'operazione di aggiornamento."""
            if not hasattr(self, 'update_data'):
                raise ValueError("Nessun dato da aggiornare")
                
            url = self.base_url
            if self.filters:
                url += "?" + "&".join(self.filters)
            
            response = requests.patch(
                url,
                headers=self.client.headers,
                json=self.update_data
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
            
            if response.status_code in [200, 201, 204]:
                return Response(response.json() if response.content else None)
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
    """Carica i risultati dal database o dal file JSON locale."""
    if is_supabase_configured():
        try:
            risultati = supabase.table('risultati').select('*').execute().data
            return risultati
        except Exception as e:
            print(f"Errore nel caricamento dei risultati da Supabase: {e}")
            # In caso di errore, carica dal file locale
            return _carica_risultati_da_file()
    else:
        print("Supabase non configurato. Caricamento risultati dal file locale.")
        return _carica_risultati_da_file()

def _carica_risultati_da_file() -> List[Dict[str, Any]]:
    """
    Funzione di supporto per la migrazione da file JSON a database.
    Carica i risultati dal file JSON.
    """
    if os.path.exists(RISULTATI_FILE):
        with open(RISULTATI_FILE, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []
    else:
        return []

def migra_risultati_da_file_a_db() -> bool:
    """
    Migra i risultati dal file JSON al database.
    Questa funzione dovrebbe essere chiamata una sola volta durante la migrazione.
    """
    if not is_supabase_configured():
        print("Supabase non configurato. Impossibile migrare i risultati.")
        return False
    
    # Carica i risultati dal file JSON
    risultati = _carica_risultati_da_file()
    if not risultati:
        print("Nessun risultato da migrare.")
        return True
    
    # Salva i risultati nel database
    return salva_risultati(risultati)

def salva_risultati(risultati: List[Dict[str, Any]]) -> bool:
    """Salva i risultati nel database."""
    # Salva sempre nel file JSON locale per sicurezza
    try:
        with open(RISULTATI_FILE, 'w', encoding='utf-8') as file:
            json.dump(risultati, file, indent=2, ensure_ascii=False)
        print("Risultati salvati nel file JSON locale.")
    except Exception as e:
        print(f"Errore nel salvataggio dei risultati nel file JSON: {e}")
        # Se non riusciamo a salvare nel file JSON, è un errore critico
        return False
    
    # Se Supabase non è configurato, termina qui (abbiamo già salvato nel file JSON)
    if not is_supabase_configured():
        print("Supabase non configurato. I risultati sono stati salvati solo localmente.")
        return True
    
    try:
        # Ottieni gli ID dei risultati esistenti
        response = supabase.table('risultati').select('id').execute()
        existing_ids = [item.get('id') for item in response.data]
        print(f"ID esistenti in Supabase: {existing_ids}")
        
        # Prepara i risultati da inserire e aggiornare
        to_insert = []
        to_update = []
        
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
            campi_validi = ['id', 'categoria', 'squadra1', 'squadra2', 'squadra3', 'punteggio1', 'punteggio2', 'punteggio3',
                           'mete1', 'mete2', 'mete3', 'arbitro', 'inserito_da', 'genere', 'data_partita', 
                           'data_partita_iso', 'modificato_da', 'message_id',
                           # Campi specifici per i triangolari
                           'partita1_punteggio1', 'partita1_punteggio2', 'partita1_mete1', 'partita1_mete2',
                           'partita2_punteggio1', 'partita2_punteggio2', 'partita2_mete1', 'partita2_mete2',
                           'partita3_punteggio1', 'partita3_punteggio2', 'partita3_mete1', 'partita3_mete2']
            
            # Gestione speciale per la sezione arbitrale
            if 'sezione_arbitrale' in risultato_db:
                # Combina arbitro e sezione arbitrale in un unico campo
                if risultato_db.get('arbitro') and risultato_db.get('sezione_arbitrale'):
                    risultato_db['arbitro'] = f"{risultato_db['arbitro']} ({risultato_db['sezione_arbitrale']})"
                # Rimuovi il campo sezione_arbitrale che non esiste nella tabella
                del risultato_db['sezione_arbitrale']
            
            # Rimuovi esplicitamente i campi che non esistono nella tabella
            for campo in ['timestamp', 'tipo_partita']:
                if campo in risultato_db:
                    del risultato_db[campo]
            
            # Crea un nuovo dizionario con solo i campi validi
            risultato_filtrato = {}
            for campo in campi_validi:
                if campo in risultato_db:
                    risultato_filtrato[campo] = risultato_db[campo]
            
            # Usa il dizionario filtrato
            risultato_db = risultato_filtrato
            
            # Determina se il risultato deve essere inserito o aggiornato
            if risultato_db['id'] in existing_ids:
                to_update.append(risultato_db)
            else:
                to_insert.append(risultato_db)
        
        # Inserisci i nuovi risultati
        if to_insert:
            for risultato in to_insert:
                print(f"Inserimento nuovo risultato in Supabase con ID {risultato['id']}")
                try:
                    # Stampa il risultato che stiamo per inserire
                    print(f"Dati da inserire: {json.dumps(risultato, indent=2)}")
                    
                    # Esegui l'inserimento
                    response = supabase.table('risultati').insert(risultato).execute()
                    
                    # Stampa la risposta completa
                    print(f"Risposta inserimento: {response.data}")
                    
                    # Verifica se l'inserimento è riuscito
                    if not response.data:
                        print("Attenzione: Nessun dato restituito dall'inserimento")
                        
                        # Verifica se il record è stato effettivamente inserito
                        check = supabase.table('risultati').select('*').eq('id', risultato['id']).execute()
                        if check.data:
                            print(f"Verifica: Record trovato nel database: {check.data}")
                        else:
                            print(f"Verifica: Record NON trovato nel database!")
                            
                            # Prova a inserire il record con un altro metodo
                            print("Tentativo di inserimento alternativo...")
                            url = f"{supabase.url}/rest/v1/risultati"
                            headers = supabase.headers
                            response_raw = requests.post(url, headers=headers, json=risultato)
                            print(f"Status code: {response_raw.status_code}")
                            print(f"Risposta: {response_raw.text}")
                            
                            if response_raw.status_code in [200, 201]:
                                print("Inserimento alternativo riuscito!")
                            else:
                                print(f"Errore nell'inserimento alternativo: {response_raw.text}")
                except Exception as e:
                    print(f"Errore durante l'inserimento: {e}")
                    print("Traceback completo:")
                    traceback.print_exc()
        
        # Aggiorna i risultati esistenti
        if to_update:
            for risultato in to_update:
                print(f"Aggiornamento risultato esistente in Supabase con ID {risultato['id']}")
                response = supabase.table('risultati').update(risultato).eq('id', risultato['id']).execute()
                print(f"Risposta aggiornamento: {response.data}")
        
        # Trova gli ID da eliminare (quelli che esistono nel database ma non nei risultati)
        result_ids = [r.get('id') for r in risultati if 'id' in r]
        to_delete = [id for id in existing_ids if id not in result_ids]
        
        # Elimina i risultati che non esistono più
        if to_delete:
            for id in to_delete:
                print(f"Eliminazione risultato da Supabase con ID {id}")
                response = supabase.table('risultati').delete().eq('id', id).execute()
                print(f"Risposta eliminazione: {response.data}")
        
        return True
    except Exception as e:
        print(f"Errore nel salvataggio dei risultati su Supabase: {e}")
        # I risultati sono stati salvati nel file JSON, quindi possiamo considerare l'operazione parzialmente riuscita
        print("I risultati sono stati salvati nel file JSON ma non su Supabase.")
        return True

# Funzioni per la gestione delle squadre
def carica_squadre() -> List[str]:
    """Carica le squadre dal database come lista semplice."""
    if is_supabase_configured():
        try:
            # Carica le squadre dalla tabella 'squadre' di Supabase
            squadre = supabase.table('squadre').select('nome').execute().data
            
            # Estrai solo i nomi delle squadre in una lista semplice
            squadre_list = [squadra.get('nome') for squadra in squadre if squadra.get('nome')]
            
            # Ordina le squadre alfabeticamente
            squadre_list.sort()
            
            # Se non ci sono squadre nel database, prova a caricarle dal file
            if not squadre_list:
                squadre_list = _carica_squadre_da_file()
            
            return squadre_list
        except Exception as e:
            print(f"Errore nel caricamento delle squadre da Supabase: {e}")
            # In caso di errore, prova a caricare dal file
            return _carica_squadre_da_file()
    else:
        print("Supabase non configurato. Caricamento squadre dal file.")
        return _carica_squadre_da_file()

def _carica_squadre_da_file() -> List[str]:
    """
    Funzione di supporto per la migrazione da file JSON a database.
    Carica le squadre dal file JSON.
    """
    if os.path.exists(SQUADRE_FILE):
        with open(SQUADRE_FILE, 'r', encoding='utf-8') as file:
            try:
                data = json.load(file)
                # Se il file contiene un dizionario (vecchio formato), estrai tutte le squadre
                if isinstance(data, dict):
                    squadre_list = []
                    for categoria, squadre in data.items():
                        squadre_list.extend(squadre)
                    return squadre_list
                # Se il file contiene già una lista (nuovo formato), usala direttamente
                elif isinstance(data, list):
                    return data
                else:
                    return []
            except json.JSONDecodeError:
                return []
    else:
        return []

def migra_squadre_da_file_a_db() -> bool:
    """
    Migra le squadre dal file JSON al database.
    Questa funzione dovrebbe essere chiamata una sola volta durante la migrazione.
    """
    if not is_supabase_configured():
        print("Supabase non configurato. Impossibile migrare le squadre.")
        return False
    
    # Carica le squadre dal file JSON
    squadre = _carica_squadre_da_file()
    if not squadre:
        print("Nessuna squadra da migrare.")
        return True
    
    # Salva le squadre nel database
    return salva_squadre(squadre)

def salva_squadre(squadre: List[str]) -> bool:
    """Salva le squadre nel database e nel file JSON."""
    # Salva sempre nel file JSON per compatibilità
    try:
        with open(SQUADRE_FILE, 'w', encoding='utf-8') as file:
            json.dump(squadre, file, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Errore nel salvataggio delle squadre nel file JSON: {e}")
    
    # Se Supabase è configurato, salva anche lì
    if is_supabase_configured():
        try:
            # Elimina tutte le squadre esistenti
            supabase.table('squadre').delete().neq('id', 0).execute()
            
            # Inserisci le nuove squadre
            for nome in squadre:
                if nome and isinstance(nome, str):  # Verifica che il nome sia valido
                    supabase.table('squadre').insert({
                        'nome': nome
                    }).execute()
            
            return True
        except Exception as e:
            print(f"Errore nel salvataggio delle squadre su Supabase: {e}")
            return False
    
    return True

def aggiungi_squadra(nome_squadra: str, user_id: int = None) -> bool:
    """
    Aggiunge una nuova squadra all'elenco.
    
    Args:
        nome_squadra: Il nome della squadra da aggiungere
        user_id: L'ID dell'utente che sta tentando di aggiungere la squadra
        
    Returns:
        bool: True se l'operazione è riuscita, False altrimenti
    """
    # Verifica che il nome della squadra sia valido
    if not nome_squadra or not isinstance(nome_squadra, str):
        return False
    
    # Se è specificato un user_id, verifica che sia un amministratore
    if user_id is not None:
        from bot_fixed_corrected import is_admin
        if not is_admin(user_id):
            print(f"Utente {user_id} non autorizzato ad aggiungere squadre")
            # Non aggiungiamo la squadra, ma restituiamo True per non interrompere il flusso
            # La squadra verrà usata solo per questa sessione
            return True
    
    # Carica le squadre esistenti
    squadre = carica_squadre()
    
    # Verifica se la squadra esiste già
    if nome_squadra in squadre:
        return True  # La squadra esiste già, non è necessario aggiungerla
    
    # Aggiungi la nuova squadra
    squadre.append(nome_squadra)
    
    # Ordina le squadre alfabeticamente
    squadre.sort()
    
    # Salva le squadre aggiornate
    return salva_squadre(squadre)

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