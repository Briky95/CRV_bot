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
            return json.load(file)
    except Exception as e:
        logger.error(f"Errore nel caricamento dei quiz in attesa: {e}")
        return {"quiz_pending": [], "last_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

def save_pending_quizzes(data: Dict[str, Any]) -> bool:
    """Salva i quiz in attesa di approvazione."""
    try:
        with open(QUIZ_PENDING_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei quiz in attesa: {e}")
        return False

def generate_sample_quiz(category: str = None) -> Dict[str, Any]:
    """Genera un quiz di esempio quando l'API di OpenAI non è disponibile."""
    # Seleziona una categoria casuale se non specificata
    if not category:
        category = random.choice(QUIZ_CATEGORIES)
    
    # Dizionario di quiz di esempio per categoria
    sample_quizzes = {
        "Regole del Rugby": {
            "categoria": "Regole del Rugby",
            "domanda": "Quanti giocatori compongono una squadra di rugby a 15?",
            "opzioni": ["13 giocatori", "15 giocatori", "11 giocatori", "17 giocatori"],
            "risposta_corretta": 1,
            "spiegazione": "Una squadra di rugby a 15 è composta da 15 giocatori in campo. Ci sono 8 avanti (o 'forwards') e 7 trequarti (o 'backs'). Ogni squadra può anche avere fino a 8 giocatori di riserva."
        },
        "Storia del Rugby": {
            "categoria": "Storia del Rugby",
            "domanda": "In quale paese è nato il rugby?",
            "opzioni": ["Francia", "Nuova Zelanda", "Inghilterra", "Australia"],
            "risposta_corretta": 2,
            "spiegazione": "Il rugby è nato in Inghilterra. Secondo la leggenda, il gioco è nato nel 1823 quando William Webb Ellis, uno studente della Rugby School, prese la palla durante una partita di calcio e corse con essa in mano, creando così un nuovo sport."
        },
        "Tecnica e Tattica": {
            "categoria": "Tecnica e Tattica",
            "domanda": "Cosa si intende per 'ruck' nel rugby?",
            "opzioni": ["Un tipo di calcio", "Una formazione di gioco", "Una fase di gioco dopo un placcaggio", "Un fallo di gioco"],
            "risposta_corretta": 2,
            "spiegazione": "Il ruck è una fase di gioco che si forma dopo un placcaggio quando uno o più giocatori di ciascuna squadra sono in piedi e in contatto fisico, chiudendosi attorno alla palla a terra. I giocatori devono usare i piedi per conquistare o mantenere il possesso della palla."
        },
        "Rugby Veneto": {
            "categoria": "Rugby Veneto",
            "domanda": "Quale squadra veneta ha vinto più scudetti nel rugby italiano?",
            "opzioni": ["Petrarca Rugby", "Benetton Rugby Treviso", "Rugby Rovigo", "Rugby San Donà"],
            "risposta_corretta": 2,
            "spiegazione": "Il Rugby Rovigo è la squadra veneta con più scudetti nel rugby italiano. Conosciuti come 'Bersaglieri', hanno una lunga tradizione nel rugby italiano e rappresentano una delle città con maggiore passione per questo sport in Italia."
        },
        "Giocatori Famosi": {
            "categoria": "Giocatori Famosi",
            "domanda": "Chi è il giocatore che ha segnato più mete nella storia della Coppa del Mondo di rugby?",
            "opzioni": ["Jonah Lomu", "Bryan Habana", "Doug Howlett", "Shane Williams"],
            "risposta_corretta": 1,
            "spiegazione": "Bryan Habana, ex ala sudafricana, detiene il record di mete segnate nella Coppa del Mondo di rugby insieme a Jonah Lomu, entrambi con 15 mete. Habana ha raggiunto questo record nel 2015, eguagliando il primato stabilito dalla leggenda neozelandese Lomu."
        },
        "Competizioni Internazionali": {
            "categoria": "Competizioni Internazionali",
            "domanda": "Quale nazione ha vinto più edizioni del Sei Nazioni (includendo il Cinque Nazioni)?",
            "opzioni": ["Inghilterra", "Galles", "Francia", "Irlanda"],
            "risposta_corretta": 1,
            "spiegazione": "Il Galles ha vinto più edizioni del Sei Nazioni (includendo il Cinque Nazioni e le precedenti versioni del torneo). Il torneo è una delle competizioni più antiche e prestigiose del rugby, iniziato nel 1883 come Home Nations Championship tra le quattro nazioni britanniche."
        },
        "Curiosità sul Rugby": {
            "categoria": "Curiosità sul Rugby",
            "domanda": "Quale oggetto viene tradizionalmente consegnato al giocatore che fa il suo debutto nella nazionale neozelandese (All Blacks)?",
            "opzioni": ["Una felce d'argento", "Un cappello nero", "Una maglia speciale", "Un primo cap"],
            "risposta_corretta": 0,
            "spiegazione": "Ai giocatori che fanno il loro debutto con gli All Blacks viene tradizionalmente consegnata una felce d'argento. Questo simbolo è molto importante nella cultura neozelandese e rappresenta l'onore di indossare la maglia nera della nazionale."
        }
    }
    
    # Seleziona un quiz dalla categoria specificata o uno casuale se la categoria non è disponibile
    if category in sample_quizzes:
        quiz = sample_quizzes[category]
    else:
        quiz = random.choice(list(sample_quizzes.values()))
    
    # Aggiungi la data di generazione e un indicatore che è un quiz di esempio
    quiz["generato_il"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    quiz["nota"] = "Quiz di esempio generato in modalità offline"
    
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
        # Chiamata all'API di OpenAI
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
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data
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
        
        # Genera il contenuto
        response = model.generate_content(prompt)
        content = response.text
        
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
        logger.info("Utilizzo Google Gemini per generare il quiz")
        quiz = generate_quiz_with_gemini(category)
        if quiz:
            return quiz
    
    # Altrimenti usa OpenAI
    if OPENAI_API_KEY:
        logger.info("Utilizzo OpenAI per generare il quiz")
        quiz = generate_quiz_with_openai(category)
        if quiz:
            return quiz
    
    # Fallback ai quiz di esempio
    logger.info("Utilizzo quiz di esempio")
    return generate_sample_quiz(category)

def generate_multiple_quizzes(num_quizzes: int = 5, category: str = None) -> List[Dict[str, Any]]:
    """Genera più quiz e li salva nel file dei quiz in attesa."""
    generated_quizzes = []
    
    for _ in range(num_quizzes):
        quiz = generate_quiz(category)
        if quiz:
            generated_quizzes.append(quiz)
    
    # Salva i quiz generati nel file dei quiz in attesa
    if generated_quizzes:
        pending_data = load_pending_quizzes()
        pending_data["quiz_pending"].extend(generated_quizzes)
        pending_data["last_generated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_pending_quizzes(pending_data)
        
        logger.info(f"Generati {len(generated_quizzes)} nuovi quiz")
    
    return generated_quizzes

def get_pending_quiz_count() -> int:
    """Restituisce il numero di quiz in attesa di approvazione."""
    pending_data = load_pending_quizzes()
    return len(pending_data["quiz_pending"])

def get_pending_quiz(index: int = 0) -> Optional[Dict[str, Any]]:
    """Restituisce un quiz in attesa di approvazione in base all'indice."""
    pending_data = load_pending_quizzes()
    
    if not pending_data["quiz_pending"] or index >= len(pending_data["quiz_pending"]):
        return None
    
    return pending_data["quiz_pending"][index]

def approve_pending_quiz(index: int) -> bool:
    """Approva un quiz in attesa e lo aggiunge al database principale."""
    pending_data = load_pending_quizzes()
    
    if not pending_data["quiz_pending"] or index >= len(pending_data["quiz_pending"]):
        return False
    
    # Ottieni il quiz da approvare
    quiz = pending_data["quiz_pending"][index]
    
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
    pending_data = load_pending_quizzes()
    
    if not pending_data["quiz_pending"] or index >= len(pending_data["quiz_pending"]):
        return False
    
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