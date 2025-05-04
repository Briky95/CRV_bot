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

# Chiave API per OpenAI (da configurare nel file .env)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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

def generate_quiz_with_openai(category: str = None) -> Optional[Dict[str, Any]]:
    """Genera un nuovo quiz utilizzando l'API di OpenAI."""
    if not OPENAI_API_KEY:
        logger.error("Chiave API OpenAI non configurata")
        return None
    
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
            return None
        
        # Estrai il contenuto della risposta
        response_data = response.json()
        content = response_data["choices"][0]["message"]["content"]
        
        # Estrai il JSON dalla risposta
        import re
        json_match = re.search(r'({.*})', content, re.DOTALL)
        if not json_match:
            logger.error("Impossibile estrarre JSON dalla risposta")
            return None
        
        json_str = json_match.group(1)
        quiz_data = json.loads(json_str)
        
        # Verifica che il quiz contenga tutti i campi necessari
        required_fields = ["categoria", "domanda", "opzioni", "risposta_corretta", "spiegazione"]
        for field in required_fields:
            if field not in quiz_data:
                logger.error(f"Campo mancante nel quiz generato: {field}")
                return None
        
        # Verifica che ci siano esattamente 4 opzioni
        if len(quiz_data["opzioni"]) != 4:
            logger.error(f"Numero errato di opzioni: {len(quiz_data['opzioni'])}")
            return None
        
        # Verifica che l'indice della risposta corretta sia valido
        if not (0 <= quiz_data["risposta_corretta"] <= 3):
            logger.error(f"Indice risposta corretta non valido: {quiz_data['risposta_corretta']}")
            return None
        
        # Aggiungi un timestamp di generazione
        quiz_data["generato_il"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return quiz_data
    
    except Exception as e:
        logger.error(f"Errore nella generazione del quiz: {e}")
        return None

def generate_multiple_quizzes(num_quizzes: int = 5, category: str = None) -> List[Dict[str, Any]]:
    """Genera più quiz e li salva nel file dei quiz in attesa."""
    generated_quizzes = []
    
    for _ in range(num_quizzes):
        quiz = generate_quiz_with_openai(category)
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