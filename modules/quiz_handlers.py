#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from modules.quiz_manager import (
    carica_quiz, salva_quiz, ottieni_quiz_casuale, invia_quiz_al_canale,
    gestisci_risposta_quiz, mostra_classifica_quiz, aggiungi_quiz,
    configura_job_quiz
)
# Importa il generatore di quiz
from modules.quiz_generator import (
    generate_quiz_with_openai, generate_multiple_quizzes,
    get_pending_quiz_count, get_pending_quiz,
    approve_pending_quiz, reject_pending_quiz, edit_pending_quiz,
    generate_sample_quiz, load_pending_quizzes, save_pending_quizzes
)

# Configurazione logging
logger = logging.getLogger(__name__)

# Comando /quiz per gli amministratori
async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce il comando /quiz per gli amministratori."""
    user_id = update.effective_user.id
    
    # Verifica che l'utente sia un amministratore
    from bot_fixed_corrected import is_admin
    if not is_admin(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Solo gli amministratori possono gestire i quiz."
        )
        return
    
    # Ottieni il numero di quiz in attesa di approvazione
    pending_count = get_pending_quiz_count()
    
    # Mostra il menu di gestione dei quiz
    keyboard = [
        [InlineKeyboardButton("📝 Aggiungi nuovo quiz", callback_data="quiz_admin_aggiungi")],
        [InlineKeyboardButton(f"🤖 Genera quiz con IA ({pending_count} in attesa)", callback_data="quiz_admin_genera")],
        [InlineKeyboardButton("📊 Statistiche quiz", callback_data="quiz_admin_statistiche")],
        [InlineKeyboardButton("🔄 Invia quiz al canale", callback_data="quiz_admin_invia")],
        [InlineKeyboardButton("📋 Gestisci categorie", callback_data="quiz_admin_categorie")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        "<b>🏉 GESTIONE QUIZ</b>\n\n"
        "Seleziona un'opzione per gestire i quiz educativi sul rugby:",
        reply_markup=reply_markup
    )

# Callback per gestire le azioni del menu quiz
async def quiz_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce le azioni del menu di gestione quiz."""
    query = update.callback_query
    await query.answer()
    
    # Verifica che l'utente sia un amministratore
    from bot_fixed_corrected import is_admin
    if not is_admin(query.from_user.id):
        await query.edit_message_text(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Solo gli amministratori possono gestire i quiz.",
            parse_mode='HTML'
        )
        return
    
    # Estrai l'azione dal callback data
    azione = query.data.replace("quiz_admin_", "")
    
    if azione == "aggiungi":
        # Avvia il processo di aggiunta di un nuovo quiz
        quiz_data = carica_quiz()
        
        # Crea i pulsanti per le categorie esistenti
        keyboard = []
        for categoria in quiz_data["categorie"]:
            keyboard.append([InlineKeyboardButton(categoria["nome"], callback_data=f"quiz_cat_{categoria['nome']}")])
        
        # Aggiungi un pulsante per creare una nuova categoria
        keyboard.append([InlineKeyboardButton("➕ Nuova categoria", callback_data="quiz_cat_nuova")])
        
        # Aggiungi un pulsante per tornare indietro
        keyboard.append([InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "<b>📝 AGGIUNGI NUOVO QUIZ</b>\n\n"
            "Seleziona la categoria per il nuovo quiz:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        # Imposta lo stato per la conversazione
        context.user_data["quiz_stato"] = "selezione_categoria"
    
    elif azione == "statistiche":
        # Mostra le statistiche dei quiz
        from modules.quiz_manager import carica_statistiche_quiz
        stats = carica_statistiche_quiz()
        
        # Calcola alcune statistiche
        num_partecipanti = len(stats["partecipanti"])
        num_quiz = len(stats["quiz_giornalieri"])
        
        # Calcola il numero totale di risposte
        risposte_totali = 0
        risposte_corrette = 0
        for quiz in stats["quiz_giornalieri"]:
            for risposta in quiz.get("risposte", []):
                risposte_totali += 1
                if risposta.get("corretta"):
                    risposte_corrette += 1
        
        # Calcola la percentuale di risposte corrette
        percentuale_corrette = (risposte_corrette / risposte_totali * 100) if risposte_totali > 0 else 0
        
        # Crea il messaggio con le statistiche
        messaggio = "<b>📊 STATISTICHE QUIZ</b>\n\n"
        messaggio += f"<b>Partecipanti totali:</b> {num_partecipanti}\n"
        messaggio += f"<b>Quiz inviati:</b> {num_quiz}\n"
        messaggio += f"<b>Risposte totali:</b> {risposte_totali}\n"
        messaggio += f"<b>Risposte corrette:</b> {risposte_corrette} ({percentuale_corrette:.1f}%)\n\n"
        
        # Aggiungi i top 5 partecipanti
        if stats["partecipanti"]:
            classifica = []
            for user_id, dati in stats["partecipanti"].items():
                classifica.append({
                    "nome": dati.get("nome", "Utente"),
                    "punti": dati.get("punti", 0),
                    "risposte_corrette": dati.get("risposte_corrette", 0)
                })
            
            # Ordina per punti
            classifica.sort(key=lambda x: x["punti"], reverse=True)
            
            messaggio += "<b>Top 5 partecipanti:</b>\n"
            for i, utente in enumerate(classifica[:5], 1):
                messaggio += f"{i}. {utente['nome']} - {utente['punti']} punti ({utente['risposte_corrette']} risposte corrette)\n"
        
        # Aggiungi pulsanti per altre azioni
        keyboard = [
            [InlineKeyboardButton("🔄 Aggiorna", callback_data="quiz_admin_statistiche")],
            [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif azione == "invia":
        # Chiedi conferma per inviare un quiz al canale
        from bot_fixed_corrected import CHANNEL_ID
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Conferma", callback_data="quiz_admin_invia_conferma"),
                InlineKeyboardButton("❌ Annulla", callback_data="quiz_admin_menu")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"<b>🔄 INVIA QUIZ AL CANALE</b>\n\n"
            f"Stai per inviare un quiz casuale al canale {CHANNEL_ID}.\n\n"
            f"Confermi l'invio?",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif azione == "invia_conferma":
        # Invia effettivamente il quiz al canale
        from bot_fixed_corrected import CHANNEL_ID
        
        success = await invia_quiz_al_canale(context, CHANNEL_ID)
        
        if success:
            await query.edit_message_text(
                "✅ <b>Quiz inviato con successo!</b>\n\n"
                f"Il quiz è stato inviato al canale {CHANNEL_ID}.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]])
            )
        else:
            await query.edit_message_text(
                "❌ <b>Errore nell'invio del quiz</b>\n\n"
                "Si è verificato un errore durante l'invio del quiz al canale. "
                "Controlla i log per maggiori dettagli.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]])
            )
    
    elif azione == "categorie":
        # Mostra le categorie esistenti
        quiz_data = carica_quiz()
        
        messaggio = "<b>📋 GESTIONE CATEGORIE</b>\n\n"
        
        if quiz_data["categorie"]:
            for i, categoria in enumerate(quiz_data["categorie"], 1):
                num_quiz = len(categoria["quiz"])
                messaggio += f"{i}. <b>{categoria['nome']}</b> ({num_quiz} quiz)\n"
                messaggio += f"   <i>{categoria['descrizione']}</i>\n\n"
        else:
            messaggio += "Non ci sono ancora categorie definite."
        
        # Pulsanti per le azioni
        keyboard = [
            [InlineKeyboardButton("➕ Nuova categoria", callback_data="quiz_cat_nuova")],
            [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif azione == "genera":
        # Menu per la generazione di quiz con IA
        keyboard = [
            [InlineKeyboardButton("🔄 Genera 1 quiz", callback_data="quiz_gen_1")],
            [InlineKeyboardButton("🔄 Genera 3 quiz", callback_data="quiz_gen_3")],
            [InlineKeyboardButton("🔄 Genera 5 quiz", callback_data="quiz_gen_5")]
        ]
        
        # Aggiungi pulsanti per le categorie se ci sono quiz in attesa
        pending_count = get_pending_quiz_count()
        if pending_count > 0:
            keyboard.append([InlineKeyboardButton(f"👁️ Visualizza quiz in attesa ({pending_count})", callback_data="quiz_gen_view")])
        
        keyboard.append([InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "<b>🤖 GENERAZIONE QUIZ CON IA</b>\n\n"
            "Seleziona quanti quiz generare automaticamente con l'intelligenza artificiale.\n\n"
            "I quiz generati dovranno essere approvati prima di essere aggiunti al database.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif azione == "menu":
        # Torna al menu principale
        pending_count = get_pending_quiz_count()
        
        keyboard = [
            [InlineKeyboardButton("📝 Aggiungi nuovo quiz", callback_data="quiz_admin_aggiungi")],
            [InlineKeyboardButton(f"🤖 Genera quiz con IA ({pending_count} in attesa)", callback_data="quiz_admin_genera")],
            [InlineKeyboardButton("📊 Statistiche quiz", callback_data="quiz_admin_statistiche")],
            [InlineKeyboardButton("🔄 Invia quiz al canale", callback_data="quiz_admin_invia")],
            [InlineKeyboardButton("📋 Gestisci categorie", callback_data="quiz_admin_categorie")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "<b>🏉 GESTIONE QUIZ</b>\n\n"
            "Seleziona un'opzione per gestire i quiz educativi sul rugby:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

# Callback per gestire la generazione e l'approvazione dei quiz
async def quiz_generator_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce le azioni relative alla generazione di quiz con IA."""
    query = update.callback_query
    await query.answer()
    
    # Verifica che l'utente sia un amministratore
    from bot_fixed_corrected import is_admin
    if not is_admin(query.from_user.id):
        await query.edit_message_text(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Solo gli amministratori possono gestire i quiz.",
            parse_mode='HTML'
        )
        return
    
    # Estrai l'azione dal callback data
    action = query.data.split("_")[1]
    
    if action == "gen":
        # Generazione di quiz
        num_quizzes = int(query.data.split("_")[2])
        
        # Mostra un messaggio di attesa
        await query.edit_message_text(
            f"<b>🔄 Generazione di {num_quizzes} quiz in corso...</b>\n\n"
            "Questo processo potrebbe richiedere alcuni secondi.",
            parse_mode='HTML'
        )
        
        try:
            # Genera i quiz con un timeout complessivo
            import asyncio
            
            # Crea una funzione che esegue la generazione in un thread separato
            def generate_in_thread():
                return generate_multiple_quizzes(num_quizzes)
            
            # Esegui la generazione in un thread separato con un timeout
            loop = asyncio.get_event_loop()
            generated_quizzes = await loop.run_in_executor(None, generate_in_thread)
            
            # Mostra il risultato
            if generated_quizzes:
                # Determina se sono stati generati quiz di esempio o online
                sample_count = sum(1 for quiz in generated_quizzes if quiz.get('nota') == "Quiz di esempio generato in modalità offline")
                online_count = len(generated_quizzes) - sample_count
                
                message = f"<b>✅ Generazione completata!</b>\n\n"
                
                if online_count > 0 and sample_count > 0:
                    message += f"Sono stati generati {len(generated_quizzes)} nuovi quiz:\n"
                    message += f"- {online_count} quiz generati online\n"
                    message += f"- {sample_count} quiz di esempio (generati offline)\n\n"
                elif online_count > 0:
                    message += f"Sono stati generati {online_count} nuovi quiz online.\n\n"
                else:
                    message += f"Sono stati generati {sample_count} quiz di esempio in modalità offline.\n"
                    message += "Non è stato possibile utilizzare l'API online. Verifica la connessione e le chiavi API.\n\n"
                
                message += f"Puoi visualizzarli e approvarli dalla sezione 'Visualizza quiz in attesa'."
                
                await query.edit_message_text(
                    message,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👁️ Visualizza quiz in attesa", callback_data="quiz_gen_view")],
                        [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                    ])
                )
            else:
                await query.edit_message_text(
                    "<b>❌ Generazione fallita</b>\n\n"
                    "Non è stato possibile generare i quiz. Possibili cause:\n"
                    "- Chiavi API non configurate o non valide\n"
                    "- Problemi di connessione\n"
                    "- Timeout nella risposta dell'API\n\n"
                    "Puoi riprovare o generare quiz di esempio.",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Riprova", callback_data=f"quiz_gen_{num_quizzes}")],
                        [InlineKeyboardButton("📝 Usa quiz di esempio", callback_data="quiz_gen_sample")],
                        [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                    ])
                )
        except Exception as e:
            logger.error(f"Errore durante la generazione dei quiz: {e}")
            await query.edit_message_text(
                f"<b>❌ Errore durante la generazione</b>\n\n"
                f"Si è verificato un errore: {str(e)[:100]}...\n\n"
                f"Puoi riprovare o generare quiz di esempio.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Riprova", callback_data=f"quiz_gen_{num_quizzes}")],
                    [InlineKeyboardButton("📝 Usa quiz di esempio", callback_data="quiz_gen_sample")],
                    [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                ])
            )
    
    elif action == "sample":
        # Genera quiz di esempio
        num_quizzes = 3  # Generiamo 3 quiz di esempio
        
        # Mostra un messaggio di attesa
        await query.edit_message_text(
            f"<b>🔄 Generazione di {num_quizzes} quiz di esempio in corso...</b>\n\n"
            "Questo processo richiederà solo un momento.",
            parse_mode='HTML'
        )
        
        try:
            # Genera i quiz di esempio
            generated_quizzes = []
            for _ in range(num_quizzes):
                quiz = generate_sample_quiz()
                if quiz:
                    generated_quizzes.append(quiz)
            
            # Salva i quiz generati
            if generated_quizzes:
                pending_data = load_pending_quizzes()
                pending_data["quiz_pending"].extend(generated_quizzes)
                pending_data["last_generated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_pending_quizzes(pending_data)
            
            # Mostra il risultato
            await query.edit_message_text(
                f"<b>✅ Generazione completata!</b>\n\n"
                f"Sono stati generati {len(generated_quizzes)} quiz di esempio.\n\n"
                f"Puoi visualizzarli e approvarli dalla sezione 'Visualizza quiz in attesa'.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👁️ Visualizza quiz in attesa", callback_data="quiz_gen_view")],
                    [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                ])
            )
        except Exception as e:
            logger.error(f"Errore durante la generazione dei quiz di esempio: {e}")
            await query.edit_message_text(
                f"<b>❌ Errore durante la generazione</b>\n\n"
                f"Si è verificato un errore: {str(e)[:100]}...",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                ])
            )
    
    elif action == "view":
        # Visualizza i quiz in attesa di approvazione
        pending_count = get_pending_quiz_count()
        
        if pending_count == 0:
            await query.edit_message_text(
                "<b>ℹ️ Nessun quiz in attesa</b>\n\n"
                "Non ci sono quiz in attesa di approvazione.\n\n"
                "Puoi generare nuovi quiz dalla sezione 'Genera quiz con IA'.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Genera quiz", callback_data="quiz_admin_genera")],
                    [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                ])
            )
            return
        
        # Ottieni il primo quiz in attesa
        quiz = get_pending_quiz(0)
        
        if not quiz:
            await query.edit_message_text(
                "<b>❌ Errore</b>\n\n"
                "Si è verificato un errore nel caricamento dei quiz in attesa.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                ])
            )
            return
        
        # Mostra il quiz
        messaggio = f"<b>🤖 QUIZ GENERATO ({1}/{pending_count})</b>\n\n"
        messaggio += f"<b>Categoria:</b> {quiz['categoria']}\n\n"
        messaggio += f"<b>Domanda:</b> {quiz['domanda']}\n\n"
        messaggio += "<b>Opzioni:</b>\n"
        
        for i, opzione in enumerate(quiz['opzioni']):
            if i == quiz['risposta_corretta']:
                messaggio += f"✅ {chr(65+i)}. {opzione}\n"
            else:
                messaggio += f"⬜ {chr(65+i)}. {opzione}\n"
        
        messaggio += f"\n<b>Spiegazione:</b> {quiz['spiegazione']}\n\n"
        messaggio += f"<i>Generato il: {quiz.get('generato_il', 'N/D')}</i>"
        
        # Crea i pulsanti per l'approvazione/rifiuto
        keyboard = [
            [
                InlineKeyboardButton("✅ Approva", callback_data="quiz_approve_0"),
                InlineKeyboardButton("❌ Rifiuta", callback_data="quiz_reject_0")
            ]
        ]
        
        # Aggiungi pulsanti per la navigazione se ci sono più quiz
        if pending_count > 1:
            keyboard.append([
                InlineKeyboardButton("⬅️ Precedente", callback_data="quiz_nav_prev_0"),
                InlineKeyboardButton("➡️ Successivo", callback_data="quiz_nav_next_0")
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_genera")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif action == "approve":
        # Approva un quiz
        try:
            index = int(query.data.split("_")[2])
            logger.info(f"Approvazione quiz con indice: {index}")
            
            success = approve_pending_quiz(index)
            
            if success:
                await query.answer("Quiz approvato con successo!")
                logger.info(f"Quiz approvato con successo (indice: {index})")
            else:
                await query.answer("Errore nell'approvazione del quiz")
                logger.error(f"Errore nell'approvazione del quiz (indice: {index})")
                return
        except Exception as e:
            logger.error(f"Errore durante l'approvazione del quiz: {e}")
            await query.answer(f"Errore: {str(e)[:200]}")
            return
            
            # Aggiorna la visualizzazione
            pending_count = get_pending_quiz_count()
            
            if pending_count > 0:
                # Mostra il prossimo quiz
                await query.edit_message_text(
                    "<b>✅ Quiz approvato con successo!</b>\n\n"
                    "Il quiz è stato aggiunto al database principale.",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👁️ Visualizza altri quiz in attesa", callback_data="quiz_gen_view")],
                        [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                    ])
                )
            else:
                # Non ci sono più quiz in attesa
                await query.edit_message_text(
                    "<b>✅ Quiz approvato con successo!</b>\n\n"
                    "Non ci sono più quiz in attesa di approvazione.",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Genera altri quiz", callback_data="quiz_admin_genera")],
                        [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                    ])
                )
        else:
            await query.answer("Errore nell'approvazione del quiz")
    
    elif action == "reject":
        # Rifiuta un quiz
        try:
            index = int(query.data.split("_")[2])
            logger.info(f"Rifiuto quiz con indice: {index}")
            
            success = reject_pending_quiz(index)
            
            if success:
                await query.answer("Quiz rifiutato")
                logger.info(f"Quiz rifiutato con successo (indice: {index})")
            else:
                await query.answer("Errore nel rifiuto del quiz")
                logger.error(f"Errore nel rifiuto del quiz (indice: {index})")
                return
        except Exception as e:
            logger.error(f"Errore durante il rifiuto del quiz: {e}")
            await query.answer(f"Errore: {str(e)[:200]}")
            return
            
            # Aggiorna la visualizzazione
            pending_count = get_pending_quiz_count()
            
            if pending_count > 0:
                # Mostra il prossimo quiz
                await query.edit_message_text(
                    "<b>❌ Quiz rifiutato</b>\n\n"
                    "Il quiz è stato rimosso dalla lista dei quiz in attesa.",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👁️ Visualizza altri quiz in attesa", callback_data="quiz_gen_view")],
                        [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                    ])
                )
            else:
                # Non ci sono più quiz in attesa
                await query.edit_message_text(
                    "<b>❌ Quiz rifiutato</b>\n\n"
                    "Non ci sono più quiz in attesa di approvazione.",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Genera altri quiz", callback_data="quiz_admin_genera")],
                        [InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_menu")]
                    ])
                )
        else:
            await query.answer("Errore nel rifiuto del quiz")
    
    elif action == "nav":
        # Navigazione tra i quiz in attesa
        try:
            direction = query.data.split("_")[2]  # prev o next
            current_index = int(query.data.split("_")[3])
            logger.info(f"Navigazione quiz: direzione={direction}, indice corrente={current_index}")
            
            if direction == "prev":
                new_index = max(0, current_index - 1)
            else:  # next
                new_index = current_index + 1
            
            # Verifica che l'indice sia valido
            pending_count = get_pending_quiz_count()
            if new_index >= pending_count:
                new_index = 0  # Torna al primo quiz
            
            logger.info(f"Nuovo indice: {new_index} (totale quiz: {pending_count})")
            
            # Ottieni il quiz
            quiz = get_pending_quiz(new_index)
        except Exception as e:
            logger.error(f"Errore durante la navigazione dei quiz: {e}")
            await query.answer(f"Errore: {str(e)[:200]}")
            return
        
        if not quiz:
            await query.answer("Errore nel caricamento del quiz")
            return
        
        # Mostra il quiz
        messaggio = f"<b>🤖 QUIZ GENERATO ({new_index+1}/{pending_count})</b>\n\n"
        messaggio += f"<b>Categoria:</b> {quiz['categoria']}\n\n"
        messaggio += f"<b>Domanda:</b> {quiz['domanda']}\n\n"
        messaggio += "<b>Opzioni:</b>\n"
        
        for i, opzione in enumerate(quiz['opzioni']):
            if i == quiz['risposta_corretta']:
                messaggio += f"✅ {chr(65+i)}. {opzione}\n"
            else:
                messaggio += f"⬜ {chr(65+i)}. {opzione}\n"
        
        messaggio += f"\n<b>Spiegazione:</b> {quiz['spiegazione']}\n\n"
        messaggio += f"<i>Generato il: {quiz.get('generato_il', 'N/D')}</i>"
        
        # Crea i pulsanti per l'approvazione/rifiuto
        keyboard = [
            [
                InlineKeyboardButton("✅ Approva", callback_data=f"quiz_approve_{new_index}"),
                InlineKeyboardButton("❌ Rifiuta", callback_data=f"quiz_reject_{new_index}")
            ]
        ]
        
        # Aggiungi pulsanti per la navigazione
        keyboard.append([
            InlineKeyboardButton("⬅️ Precedente", callback_data=f"quiz_nav_prev_{new_index}"),
            InlineKeyboardButton("➡️ Successivo", callback_data=f"quiz_nav_next_{new_index}")
        ])
        
        keyboard.append([InlineKeyboardButton("◀️ Torna al menu", callback_data="quiz_admin_genera")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            messaggio,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

# Funzione per registrare i gestori dei quiz
def register_quiz_handlers(application):
    """Registra i gestori per i quiz nel bot."""
    # Comando per gli amministratori
    application.add_handler(CommandHandler("quiz", quiz_command))
    
    # Callback per le azioni di amministrazione
    application.add_handler(CallbackQueryHandler(quiz_admin_callback, pattern=r"^quiz_admin_"))
    
    # Callback per la generazione e approvazione dei quiz
    application.add_handler(CallbackQueryHandler(quiz_generator_callback, pattern=r"^quiz_(gen|approve|reject|nav)"))
    
    # Callback per le risposte ai quiz
    application.add_handler(CallbackQueryHandler(gestisci_risposta_quiz, pattern=r"^quiz_risposta:"))
    
    # Callback per la classifica
    application.add_handler(CallbackQueryHandler(mostra_classifica_quiz, pattern=r"^quiz_classifica$"))
    
    # Non configuriamo qui i job per evitare problemi di importazione circolare
    logger.info("Gestori per i quiz registrati con successo")