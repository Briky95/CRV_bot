#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import random
import logging
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

# Configurazione logging
logger = logging.getLogger(__name__)

# Percorso del file JSON per i quiz
QUIZ_FILE = "data/quiz.json"
QUIZ_STATS_FILE = "data/quiz_stats.json"

# Struttura base per i quiz
DEFAULT_QUIZ_DATA = {
    "categorie": [
        {
            "nome": "Regole del Rugby",
            "descrizione": "Domande sulle regole ufficiali del rugby",
            "quiz": []
        },
        {
            "nome": "Storia del Rugby",
            "descrizione": "Domande sulla storia del rugby mondiale e italiano",
            "quiz": []
        },
        {
            "nome": "Tecnica e Tattica",
            "descrizione": "Domande su tecniche di gioco e tattiche",
            "quiz": []
        },
        {
            "nome": "Rugby Veneto",
            "descrizione": "Domande specifiche sul rugby nella regione Veneto",
            "quiz": []
        }
    ]
}

# Esempio di quiz precompilati
QUIZ_ESEMPI = [
    {
        "categoria": "Regole del Rugby",
        "domanda": "Quanti giocatori compongono una squadra di rugby in campo?",
        "opzioni": ["13", "15", "11", "7"],
        "risposta_corretta": 1,  # Indice dell'opzione corretta (15)
        "spiegazione": "Una squadra di rugby a 15 è composta da 15 giocatori in campo. Esistono anche varianti come il rugby a 7 o a 13."
    },
    {
        "categoria": "Regole del Rugby",
        "domanda": "Quanto vale una meta nel rugby?",
        "opzioni": ["3 punti", "5 punti", "7 punti", "2 punti"],
        "risposta_corretta": 1,  # 5 punti
        "spiegazione": "Una meta vale 5 punti. Dopo la meta, la squadra ha l'opportunità di calciare per la trasformazione che vale 2 punti aggiuntivi."
    },
    {
        "categoria": "Storia del Rugby",
        "domanda": "In quale paese è nato il rugby?",
        "opzioni": ["Francia", "Nuova Zelanda", "Inghilterra", "Australia"],
        "risposta_corretta": 2,  # Inghilterra
        "spiegazione": "Il rugby è nato in Inghilterra, nella città di Rugby. Secondo la leggenda, William Webb Ellis, uno studente della Rugby School, prese la palla con le mani durante una partita di calcio nel 1823."
    },
    {
        "categoria": "Tecnica e Tattica",
        "domanda": "Cosa si intende per 'ruck' nel rugby?",
        "opzioni": ["Un tipo di calcio", "Una formazione dopo un placcaggio", "Un fallo di gioco", "Una mischia ordinata"],
        "risposta_corretta": 1,  # Una formazione dopo un placcaggio
        "spiegazione": "Il ruck è una fase di gioco che si forma quando uno o più giocatori di ciascuna squadra sono in piedi e a contatto, chiudendosi attorno al pallone che si trova a terra."
    },
    {
        "categoria": "Rugby Veneto",
        "domanda": "Quale squadra veneta ha vinto più scudetti nel rugby italiano?",
        "opzioni": ["Petrarca Rugby", "Rugby Rovigo", "Benetton Rugby Treviso", "Rugby San Donà"],
        "risposta_corretta": 1,  # Rugby Rovigo
        "spiegazione": "Il Rugby Rovigo è la squadra veneta con più scudetti nella storia del rugby italiano, seguito dal Petrarca Rugby e dal Benetton Rugby Treviso."
    }
]

