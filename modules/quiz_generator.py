#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import os
import random
import requests
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

# Configurazione logging
logger = logging.getLogger(__name__)

# Carica le variabili d'ambiente
from dotenv import load_dotenv
load_dotenv()

# Chiavi API per i servizi di AI (da configurare nel file .env)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Aggiungi questa chiave al file .env

# Flag per indicare quale servizio utilizzare
USE_GEMINI = os.getenv("USE_GEMINI", "false").lower() == "true"

# File per i quiz in attesa di approvazione
QUIZ_PENDING_FILE = "data/quiz_pending.json"

# Categorie disponibili per i quiz
QUIZ_CATEGORIES = [
    "Regole del Rugby",
    "Storia del Rugby",
    "Tecnica e Tattica",
    "Rugby Veneto",
    "Giocatori Famosi",
    "Competizioni Internazionali",
    "Curiosità sul Rugby"
]

def initialize_pending_quiz_file():
    """Inizializza il file dei quiz in attesa di approvazione se non esiste."""
    if not os.path.exists(os.path.dirname(QUIZ_PENDING_FILE)):
        os.makedirs(os.path.dirname(QUIZ_PENDING_FILE))
    
    if not os.path.exists(QUIZ_PENDING_FILE):
        with open(QUIZ_PENDING_FILE, "w", encoding="utf-8") as file:
            json.dump({
                "quiz_pending": [],
                "last_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, file, ensure_ascii=False, indent=4)
        
        logger.info("File quiz in attesa inizializzato")

def load_pending_quizzes() -> Dict[str, Any]:
    """Carica i quiz in attesa di approvazione."""
    initialize_pending_quiz_file()
    
    try:
        with open(QUIZ_PENDING_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            
            # Verifica che il formato del file sia corretto
            if not isinstance(data, dict):
                logger.error(f"Il file dei quiz in attesa non contiene un dizionario: {type(data)}")
                data = {"quiz_pending": [], "last_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                save_pending_quizzes(data)
            
            # Verifica che quiz_pending sia presente e sia una lista
            if "quiz_pending" not in data:
                logger.error("Il file dei quiz in attesa non contiene la chiave 'quiz_pending'")
                data["quiz_pending"] = []
            elif not isinstance(data["quiz_pending"], list):
                logger.error(f"quiz_pending non è una lista: {type(data['quiz_pending'])}")
                data["quiz_pending"] = []
            
            # Verifica che last_generated sia presente
            if "last_generated" not in data:
                data["last_generated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return data
    except json.JSONDecodeError as e:
        logger.error(f"Errore nella decodifica del file JSON dei quiz in attesa: {e}")
        # Il file è corrotto, lo reiniziamo
        data = {"quiz_pending": [], "last_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        save_pending_quizzes(data)
        return data
    except Exception as e:
        logger.error(f"Errore nel caricamento dei quiz in attesa: {e}")
        return {"quiz_pending": [], "last_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

def save_pending_quizzes(data: Dict[str, Any]) -> bool:
    """Salva i quiz in attesa di approvazione."""
    try:
        # Verifica che data sia un dizionario
        if not isinstance(data, dict):
            logger.error(f"I dati da salvare non sono un dizionario: {type(data)}")
            data = {"quiz_pending": [], "last_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        
        # Verifica che quiz_pending sia presente e sia una lista
        if "quiz_pending" not in data:
            logger.error("I dati da salvare non contengono la chiave 'quiz_pending'")
            data["quiz_pending"] = []
        elif not isinstance(data["quiz_pending"], list):
            logger.error(f"quiz_pending non è una lista: {type(data['quiz_pending'])}")
            data["quiz_pending"] = []
        
        # Verifica che last_generated sia presente
        if "last_generated" not in data:
            data["last_generated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Crea la directory se non esiste
        os.makedirs(os.path.dirname(QUIZ_PENDING_FILE), exist_ok=True)
        
        # Salva i dati
        with open(QUIZ_PENDING_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        
        logger.info(f"Salvati {len(data['quiz_pending'])} quiz in attesa")
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei quiz in attesa: {e}")
        return False

def generate_sample_quiz(category: str = None) -> Dict[str, Any]:
    """Genera un quiz di esempio quando l'API di OpenAI non è disponibile."""
    # Seleziona una categoria casuale se non specificata
    if not category:
        category = random.choice(QUIZ_CATEGORIES)
    
    # Dizionario di quiz di esempio per categoria (ampliato con più opzioni per ogni categoria)
    sample_quizzes = {
        "Regole del Rugby": [
            {
                "categoria": "Regole del Rugby",
                "domanda": "Quanti giocatori compongono una squadra di rugby a 15?",
                "opzioni": ["13 giocatori", "15 giocatori", "11 giocatori", "17 giocatori"],
                "risposta_corretta": 1,
                "spiegazione": "Una squadra di rugby a 15 è composta da 15 giocatori in campo. Ci sono 8 avanti (o 'forwards') e 7 trequarti (o 'backs'). Ogni squadra può anche avere fino a 8 giocatori di riserva."
            },
            {
                "categoria": "Regole del Rugby",
                "domanda": "Quanto dura una partita di rugby a 15?",
                "opzioni": ["60 minuti", "70 minuti", "80 minuti", "90 minuti"],
                "risposta_corretta": 2,
                "spiegazione": "Una partita di rugby a 15 dura 80 minuti, divisi in due tempi da 40 minuti ciascuno con un intervallo di 10-15 minuti tra i due tempi."
            },
            {
                "categoria": "Regole del Rugby",
                "domanda": "Quanti punti vale una meta nel rugby?",
                "opzioni": ["3 punti", "5 punti", "7 punti", "10 punti"],
                "risposta_corretta": 1,
                "spiegazione": "Una meta nel rugby vale 5 punti. Dopo una meta, la squadra ha la possibilità di calciare per la trasformazione che vale ulteriori 2 punti."
            }
        ],
        "Storia del Rugby": [
            {
                "categoria": "Storia del Rugby",
                "domanda": "In quale paese è nato il rugby?",
                "opzioni": ["Francia", "Nuova Zelanda", "Inghilterra", "Australia"],
                "risposta_corretta": 2,
                "spiegazione": "Il rugby è nato in Inghilterra. Secondo la leggenda, il gioco è nato nel 1823 quando William Webb Ellis, uno studente della Rugby School, prese la palla durante una partita di calcio e corse con essa in mano, creando così un nuovo sport."
            },
            {
                "categoria": "Storia del Rugby",
                "domanda": "In che anno si è disputata la prima Coppa del Mondo di rugby?",
                "opzioni": ["1975", "1987", "1991", "1995"],
                "risposta_corretta": 1,
                "spiegazione": "La prima Coppa del Mondo di rugby si è disputata nel 1987, organizzata congiuntamente da Australia e Nuova Zelanda. La Nuova Zelanda vinse il torneo battendo la Francia in finale."
            },
            {
                "categoria": "Storia del Rugby",
                "domanda": "Quale squadra ha vinto più Coppe del Mondo di rugby?",
                "opzioni": ["Australia", "Nuova Zelanda", "Sudafrica", "Inghilterra"],
                "risposta_corretta": 1,
                "spiegazione": "La Nuova Zelanda (All Blacks) ha vinto più Coppe del Mondo di rugby, con tre vittorie (1987, 2011 e 2015). Il Sudafrica ha vinto tre volte (1995, 2007 e 2019), l'Australia due volte (1991 e 1999) e l'Inghilterra una volta (2003)."
            }
        ],
        "Tecnica e Tattica": [
            {
                "categoria": "Tecnica e Tattica",
                "domanda": "Cosa si intende per 'ruck' nel rugby?",
                "opzioni": ["Un tipo di calcio", "Una formazione di gioco", "Una fase di gioco dopo un placcaggio", "Un fallo di gioco"],
                "risposta_corretta": 2,
                "spiegazione": "Il ruck è una fase di gioco che si forma dopo un placcaggio quando uno o più giocatori di ciascuna squadra sono in piedi e in contatto fisico, chiudendosi attorno alla palla a terra. I giocatori devono usare i piedi per conquistare o mantenere il possesso della palla."
            },
            {
                "categoria": "Tecnica e Tattica",
                "domanda": "Cosa si intende per 'maul' nel rugby?",
                "opzioni": ["Un tipo di calcio", "Una formazione di gioco statica", "Un giocatore placcato a terra", "Un fallo di gioco"],
                "risposta_corretta": 1,
                "spiegazione": "Il maul è una formazione di gioco statica che si crea quando un giocatore in possesso della palla è trattenuto da uno o più avversari, e uno o più compagni di squadra si legano al portatore della palla. La palla non deve toccare terra e il maul deve muoversi verso una linea di meta."
            },
            {
                "categoria": "Tecnica e Tattica",
                "domanda": "Quale di queste non è una posizione nel rugby a 15?",
                "opzioni": ["Pilone", "Mediano di mischia", "Ala", "Libero"],
                "risposta_corretta": 3,
                "spiegazione": "Il 'Libero' non è una posizione nel rugby a 15. Le posizioni tradizionali includono: piloni, tallonatore, seconde linee, flanker, numero 8, mediano di mischia, mediano d'apertura, centri, ali e estremo."
            }
        ],
        "Rugby Veneto": [
            {
                "categoria": "Rugby Veneto",
                "domanda": "Quale squadra veneta ha vinto più scudetti nel rugby italiano?",
                "opzioni": ["Petrarca Rugby", "Benetton Rugby Treviso", "Rugby Rovigo", "Rugby San Donà"],
                "risposta_corretta": 2,
                "spiegazione": "Il Rugby Rovigo è la squadra veneta con più scudetti nel rugby italiano. Conosciuti come 'Bersaglieri', hanno una lunga tradizione nel rugby italiano e rappresentano una delle città con maggiore passione per questo sport in Italia."
            },
            {
                "categoria": "Rugby Veneto",
                "domanda": "Quale città veneta ospita una squadra che partecipa al campionato United Rugby Championship?",
                "opzioni": ["Padova", "Rovigo", "Treviso", "Verona"],
                "risposta_corretta": 2,
                "spiegazione": "Treviso, con la squadra Benetton Rugby, partecipa al campionato United Rugby Championship (ex Pro14), competizione internazionale che include squadre da Italia, Irlanda, Galles, Scozia e Sudafrica."
            },
            {
                "categoria": "Rugby Veneto",
                "domanda": "Quale di queste squadre venete non ha mai vinto il campionato italiano di rugby?",
                "opzioni": ["Petrarca Rugby", "Benetton Rugby", "Rugby San Donà", "Rugby Rovigo"],
                "risposta_corretta": 2,
                "spiegazione": "Il Rugby San Donà non ha mai vinto il campionato italiano di rugby. Petrarca Rugby (Padova), Benetton Rugby (Treviso) e Rugby Rovigo hanno invece vinto più volte il titolo nazionale."
            }
        ],
        "Giocatori Famosi": [
            {
                "categoria": "Giocatori Famosi",
                "domanda": "Chi è il giocatore che ha segnato più mete nella storia della Coppa del Mondo di rugby?",
                "opzioni": ["Jonah Lomu", "Bryan Habana", "Doug Howlett", "Shane Williams"],
                "risposta_corretta": 1,
                "spiegazione": "Bryan Habana, ex ala sudafricana, detiene il record di mete segnate nella Coppa del Mondo di rugby insieme a Jonah Lomu, entrambi con 15 mete. Habana ha raggiunto questo record nel 2015, eguagliando il primato stabilito dalla leggenda neozelandese Lomu."
            },
            {
                "categoria": "Giocatori Famosi",
                "domanda": "Quale giocatore italiano ha disputato più partite con la nazionale di rugby?",
                "opzioni": ["Sergio Parisse", "Martin Castrogiovanni", "Alessandro Zanni", "Leonardo Ghiraldini"],
                "risposta_corretta": 0,
                "spiegazione": "Sergio Parisse detiene il record di presenze con la nazionale italiana di rugby, con oltre 140 caps. È considerato uno dei migliori numeri 8 al mondo e ha giocato in diversi club prestigiosi, tra cui lo Stade Français."
            },
            {
                "categoria": "Giocatori Famosi",
                "domanda": "Chi è stato nominato 'World Rugby Player of the Year' più volte?",
                "opzioni": ["Jonny Wilkinson", "Richie McCaw", "Dan Carter", "Brian O'Driscoll"],
                "risposta_corretta": 1,
                "spiegazione": "Richie McCaw, ex capitano degli All Blacks, è stato nominato 'World Rugby Player of the Year' tre volte (2006, 2009 e 2010), più di qualsiasi altro giocatore. Ha guidato la Nuova Zelanda alla vittoria in due Coppe del Mondo consecutive (2011 e 2015)."
            }
        ],
        "Competizioni Internazionali": [
            {
                "categoria": "Competizioni Internazionali",
                "domanda": "Quale nazione ha vinto più edizioni del Sei Nazioni (includendo il Cinque Nazioni)?",
                "opzioni": ["Inghilterra", "Galles", "Francia", "Irlanda"],
                "risposta_corretta": 1,
                "spiegazione": "Il Galles ha vinto più edizioni del Sei Nazioni (includendo il Cinque Nazioni e le precedenti versioni del torneo). Il torneo è una delle competizioni più antiche e prestigiose del rugby, iniziato nel 1883 come Home Nations Championship tra le quattro nazioni britanniche."
            },
            {
                "categoria": "Competizioni Internazionali",
                "domanda": "Quale trofeo viene assegnato alla squadra vincitrice della Coppa del Mondo di rugby?",
                "opzioni": ["Coppa Webb Ellis", "Trofeo Calcutta", "Six Nations Trophy", "Rugby Championship Trophy"],
                "risposta_corretta": 0,
                "spiegazione": "La Coppa Webb Ellis viene assegnata alla squadra vincitrice della Coppa del Mondo di rugby. Il nome del trofeo è un omaggio a William Webb Ellis, a cui viene attribuita l'invenzione del rugby."
            },
            {
                "categoria": "Competizioni Internazionali",
                "domanda": "Quale competizione ha sostituito il Tri Nations nel rugby dell'emisfero sud?",
                "opzioni": ["Super Rugby", "Rugby Championship", "Pacific Nations Cup", "Rugby World Cup"],
                "risposta_corretta": 1,
                "spiegazione": "Il Rugby Championship ha sostituito il Tri Nations nel 2012, quando l'Argentina si è unita a Nuova Zelanda, Australia e Sudafrica. In precedenza, il Tri Nations era disputato solo dalle tre nazioni dell'emisfero sud dal 1996."
            }
        ],
        "Curiosità sul Rugby": [
            {
                "categoria": "Curiosità sul Rugby",
                "domanda": "Quale oggetto viene tradizionalmente consegnato al giocatore che fa il suo debutto nella nazionale neozelandese (All Blacks)?",
                "opzioni": ["Una felce d'argento", "Un cappello nero", "Una maglia speciale", "Un primo cap"],
                "risposta_corretta": 0,
                "spiegazione": "Ai giocatori che fanno il loro debutto con gli All Blacks viene tradizionalmente consegnata una felce d'argento. Questo simbolo è molto importante nella cultura neozelandese e rappresenta l'onore di indossare la maglia nera della nazionale."
            },
            {
                "categoria": "Curiosità sul Rugby",
                "domanda": "Quale danza tradizionale eseguono gli All Blacks prima delle partite?",
                "opzioni": ["Siva Tau", "Cibi", "Haka", "Sipi Tau"],
                "risposta_corretta": 2,
                "spiegazione": "Gli All Blacks eseguono l'Haka, una danza tradizionale maori, prima delle partite. Esistono diverse versioni dell'Haka, ma quella più comunemente eseguita è la 'Ka Mate'. Altre nazionali del Pacifico hanno danze simili: Samoa esegue il Siva Tau, Fiji il Cibi e Tonga il Sipi Tau."
            },
            {
                "categoria": "Curiosità sul Rugby",
                "domanda": "Quale nazione ha la percentuale più alta di vittorie nella storia del rugby internazionale?",
                "opzioni": ["Sudafrica", "Nuova Zelanda", "Inghilterra", "Australia"],
                "risposta_corretta": 1,
                "spiegazione": "La Nuova Zelanda (All Blacks) ha la percentuale più alta di vittorie nella storia del rugby internazionale, con oltre il 75% di partite vinte. Questo li rende una delle squadre sportive di maggior successo in qualsiasi sport a livello mondiale."
            }
        ]
    }
    
    # Seleziona un quiz dalla categoria specificata o uno casuale se la categoria non è disponibile
    if category in sample_quizzes:
        # Seleziona un quiz casuale dalla lista di quiz disponibili per quella categoria
        quiz = dict(random.choice(sample_quizzes[category]))  # Crea una copia del dizionario
    else:
        # Seleziona una categoria casuale e poi un quiz casuale da quella categoria
        random_category = random.choice(list(sample_quizzes.keys()))
        quiz = dict(random.choice(sample_quizzes[random_category]))  # Crea una copia del dizionario
    
    # Aggiungi la data di generazione e un indicatore che è un quiz di esempio
    quiz["generato_il"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    quiz["nota"] = "Quiz di esempio generato in modalità offline"
    
    # Verifica che il quiz contenga tutti i campi necessari
    required_fields = ["categoria", "domanda", "opzioni", "risposta_corretta", "spiegazione"]
    for field in required_fields:
        if field not in quiz:
            logger.error(f"Campo mancante nel quiz di esempio: {field}")
            # Aggiungi un valore predefinito
            if field == "categoria":
                quiz[field] = category or "Regole del Rugby"
            elif field == "domanda":
                quiz[field] = "Domanda di esempio"
            elif field == "opzioni":
                quiz[field] = ["Opzione A", "Opzione B", "Opzione C", "Opzione D"]
            elif field == "risposta_corretta":
                quiz[field] = 0
            elif field == "spiegazione":
                quiz[field] = "Spiegazione di esempio"
    
    # Verifica che ci siano esattamente 4 opzioni
    if len(quiz["opzioni"]) != 4:
        logger.warning(f"Numero errato di opzioni nel quiz di esempio: {len(quiz['opzioni'])}")
        # Aggiungi opzioni mancanti o rimuovi quelle in eccesso
        while len(quiz["opzioni"]) < 4:
            quiz["opzioni"].append(f"Opzione {len(quiz['opzioni']) + 1}")
        quiz["opzioni"] = quiz["opzioni"][:4]
    
    # Verifica che l'indice della risposta corretta sia valido
    if not (0 <= quiz["risposta_corretta"] <= 3):
        logger.warning(f"Indice risposta corretta non valido nel quiz di esempio: {quiz['risposta_corretta']}")
        quiz["risposta_corretta"] = 0
    
    return quiz

def generate_quiz_with_openai(category: str = None) -> Optional[Dict[str, Any]]:
    """Genera un nuovo quiz utilizzando l'API di OpenAI o un quiz di esempio se l'API non è disponibile."""
    if not OPENAI_API_KEY:
        logger.warning("Chiave API OpenAI non configurata, utilizzo modalità offline")
        return generate_sample_quiz(category)
    
    # Se non è specificata una categoria, ne scegliamo una casuale
    if not category:
        category = random.choice(QUIZ_CATEGORIES)
    
    # Prepara il prompt per l'API
    prompt = f"""Genera un quiz educativo sul rugby nella categoria '{category}'.
Il quiz deve avere:
1. Una domanda chiara e precisa
2. Quattro opzioni di risposta (A, B, C, D)
3. L'indice della risposta corretta (0 per A, 1 per B, 2 per C, 3 per D)
4. Una spiegazione dettagliata della risposta corretta

Restituisci il risultato in formato JSON con i seguenti campi:
{{
  "categoria": "{category}",
  "domanda": "La domanda del quiz",
  "opzioni": ["Opzione A", "Opzione B", "Opzione C", "Opzione D"],
  "risposta_corretta": 0,
  "spiegazione": "Spiegazione dettagliata della risposta corretta"
}}

Assicurati che:
- La domanda sia interessante e educativa
- Le opzioni siano plausibili ma solo una sia corretta
- La spiegazione sia informativa e approfondita
- Il JSON sia valido e ben formattato
"""

    try:
        # Chiamata all'API di OpenAI con timeout
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "Sei un esperto di rugby che crea quiz educativi accurati e interessanti."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 800
        }
        
        # Aggiungi un timeout di 10 secondi per evitare blocchi
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10  # Timeout di 10 secondi
        )
        
        if response.status_code != 200:
            logger.error(f"Errore nella chiamata API: {response.status_code} - {response.text}")
            logger.info("Utilizzo modalità offline per generare un quiz di esempio")
            return generate_sample_quiz(category)
        
        # Estrai il contenuto della risposta
        response_data = response.json()
        content = response_data["choices"][0]["message"]["content"]
        
        # Estrai il JSON dalla risposta
        import re
        json_match = re.search(r'({.*})', content, re.DOTALL)
        if not json_match:
            logger.error("Impossibile estrarre JSON dalla risposta")
            return generate_sample_quiz(category)
        
        json_str = json_match.group(1)
        quiz_data = json.loads(json_str)
        
        # Verifica che il quiz contenga tutti i campi necessari
        required_fields = ["categoria", "domanda", "opzioni", "risposta_corretta", "spiegazione"]
        for field in required_fields:
            if field not in quiz_data:
                logger.error(f"Campo mancante nel quiz generato: {field}")
                return generate_sample_quiz(category)
        
        # Verifica che ci siano esattamente 4 opzioni
        if len(quiz_data["opzioni"]) != 4:
            logger.error(f"Numero errato di opzioni: {len(quiz_data['opzioni'])}")
            return generate_sample_quiz(category)
        
        # Verifica che l'indice della risposta corretta sia valido
        if not (0 <= quiz_data["risposta_corretta"] <= 3):
            logger.error(f"Indice risposta corretta non valido: {quiz_data['risposta_corretta']}")
            return generate_sample_quiz(category)
        
        # Aggiungi un timestamp di generazione
        quiz_data["generato_il"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return quiz_data
    
    except Exception as e:
        logger.error(f"Errore nella generazione del quiz: {e}")
        return generate_sample_quiz(category)

def generate_quiz_with_gemini(category: str = None) -> Optional[Dict[str, Any]]:
    """Genera un quiz utilizzando l'API di Google Gemini."""
    if not GEMINI_API_KEY:
        logger.warning("Chiave API Gemini non configurata, utilizzo modalità offline")
        return generate_sample_quiz(category)
    
    # Se non è specificata una categoria, ne scegliamo una casuale
    if not category:
        category = random.choice(QUIZ_CATEGORIES)
    
    try:
        try:
            # Importa la libreria solo se necessario
            import google.generativeai as genai
        except ImportError:
            logger.error("Libreria 'google-generativeai' non installata. Esegui 'pip install google-generativeai' per installarla.")
            return generate_sample_quiz(category)
        
        # Configura l'API
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        
        # Prepara il prompt
        prompt = f"""Genera un quiz educativo sul rugby nella categoria '{category}'.
Il quiz deve avere:
1. Una domanda chiara e precisa
2. Quattro opzioni di risposta (A, B, C, D)
3. L'indice della risposta corretta (0 per A, 1 per B, 2 per C, 3 per D)
4. Una spiegazione dettagliata della risposta corretta

Restituisci il risultato in formato JSON con i seguenti campi:
{{
  "categoria": "{category}",
  "domanda": "La domanda del quiz",
  "opzioni": ["Opzione A", "Opzione B", "Opzione C", "Opzione D"],
  "risposta_corretta": 0,
  "spiegazione": "Spiegazione dettagliata della risposta corretta"
}}

Assicurati che:
- La domanda sia interessante e educativa
- Le opzioni siano plausibili ma solo una sia corretta
- La spiegazione sia informativa e approfondita
- Il JSON sia valido e ben formattato
"""
        
        # Genera il contenuto con timeout
        import concurrent.futures
        import time
        
        def generate_with_timeout():
            try:
                return model.generate_content(prompt)
            except Exception as e:
                logger.error(f"Errore nella generazione con Gemini: {e}")
                return None
        
        # Esegui la generazione con un timeout di 15 secondi
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(generate_with_timeout)
            try:
                response = future.result(timeout=15)  # 15 secondi di timeout
                if response is None:
                    raise Exception("Generazione fallita")
                content = response.text
            except concurrent.futures.TimeoutError:
                logger.error("Timeout nella generazione con Gemini")
                raise Exception("Timeout nella generazione con Gemini")
        
        # Estrai il JSON dalla risposta
        import re
        json_match = re.search(r'({.*})', content, re.DOTALL)
        if not json_match:
            logger.error("Impossibile estrarre JSON dalla risposta di Gemini")
            return generate_sample_quiz(category)
        
        json_str = json_match.group(1)
        quiz_data = json.loads(json_str)
        
        # Verifica che il quiz contenga tutti i campi necessari
        required_fields = ["categoria", "domanda", "opzioni", "risposta_corretta", "spiegazione"]
        for field in required_fields:
            if field not in quiz_data:
                logger.error(f"Campo mancante nel quiz generato con Gemini: {field}")
                return generate_sample_quiz(category)
        
        # Verifica che ci siano esattamente 4 opzioni
        if len(quiz_data["opzioni"]) != 4:
            logger.error(f"Numero errato di opzioni: {len(quiz_data['opzioni'])}")
            return generate_sample_quiz(category)
        
        # Verifica che l'indice della risposta corretta sia valido
        if not (0 <= quiz_data["risposta_corretta"] <= 3):
            logger.error(f"Indice risposta corretta non valido: {quiz_data['risposta_corretta']}")
            return generate_sample_quiz(category)
        
        # Aggiungi un timestamp di generazione
        quiz_data["generato_il"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        quiz_data["provider"] = "Google Gemini"
        
        return quiz_data
    
    except Exception as e:
        logger.error(f"Errore nella generazione del quiz con Gemini: {e}")
        return generate_sample_quiz(category)

def generate_quiz(category: str = None) -> Dict[str, Any]:
    """Genera un quiz utilizzando il provider configurato."""
    # Usa Gemini se configurato
    if USE_GEMINI and GEMINI_API_KEY:
        try:
            logger.info("Utilizzo Google Gemini per generare il quiz")
            # Verifica che la libreria sia installata
            try:
                import google.generativeai as genai
            except ImportError:
                logger.error("Libreria 'google-generativeai' non installata. Passaggio a OpenAI o quiz di esempio.")
                raise ImportError("Libreria google-generativeai non installata")
                
            quiz = generate_quiz_with_gemini(category)
            if quiz:
                logger.info("Quiz generato con successo usando Gemini")
                return quiz
            else:
                logger.warning("Gemini non ha generato un quiz valido, passaggio a OpenAI")
        except Exception as e:
            logger.error(f"Errore durante l'utilizzo di Gemini: {e}")
            logger.info("Passaggio a OpenAI dopo errore con Gemini")
    
    # Prova con OpenAI se Gemini fallisce o non è configurato
    if OPENAI_API_KEY:
        try:
            logger.info("Utilizzo OpenAI per generare il quiz")
            quiz = generate_quiz_with_openai(category)
            if quiz:
                logger.info("Quiz generato con successo usando OpenAI")
                return quiz
            else:
                logger.warning("OpenAI non ha generato un quiz valido, passaggio ai quiz di esempio")
        except Exception as e:
            logger.error(f"Errore durante l'utilizzo di OpenAI: {e}")
    else:
        logger.warning("Chiave API OpenAI non configurata")
    
    # Fallback ai quiz di esempio
    logger.info("Utilizzo quiz di esempio come fallback")
    return generate_sample_quiz(category)

def generate_multiple_quizzes(num_quizzes: int = 5, category: str = None) -> List[Dict[str, Any]]:
    """Genera più quiz e li salva nel file dei quiz in attesa."""
    generated_quizzes = []
    errors = 0
    online_generated = 0
    sample_generated = 0
    
    # Verifica iniziale delle API disponibili
    api_available = True
    
    # Verifica se le API sono configurate correttamente
    if USE_GEMINI and GEMINI_API_KEY:
        try:
            # Verifica che la libreria Gemini sia installata
            import google.generativeai as genai
            logger.info("Google Gemini API configurata correttamente")
        except ImportError:
            logger.error("Libreria 'google-generativeai' non installata. Utilizzo OpenAI o quiz di esempio.")
            if not OPENAI_API_KEY:
                api_available = False
                logger.warning("Anche OpenAI non è configurato. Verranno generati solo quiz di esempio.")
    elif not OPENAI_API_KEY:
        api_available = False
        logger.warning("Nessuna API configurata. Verranno generati solo quiz di esempio.")
    
    # Genera i quiz richiesti
    for i in range(num_quizzes):
        try:
            # Se le API non sono disponibili o se abbiamo già avuto troppi errori, usa i quiz di esempio
            if not api_available or (errors > 2 and online_generated == 0):
                # Genera un quiz di esempio con categoria casuale se non specificata
                current_category = category if category else random.choice(QUIZ_CATEGORIES)
                quiz = generate_sample_quiz(current_category)
                if quiz:
                    # Aggiungi una nota che indica che è un quiz di esempio
                    quiz["nota"] = f"Quiz di esempio (categoria: {current_category})"
                    sample_generated += 1
                    logger.info(f"Generato quiz di esempio {i+1}/{num_quizzes} (categoria: {current_category})")
            else:
                # Prova a generare un quiz online
                quiz = generate_quiz(category)
                if quiz:
                    online_generated += 1
                    logger.info(f"Generato quiz online {i+1}/{num_quizzes}")
            
            # Aggiungi il quiz alla lista se è stato generato correttamente
            if quiz:
                # Assicurati che ogni quiz abbia un timestamp unico
                quiz["generato_il"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                generated_quizzes.append(quiz)
            else:
                errors += 1
                logger.error(f"Errore nella generazione del quiz {i+1}/{num_quizzes}")
                
        except Exception as e:
            errors += 1
            logger.error(f"Eccezione nella generazione del quiz {i+1}/{num_quizzes}: {e}")
            
            # Se abbiamo troppi errori consecutivi, passa ai quiz di esempio
            if errors > 2 and online_generated == 0:
                api_available = False
                logger.warning("Troppi errori consecutivi. Passaggio ai quiz di esempio per i rimanenti.")
                
    # Log riassuntivo
    logger.info(f"Generazione completata: {len(generated_quizzes)} quiz totali, {online_generated} online, {sample_generated} di esempio, {errors} errori")
    
    # Salva i quiz generati nel file dei quiz in attesa
    if generated_quizzes:
        pending_data = load_pending_quizzes()
        pending_data["quiz_pending"].extend(generated_quizzes)
        pending_data["last_generated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_pending_quizzes(pending_data)
        
        logger.info(f"Generati {len(generated_quizzes)} nuovi quiz ({errors} errori)")
    else:
        logger.error(f"Nessun quiz generato ({errors} errori)")
    
    return generated_quizzes

def get_pending_quiz_count() -> int:
    """Restituisce il numero di quiz in attesa di approvazione."""
    try:
        pending_data = load_pending_quizzes()
        
        # Verifica che quiz_pending sia una lista
        if not isinstance(pending_data.get("quiz_pending"), list):
            logger.error(f"quiz_pending non è una lista: {type(pending_data.get('quiz_pending'))}")
            # Inizializza quiz_pending come lista vuota
            pending_data["quiz_pending"] = []
            save_pending_quizzes(pending_data)
            return 0
        
        return len(pending_data["quiz_pending"])
    except Exception as e:
        logger.error(f"Errore nel conteggio dei quiz in attesa: {e}")
        return 0

def get_pending_quiz(index: int = 0) -> Optional[Dict[str, Any]]:
    """Restituisce un quiz in attesa di approvazione in base all'indice."""
    try:
        logger.info(f"Recupero quiz con indice: {index}")
        pending_data = load_pending_quizzes()
        
        # Verifica che l'indice sia un intero
        if not isinstance(index, int):
            try:
                index = int(index)
                logger.info(f"Indice convertito a intero: {index}")
            except (ValueError, TypeError):
                logger.error(f"Indice non valido: {index} (tipo: {type(index)})")
                return None
        
        # Verifica che quiz_pending sia una lista
        if not isinstance(pending_data.get("quiz_pending"), list):
            logger.error(f"quiz_pending non è una lista: {type(pending_data.get('quiz_pending'))}")
            # Inizializza quiz_pending come lista vuota
            pending_data["quiz_pending"] = []
            save_pending_quizzes(pending_data)
            return None
        
        # Verifica che ci siano quiz e che l'indice sia valido
        if not pending_data["quiz_pending"]:
            logger.warning("Nessun quiz in attesa")
            return None
        
        if index >= len(pending_data["quiz_pending"]):
            logger.warning(f"Indice fuori range: {index} (totale quiz: {len(pending_data['quiz_pending'])})")
            return None
        
        # Verifica che il quiz all'indice specificato sia un dizionario
        quiz = pending_data["quiz_pending"][index]
        if not isinstance(quiz, dict):
            logger.error(f"Quiz all'indice {index} non è un dizionario: {type(quiz)}")
            return None
        
        # Verifica che il quiz contenga tutti i campi necessari
        required_fields = ["categoria", "domanda", "opzioni", "risposta_corretta", "spiegazione"]
        for field in required_fields:
            if field not in quiz:
                logger.error(f"Campo mancante nel quiz all'indice {index}: {field}")
                # Aggiungi un valore predefinito
                if field == "categoria":
                    quiz[field] = "Regole del Rugby"
                elif field == "domanda":
                    quiz[field] = "Domanda di esempio"
                elif field == "opzioni":
                    quiz[field] = ["Opzione A", "Opzione B", "Opzione C", "Opzione D"]
                elif field == "risposta_corretta":
                    quiz[field] = 0
                elif field == "spiegazione":
                    quiz[field] = "Spiegazione di esempio"
                
                # Salva le modifiche
                pending_data["quiz_pending"][index] = quiz
                save_pending_quizzes(pending_data)
        
        return quiz
    except Exception as e:
        logger.error(f"Errore nel recupero del quiz in attesa: {e}")
        return None

def approve_pending_quiz(index: int) -> bool:
    """Approva un quiz in attesa e lo aggiunge al database principale."""
    logger.info(f"Approvazione quiz con indice: {index}")
    pending_data = load_pending_quizzes()
    
    # Verifica che l'indice sia un intero
    if not isinstance(index, int):
        try:
            index = int(index)
        except (ValueError, TypeError):
            logger.error(f"Indice non valido: {index} (tipo: {type(index)})")
            return False
    
    # Verifica che ci siano quiz in attesa e che l'indice sia valido
    if not pending_data["quiz_pending"]:
        logger.error("Nessun quiz in attesa")
        return False
    
    if index >= len(pending_data["quiz_pending"]):
        logger.error(f"Indice fuori range: {index} (totale quiz: {len(pending_data['quiz_pending'])})")
        return False
    
    # Ottieni il quiz da approvare
    quiz = pending_data["quiz_pending"][index]
    logger.info(f"Quiz da approvare: {quiz['domanda'][:30]}...")
    
    # Aggiungi il quiz al database principale
    from modules.quiz_manager import aggiungi_quiz
    
    success = aggiungi_quiz(
        quiz["categoria"],
        quiz["domanda"],
        quiz["opzioni"],
        quiz["risposta_corretta"],
        quiz["spiegazione"]
    )
    
    if success:
        # Rimuovi il quiz dalla lista dei quiz in attesa
        pending_data["quiz_pending"].pop(index)
        save_pending_quizzes(pending_data)
        logger.info(f"Quiz approvato e aggiunto al database principale")
        return True
    
    return False

def reject_pending_quiz(index: int) -> bool:
    """Rifiuta un quiz in attesa e lo rimuove dalla lista."""
    logger.info(f"Rifiuto quiz con indice: {index}")
    pending_data = load_pending_quizzes()
    
    # Verifica che l'indice sia un intero
    if not isinstance(index, int):
        try:
            index = int(index)
        except (ValueError, TypeError):
            logger.error(f"Indice non valido: {index} (tipo: {type(index)})")
            return False
    
    # Verifica che ci siano quiz in attesa e che l'indice sia valido
    if not pending_data["quiz_pending"]:
        logger.error("Nessun quiz in attesa")
        return False
    
    if index >= len(pending_data["quiz_pending"]):
        logger.error(f"Indice fuori range: {index} (totale quiz: {len(pending_data['quiz_pending'])})")
        return False
    
    # Ottieni il quiz da rifiutare per il log
    quiz = pending_data["quiz_pending"][index]
    logger.info(f"Quiz da rifiutare: {quiz['domanda'][:30]}...")
    
    # Rimuovi il quiz dalla lista dei quiz in attesa
    pending_data["quiz_pending"].pop(index)
    save_pending_quizzes(pending_data)
    
    logger.info(f"Quiz rifiutato e rimosso dalla lista")
    return True

def edit_pending_quiz(index: int, field: str, value: Any) -> bool:
    """Modifica un campo di un quiz in attesa."""
    pending_data = load_pending_quizzes()
    
    if not pending_data["quiz_pending"] or index >= len(pending_data["quiz_pending"]):
        return False
    
    # Verifica che il campo sia valido
    valid_fields = ["categoria", "domanda", "opzioni", "risposta_corretta", "spiegazione"]
    if field not in valid_fields:
        logger.error(f"Campo non valido: {field}")
        return False
    
    # Modifica il campo
    pending_data["quiz_pending"][index][field] = value
    
    # Salva le modifiche
    save_pending_quizzes(pending_data)
    
    logger.info(f"Quiz modificato: campo {field}")
    return True

# Inizializza il file dei quiz in attesa all'avvio del modulo
initialize_pending_quiz_file()