# Funzione per inizializzare il file dei quiz se non esiste
def inizializza_quiz():
    """Inizializza il file dei quiz con esempi predefiniti se non esiste."""
    if not os.path.exists(os.path.dirname(QUIZ_FILE)):
        os.makedirs(os.path.dirname(QUIZ_FILE))
    
    if not os.path.exists(QUIZ_FILE):
        quiz_data = DEFAULT_QUIZ_DATA
        
        # Aggiungi i quiz di esempio alle rispettive categorie
        for quiz in QUIZ_ESEMPI:
            for categoria in quiz_data["categorie"]:
                if categoria["nome"] == quiz["categoria"]:
                    categoria["quiz"].append({
                        "domanda": quiz["domanda"],
                        "opzioni": quiz["opzioni"],
                        "risposta_corretta": quiz["risposta_corretta"],
                        "spiegazione": quiz["spiegazione"]
                    })
        
        with open(QUIZ_FILE, "w", encoding="utf-8") as file:
            json.dump(quiz_data, file, ensure_ascii=False, indent=4)
        
        logger.info(f"File quiz inizializzato con {len(QUIZ_ESEMPI)} quiz di esempio")
    
    # Inizializza anche il file delle statistiche
    if not os.path.exists(QUIZ_STATS_FILE):
        with open(QUIZ_STATS_FILE, "w", encoding="utf-8") as file:
            json.dump({
                "partecipanti": {},
                "quiz_giornalieri": [],
                "classifica_mensile": [],
                "ultimo_aggiornamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, file, ensure_ascii=False, indent=4)
        
        logger.info("File statistiche quiz inizializzato")

# Funzione per caricare i quiz
def carica_quiz():
    """Carica i quiz dal file JSON."""
    try:
        inizializza_quiz()  # Assicurati che il file esista
        
        with open(QUIZ_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Errore nel caricamento dei quiz: {e}")
        return DEFAULT_QUIZ_DATA

# Funzione per salvare i quiz
def salva_quiz(quiz_data):
    """Salva i quiz nel file JSON."""
    try:
        with open(QUIZ_FILE, "w", encoding="utf-8") as file:
            json.dump(quiz_data, file, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei quiz: {e}")
        return False

# Funzione per caricare le statistiche dei quiz
def carica_statistiche_quiz():
    """Carica le statistiche dei quiz dal file JSON."""
    try:
        if not os.path.exists(QUIZ_STATS_FILE):
            with open(QUIZ_STATS_FILE, "w", encoding="utf-8") as file:
                json.dump({
                    "partecipanti": {},
                    "quiz_giornalieri": [],
                    "classifica_mensile": [],
                    "ultimo_aggiornamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, file, ensure_ascii=False, indent=4)
        
        with open(QUIZ_STATS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Errore nel caricamento delle statistiche dei quiz: {e}")
        return {
            "partecipanti": {},
            "quiz_giornalieri": [],
            "classifica_mensile": [],
            "ultimo_aggiornamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

# Funzione per salvare le statistiche dei quiz
def salva_statistiche_quiz(stats_data):
    """Salva le statistiche dei quiz nel file JSON."""
    try:
        with open(QUIZ_STATS_FILE, "w", encoding="utf-8") as file:
            json.dump(stats_data, file, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio delle statistiche dei quiz: {e}")
        return False

# Funzione per ottenere un quiz casuale da una categoria
def ottieni_quiz_casuale(categoria=None):
    """Ottiene un quiz casuale, opzionalmente da una categoria specifica."""
    quiz_data = carica_quiz()
    
    if categoria:
        # Cerca la categoria specificata
        for cat in quiz_data["categorie"]:
            if cat["nome"] == categoria and cat["quiz"]:
                return random.choice(cat["quiz"]), cat["nome"]
        
        # Se la categoria non esiste o non ha quiz, ritorna None
        return None, None
    else:
        # Seleziona una categoria casuale che ha quiz
        categorie_con_quiz = [cat for cat in quiz_data["categorie"] if cat["quiz"]]
        if not categorie_con_quiz:
            return None, None
        
        categoria_scelta = random.choice(categorie_con_quiz)
        return random.choice(categoria_scelta["quiz"]), categoria_scelta["nome"]

# Funzione per creare un messaggio di quiz per il canale
async def invia_quiz_al_canale(context: ContextTypes.DEFAULT_TYPE, channel_id, quiz_specifico=None):
    """
    Invia un quiz al canale specificato.
    
    Args:
        context: Il contesto del bot Telegram
        channel_id: L'ID del canale a cui inviare il quiz
        quiz_specifico: Un quiz specifico da inviare (opzionale). Se None, ne verrà scelto uno casuale.
    
    Returns:
        bool: True se l'invio è riuscito, False altrimenti
    """
    if quiz_specifico:
        # Usa il quiz specifico fornito
        quiz = quiz_specifico["quiz"]
        categoria = quiz_specifico["categoria"]
    else:
        # Scegli un quiz casuale
        quiz, categoria = ottieni_quiz_casuale()
    
    if not quiz:
        logger.error("Nessun quiz disponibile da inviare al canale")
        return False
    
    # Crea il messaggio del quiz
    messaggio = f"🏉 <b>QUIZ DEL GIORNO: {categoria}</b> 🏉\n\n"
    messaggio += f"<b>Domanda:</b> {quiz['domanda']}\n\n"
    
    # Crea i pulsanti per le opzioni
    keyboard = []
    for i, opzione in enumerate(quiz["opzioni"]):
        callback_data = f"quiz_risposta:{i}:{quiz['risposta_corretta']}"
        keyboard.append([InlineKeyboardButton(f"{chr(65+i)}. {opzione}", callback_data=callback_data)])
    
    # Aggiungi un pulsante per vedere le statistiche
    keyboard.append([InlineKeyboardButton("📊 Classifica Quiz", callback_data="quiz_classifica")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Invia il messaggio al canale
        message = await context.bot.send_message(
            chat_id=channel_id,
            text=messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        # Salva il quiz corrente nelle statistiche
        stats = carica_statistiche_quiz()
        stats["quiz_giornalieri"].append({
            "message_id": message.message_id,
            "categoria": categoria,
            "domanda": quiz["domanda"],
            "risposta_corretta": quiz["risposta_corretta"],
            "spiegazione": quiz["spiegazione"],
            "data": datetime.now().strftime("%Y-%m-%d"),
            "risposte": []
        })
        
        # Mantieni solo gli ultimi 30 quiz
        if len(stats["quiz_giornalieri"]) > 30:
            stats["quiz_giornalieri"] = stats["quiz_giornalieri"][-30:]
        
        salva_statistiche_quiz(stats)
        
        logger.info(f"Quiz inviato al canale {channel_id} con ID messaggio {message.message_id}")
        return True
    except Exception as e:
        logger.error(f"Errore nell'invio del quiz al canale: {e}")
        return False

# Funzione per gestire le risposte ai quiz
async def gestisci_risposta_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce le risposte degli utenti ai quiz."""
    query = update.callback_query
    await query.answer()
    
    # Estrai i dati dal callback
    data = query.data.split(":")
    if len(data) < 3 or data[0] != "quiz_risposta":
        return
    
    risposta_utente = int(data[1])
    risposta_corretta = int(data[2])
    
    # Ottieni le informazioni sull'utente
    user_id = query.from_user.id
    user_name = query.from_user.full_name
    username = query.from_user.username
    
    # Carica le statistiche
    stats = carica_statistiche_quiz()
    
    # Trova il quiz corrente
    quiz_corrente = None
    for quiz in stats["quiz_giornalieri"]:
        if quiz.get("message_id") == query.message.message_id:
            quiz_corrente = quiz
            break
    
    if not quiz_corrente:
        await query.edit_message_reply_markup(reply_markup=None)
        return
    
    # Verifica se l'utente ha già risposto a questo quiz
    for risposta in quiz_corrente.get("risposte", []):
        if risposta.get("user_id") == user_id:
            await query.answer("Hai già risposto a questo quiz!", show_alert=True)
            return
    
    # Registra la risposta dell'utente
    quiz_corrente.setdefault("risposte", []).append({
        "user_id": user_id,
        "user_name": user_name,
        "username": username,
        "risposta": risposta_utente,
        "corretta": risposta_utente == risposta_corretta,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Aggiorna le statistiche dell'utente
    if str(user_id) not in stats["partecipanti"]:
        stats["partecipanti"][str(user_id)] = {
            "nome": user_name,
            "username": username,
            "risposte_totali": 0,
            "risposte_corrette": 0,
            "punti": 0,
            "ultimo_quiz": datetime.now().strftime("%Y-%m-%d")
        }
    
    stats["partecipanti"][str(user_id)]["risposte_totali"] += 1
    
    if risposta_utente == risposta_corretta:
        stats["partecipanti"][str(user_id)]["risposte_corrette"] += 1
        stats["partecipanti"][str(user_id)]["punti"] += 10  # 10 punti per risposta corretta
    
    stats["partecipanti"][str(user_id)]["ultimo_quiz"] = datetime.now().strftime("%Y-%m-%d")
    
    # Salva le statistiche aggiornate
    salva_statistiche_quiz(stats)
    
    # Invia un messaggio privato all'utente con il risultato
    try:
        if risposta_utente == risposta_corretta:
            messaggio = f"✅ <b>Risposta corretta!</b>\n\n"
            messaggio += f"<b>Spiegazione:</b> {quiz_corrente['spiegazione']}\n\n"
            messaggio += f"Hai guadagnato 10 punti! Il tuo punteggio totale è ora {stats['partecipanti'][str(user_id)]['punti']} punti."
        else:
            messaggio = f"❌ <b>Risposta errata!</b>\n\n"
            messaggio += f"La risposta corretta era: <b>{quiz_corrente['opzioni'][risposta_corretta]}</b>\n\n"
            messaggio += f"<b>Spiegazione:</b> {quiz_corrente['spiegazione']}"
        
        await context.bot.send_message(
            chat_id=user_id,
            text=messaggio,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Errore nell'invio del messaggio privato all'utente {user_id}: {e}")
    
    # Aggiorna il messaggio nel canale se necessario (ad esempio, dopo un certo numero di risposte)
    num_risposte = len(quiz_corrente.get("risposte", []))
    if num_risposte >= 10:  # Mostra i risultati dopo 10 risposte
        await mostra_risultati_quiz(context, query.message.chat_id, query.message.message_id)

# Funzione per mostrare i risultati di un quiz
async def mostra_risultati_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id, message_id):
    """Mostra i risultati di un quiz specifico."""
    stats = carica_statistiche_quiz()
    
    # Trova il quiz
    quiz_corrente = None
    for quiz in stats["quiz_giornalieri"]:
        if quiz.get("message_id") == message_id:
            quiz_corrente = quiz
            break
    
    if not quiz_corrente:
        return
    
    # Crea il messaggio con i risultati
    messaggio = f"🏉 <b>RISULTATI DEL QUIZ</b> 🏉\n\n"
    messaggio += f"<b>Domanda:</b> {quiz_corrente['domanda']}\n\n"
    messaggio += f"<b>Risposta corretta:</b> {quiz_corrente['opzioni'][quiz_corrente['risposta_corretta']]}\n\n"
    messaggio += f"<b>Spiegazione:</b> {quiz_corrente['spiegazione']}\n\n"
    
    # Statistiche delle risposte
    risposte_corrette = sum(1 for r in quiz_corrente.get("risposte", []) if r.get("corretta"))
    totale_risposte = len(quiz_corrente.get("risposte", []))
    
    if totale_risposte > 0:
        percentuale_corrette = (risposte_corrette / totale_risposte) * 100
        messaggio += f"<b>Statistiche:</b>\n"
        messaggio += f"• Risposte totali: {totale_risposte}\n"
        messaggio += f"• Risposte corrette: {risposte_corrette} ({percentuale_corrette:.1f}%)\n\n"
        
        # Elenco dei primi 5 utenti che hanno risposto correttamente
        risposte_corrette_list = [r for r in quiz_corrente.get("risposte", []) if r.get("corretta")]
        if risposte_corrette_list:
            messaggio += "<b>Hanno risposto correttamente:</b>\n"
            for i, risposta in enumerate(risposte_corrette_list[:5], 1):
                nome = risposta.get("user_name", "Utente")
                messaggio += f"{i}. {nome}\n"
            
            if len(risposte_corrette_list) > 5:
                messaggio += f"...e altri {len(risposte_corrette_list) - 5} utenti\n"
    else:
        messaggio += "Nessuna risposta ricevuta per questo quiz."
    
    # Pulsante per vedere la classifica
    keyboard = [[InlineKeyboardButton("📊 Classifica Quiz", callback_data="quiz_classifica")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento del messaggio del quiz: {e}")

# Funzione per mostrare la classifica dei quiz
async def mostra_classifica_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra la classifica dei partecipanti ai quiz."""
    query = update.callback_query
    await query.answer()
    
    stats = carica_statistiche_quiz()
    
    # Crea la classifica basata sui punti
    classifica = []
    for user_id, dati in stats["partecipanti"].items():
        classifica.append({
            "user_id": user_id,
            "nome": dati.get("nome", "Utente"),
            "username": dati.get("username", ""),
            "punti": dati.get("punti", 0),
            "risposte_corrette": dati.get("risposte_corrette", 0),
            "risposte_totali": dati.get("risposte_totali", 0)
        })
    
    # Ordina per punti (decrescente)
    classifica.sort(key=lambda x: x["punti"], reverse=True)
    
    # Crea il messaggio della classifica
    messaggio = f"🏆 <b>CLASSIFICA QUIZ</b> 🏆\n\n"
    
    if classifica:
        for i, utente in enumerate(classifica[:10], 1):
            nome = utente["nome"]
            punti = utente["punti"]
            risposte_corrette = utente["risposte_corrette"]
            risposte_totali = utente["risposte_totali"]
            
            if i == 1:
                emoji = "🥇"
            elif i == 2:
                emoji = "🥈"
            elif i == 3:
                emoji = "🥉"
            else:
                emoji = "•"
            
            accuratezza = (risposte_corrette / risposte_totali * 100) if risposte_totali > 0 else 0
            
            messaggio += f"{emoji} <b>{i}. {nome}</b>\n"
            messaggio += f"   Punti: {punti} | Accuratezza: {accuratezza:.1f}%\n"
        
        if len(classifica) > 10:
            messaggio += f"\n<i>...e altri {len(classifica) - 10} partecipanti</i>"
    else:
        messaggio += "Nessun partecipante ha ancora risposto ai quiz."
    
    # Aggiungi informazioni sul prossimo quiz
    messaggio += f"\n\n<b>Prossimo quiz:</b> Ogni giorno alle 12:00"
    
    # Pulsante per tornare al quiz
    keyboard = [[InlineKeyboardButton("◀️ Torna al quiz", callback_data="quiz_torna")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            text=messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento del messaggio della classifica: {e}")

# Funzione per aggiungere un nuovo quiz
def aggiungi_quiz(categoria, domanda, opzioni, risposta_corretta, spiegazione):
    """Aggiunge un nuovo quiz alla categoria specificata."""
    quiz_data = carica_quiz()
    
    # Trova la categoria
    categoria_trovata = False
    for cat in quiz_data["categorie"]:
        if cat["nome"] == categoria:
            cat["quiz"].append({
                "domanda": domanda,
                "opzioni": opzioni,
                "risposta_corretta": risposta_corretta,
                "spiegazione": spiegazione
            })
            categoria_trovata = True
            break
    
    # Se la categoria non esiste, creala
    if not categoria_trovata:
        quiz_data["categorie"].append({
            "nome": categoria,
            "descrizione": f"Domande su {categoria}",
            "quiz": [{
                "domanda": domanda,
                "opzioni": opzioni,
                "risposta_corretta": risposta_corretta,
                "spiegazione": spiegazione
            }]
        })
    
    return salva_quiz(quiz_data)

# Funzione per configurare i job per l'invio automatico dei quiz
def configura_job_quiz(application, channel_id):
    """Configura i job per l'invio automatico dei quiz."""
    try:
        from datetime import time as dt_time
        
        # Orario per l'invio del quiz giornaliero (12:00)
        job_time = dt_time(hour=12, minute=0, second=0)
        
        # Funzione wrapper per il job
        async def job_invia_quiz(context):
            await invia_quiz_al_canale(context, channel_id)
        
        # Pianifica il job giornaliero
        application.job_queue.run_daily(
            job_invia_quiz,
            time=job_time,
            name="quiz_giornaliero"
        )
        
        # Pianifica anche il job per mostrare i risultati dopo 24 ore
        async def job_mostra_risultati(context):
            stats = carica_statistiche_quiz()
            ieri = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            for quiz in stats["quiz_giornalieri"]:
                if quiz.get("data") == ieri and quiz.get("message_id"):
                    await mostra_risultati_quiz(context, channel_id, quiz.get("message_id"))
        
        # Pianifica il job per mostrare i risultati (alle 11:55, prima del nuovo quiz)
        risultati_time = dt_time(hour=11, minute=55, second=0)
        application.job_queue.run_daily(
            job_mostra_risultati,
            time=risultati_time,
            name="mostra_risultati_quiz"
        )
        
        logger.info(f"Job per quiz giornaliero configurato con successo per le {job_time}")
        return True
    except Exception as e:
        logger.error(f"Errore nella configurazione del job per i quiz: {e}")
        return False

# Inizializza i quiz all'avvio del modulo
inizializza_quiz()