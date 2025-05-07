#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import sys
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

# Aggiungi la directory principale al path per poter importare i moduli
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurazione logging
logger = logging.getLogger(__name__)

# Stati della conversazione per la modifica dei risultati
SELEZIONA_RISULTATO, SELEZIONA_CAMPO, INSERISCI_VALORE, CONFERMA_MODIFICA = range(4)

# Comando /modifica per avviare la modifica di un risultato
async def modifica_comando(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Avvia il processo di modifica di un risultato."""
    # Importa le funzioni necessarie
    from bot_fixed_corrected import is_utente_autorizzato, is_admin
    from modules.db_manager import carica_risultati
    
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    # Verifica che l'utente sia autorizzato
    if not is_utente_autorizzato(user_id):
        await update.message.reply_html(
            "⚠️ <b>Accesso non autorizzato</b>\n\n"
            "Non sei autorizzato a utilizzare questo comando.\n"
            "Usa /start per richiedere l'accesso.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    # Carica i risultati
    risultati = carica_risultati()
    
    # Se è un admin, mostra tutti i risultati recenti
    # Altrimenti mostra solo i risultati inseriti dall'utente
    if is_admin(user_id):
        risultati_modificabili = risultati[-20:]  # Ultimi 20 risultati
    else:
        risultati_modificabili = [r for r in risultati if r.get('inserito_da') == user_name][-10:]  # Ultimi 10 risultati dell'utente
    
    if not risultati_modificabili:
        await update.message.reply_html(
            "❌ <b>Nessun risultato da modificare</b>\n\n"
            "Non hai inserito risultati recentemente o non ci sono risultati disponibili.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    # Salva i risultati modificabili nel contesto
    context.user_data['risultati_modificabili'] = risultati_modificabili
    
    # Crea i pulsanti per selezionare il risultato da modificare
    keyboard = []
    for i, risultato in enumerate(risultati_modificabili):
        data = risultato.get('data_partita', 'N/D')
        if risultato.get('tipo_partita') == 'triangolare':
            testo = f"{i+1}. {data} - Triangolare {risultato.get('categoria')} {risultato.get('genere')}"
            testo += f" ({risultato.get('squadra1')}, {risultato.get('squadra2')}, {risultato.get('squadra3')})"
        else:
            testo = f"{i+1}. {data} - {risultato.get('categoria')} {risultato.get('genere')}"
            testo += f" {risultato.get('squadra1')} {risultato.get('punteggio1')}-{risultato.get('punteggio2')} {risultato.get('squadra2')}"
        
        keyboard.append([InlineKeyboardButton(testo, callback_data=f"mod_{i}")])
    
    # Aggiungi un pulsante per annullare
    keyboard.append([InlineKeyboardButton("❌ Annulla", callback_data="mod_annulla")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        "<b>🔄 MODIFICA RISULTATO</b>\n\n"
        "Seleziona il risultato che desideri modificare:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return SELEZIONA_RISULTATO

# Callback per la selezione del risultato da modificare
async def seleziona_risultato_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione del risultato da modificare."""
    # Importa le funzioni necessarie
    from bot_fixed_corrected import is_admin
    
    query = update.callback_query
    await query.answer()
    
    # Se l'utente ha annullato
    if query.data == "mod_annulla":
        await query.edit_message_text(
            "❌ Modifica annullata.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    # Estrai l'indice del risultato selezionato
    indice = int(query.data.split("_")[1])
    risultati_modificabili = context.user_data.get('risultati_modificabili', [])
    
    if indice >= len(risultati_modificabili):
        await query.edit_message_text(
            "❌ <b>Errore</b>\n\n"
            "Risultato non trovato. Riprova.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    # Salva il risultato selezionato nel contesto
    risultato = risultati_modificabili[indice]
    context.user_data['risultato_da_modificare'] = risultato
    context.user_data['indice_risultato'] = indice
    
    # Verifica che l'utente sia l'autore o un admin
    user_id = query.from_user.id
    user_name = query.from_user.full_name
    
    if risultato.get('inserito_da') != user_name and not is_admin(user_id):
        await query.edit_message_text(
            "⚠️ <b>Permesso negato</b>\n\n"
            "Puoi modificare solo i risultati che hai inserito tu.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    # Mostra i campi che possono essere modificati
    tipo_partita = risultato.get('tipo_partita', 'normale')
    
    # Crea i pulsanti per selezionare il campo da modificare
    keyboard = []
    
    if tipo_partita == 'normale':
        # Campi modificabili per partite normali
        keyboard.append([InlineKeyboardButton("Punteggio squadra 1", callback_data="campo_punteggio1")])
        keyboard.append([InlineKeyboardButton("Punteggio squadra 2", callback_data="campo_punteggio2")])
        keyboard.append([InlineKeyboardButton("Mete squadra 1", callback_data="campo_mete1")])
        keyboard.append([InlineKeyboardButton("Mete squadra 2", callback_data="campo_mete2")])
    else:
        # Campi modificabili per triangolari
        keyboard.append([InlineKeyboardButton("Punteggi partita 1", callback_data="campo_punteggi_partita1")])
        keyboard.append([InlineKeyboardButton("Punteggi partita 2", callback_data="campo_punteggi_partita2")])
        keyboard.append([InlineKeyboardButton("Punteggi partita 3", callback_data="campo_punteggi_partita3")])
        keyboard.append([InlineKeyboardButton("Mete partita 1", callback_data="campo_mete_partita1")])
        keyboard.append([InlineKeyboardButton("Mete partita 2", callback_data="campo_mete_partita2")])
        keyboard.append([InlineKeyboardButton("Mete partita 3", callback_data="campo_mete_partita3")])
    
    # Campi comuni a entrambi i tipi di partita
    keyboard.append([InlineKeyboardButton("Arbitro", callback_data="campo_arbitro")])
    keyboard.append([InlineKeyboardButton("Sezione arbitrale", callback_data="campo_sezione_arbitrale")])
    
    # Aggiungi pulsanti per confermare o annullare
    keyboard.append([
        InlineKeyboardButton("✅ Conferma modifiche", callback_data="campo_conferma"),
        InlineKeyboardButton("❌ Annulla", callback_data="campo_annulla")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Prepara il messaggio con il riepilogo del risultato selezionato
    if tipo_partita == 'normale':
        messaggio = f"<b>🔄 MODIFICA RISULTATO</b>\n\n"
        messaggio += f"<b>Data:</b> {risultato.get('data_partita')}\n"
        messaggio += f"<b>Categoria:</b> {risultato.get('categoria')} {risultato.get('genere')}\n"
        messaggio += f"<b>Squadre:</b> {risultato.get('squadra1')} vs {risultato.get('squadra2')}\n"
        messaggio += f"<b>Punteggio:</b> {risultato.get('punteggio1')}-{risultato.get('punteggio2')}\n"
        messaggio += f"<b>Mete:</b> {risultato.get('mete1')}-{risultato.get('mete2')}\n"
        messaggio += f"<b>Arbitro:</b> {risultato.get('arbitro', 'N/D')} ({risultato.get('sezione_arbitrale', 'N/D')})\n\n"
    else:
        messaggio = f"<b>🔄 MODIFICA TRIANGOLARE</b>\n\n"
        messaggio += f"<b>Data:</b> {risultato.get('data_partita')}\n"
        messaggio += f"<b>Categoria:</b> {risultato.get('categoria')} {risultato.get('genere')}\n"
        messaggio += f"<b>Squadre:</b> {risultato.get('squadra1')}, {risultato.get('squadra2')}, {risultato.get('squadra3')}\n\n"
        
        # Partita 1
        messaggio += f"<b>Partita 1:</b> {risultato.get('squadra1')} vs {risultato.get('squadra2')}\n"
        messaggio += f"<b>Punteggio:</b> {risultato.get('partita1_punteggio1')}-{risultato.get('partita1_punteggio2')}\n"
        messaggio += f"<b>Mete:</b> {risultato.get('partita1_mete1')}-{risultato.get('partita1_mete2')}\n\n"
        
        # Partita 2
        messaggio += f"<b>Partita 2:</b> {risultato.get('squadra1')} vs {risultato.get('squadra3')}\n"
        messaggio += f"<b>Punteggio:</b> {risultato.get('partita2_punteggio1')}-{risultato.get('partita2_punteggio2')}\n"
        messaggio += f"<b>Mete:</b> {risultato.get('partita2_mete1')}-{risultato.get('partita2_mete2')}\n\n"
        
        # Partita 3
        messaggio += f"<b>Partita 3:</b> {risultato.get('squadra2')} vs {risultato.get('squadra3')}\n"
        messaggio += f"<b>Punteggio:</b> {risultato.get('partita3_punteggio1')}-{risultato.get('partita3_punteggio2')}\n"
        messaggio += f"<b>Mete:</b> {risultato.get('partita3_mete1')}-{risultato.get('partita3_mete2')}\n\n"
        
        messaggio += f"<b>Arbitro:</b> {risultato.get('arbitro', 'N/D')} ({risultato.get('sezione_arbitrale', 'N/D')})\n\n"
    
    messaggio += "Seleziona il campo che desideri modificare:"
    
    await query.edit_message_text(
        messaggio,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    # Inizializza il dizionario delle modifiche
    context.user_data['modifiche'] = {}
    
    return SELEZIONA_CAMPO

# Callback per la selezione del campo da modificare
async def seleziona_campo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione del campo da modificare."""
    query = update.callback_query
    await query.answer()
    
    # Se l'utente ha annullato
    if query.data == "campo_annulla":
        await query.edit_message_text(
            "❌ Modifica annullata.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    # Se l'utente ha confermato le modifiche
    if query.data == "campo_conferma":
        return await conferma_modifiche(update, context)
    
    # Estrai il campo selezionato
    campo = query.data.split("_", 1)[1]
    context.user_data['campo_selezionato'] = campo
    
    # Prepara il messaggio per chiedere il nuovo valore
    risultato = context.user_data.get('risultato_da_modificare', {})
    
    if campo == "punteggio1":
        messaggio = f"Inserisci il nuovo punteggio per {risultato.get('squadra1')}:"
        valore_attuale = risultato.get('punteggio1', 0)
    elif campo == "punteggio2":
        messaggio = f"Inserisci il nuovo punteggio per {risultato.get('squadra2')}:"
        valore_attuale = risultato.get('punteggio2', 0)
    elif campo == "mete1":
        messaggio = f"Inserisci il nuovo numero di mete per {risultato.get('squadra1')}:"
        valore_attuale = risultato.get('mete1', 0)
    elif campo == "mete2":
        messaggio = f"Inserisci il nuovo numero di mete per {risultato.get('squadra2')}:"
        valore_attuale = risultato.get('mete2', 0)
    elif campo == "arbitro":
        messaggio = "Inserisci il nuovo nome dell'arbitro:"
        valore_attuale = risultato.get('arbitro', '')
    elif campo == "sezione_arbitrale":
        messaggio = "Inserisci la nuova sezione arbitrale:"
        valore_attuale = risultato.get('sezione_arbitrale', '')
    elif campo.startswith("punteggi_partita"):
        partita_num = campo[-1]
        messaggio = f"Inserisci i nuovi punteggi per la partita {partita_num} nel formato 'punteggio1-punteggio2':"
        punteggio1 = risultato.get(f'partita{partita_num}_punteggio1', 0)
        punteggio2 = risultato.get(f'partita{partita_num}_punteggio2', 0)
        valore_attuale = f"{punteggio1}-{punteggio2}"
    elif campo.startswith("mete_partita"):
        partita_num = campo[-1]
        messaggio = f"Inserisci le nuove mete per la partita {partita_num} nel formato 'mete1-mete2':"
        mete1 = risultato.get(f'partita{partita_num}_mete1', 0)
        mete2 = risultato.get(f'partita{partita_num}_mete2', 0)
        valore_attuale = f"{mete1}-{mete2}"
    else:
        await query.edit_message_text(
            "❌ <b>Errore</b>\n\n"
            "Campo non valido. Riprova.",
            parse_mode='HTML'
        )
        return SELEZIONA_CAMPO
    
    messaggio += f"\n\n<i>Valore attuale: {valore_attuale}</i>"
    
    await query.edit_message_text(
        messaggio,
        parse_mode='HTML'
    )
    
    return INSERISCI_VALORE

# Handler per l'inserimento del nuovo valore
async def inserisci_valore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento del nuovo valore per il campo selezionato."""
    # Importa le funzioni necessarie
    from bot_fixed_corrected import verifica_congruenza_punteggio_mete
    
    nuovo_valore = update.message.text.strip()
    campo = context.user_data.get('campo_selezionato', '')
    risultato = context.user_data.get('risultato_da_modificare', {})
    modifiche = context.user_data.get('modifiche', {})
    
    # Validazione del nuovo valore
    if campo in ["punteggio1", "punteggio2", "mete1", "mete2"]:
        try:
            nuovo_valore = int(nuovo_valore)
            if nuovo_valore < 0:
                raise ValueError("Il valore deve essere positivo")
        except ValueError:
            await update.message.reply_html(
                "❌ <b>Errore</b>\n\n"
                "Inserisci un numero intero positivo.",
                parse_mode='HTML'
            )
            return INSERISCI_VALORE
    
    elif campo.startswith("punteggi_partita") or campo.startswith("mete_partita"):
        try:
            parti = nuovo_valore.split("-")
            if len(parti) != 2:
                raise ValueError("Formato non valido")
            
            valore1 = int(parti[0].strip())
            valore2 = int(parti[1].strip())
            
            if valore1 < 0 or valore2 < 0:
                raise ValueError("I valori devono essere positivi")
            
            partita_num = campo[-1]
            
            if campo.startswith("punteggi_partita"):
                modifiche[f'partita{partita_num}_punteggio1'] = valore1
                modifiche[f'partita{partita_num}_punteggio2'] = valore2
            else:  # mete_partita
                modifiche[f'partita{partita_num}_mete1'] = valore1
                modifiche[f'partita{partita_num}_mete2'] = valore2
            
            # Salva le modifiche
            context.user_data['modifiche'] = modifiche
            
            # Ricrea la tastiera per la selezione del campo
            tipo_partita = risultato.get('tipo_partita', 'normale')
            keyboard = []
            
            if tipo_partita == 'normale':
                keyboard.append([InlineKeyboardButton("Punteggio squadra 1", callback_data="campo_punteggio1")])
                keyboard.append([InlineKeyboardButton("Punteggio squadra 2", callback_data="campo_punteggio2")])
                keyboard.append([InlineKeyboardButton("Mete squadra 1", callback_data="campo_mete1")])
                keyboard.append([InlineKeyboardButton("Mete squadra 2", callback_data="campo_mete2")])
            else:
                keyboard.append([InlineKeyboardButton("Punteggi partita 1", callback_data="campo_punteggi_partita1")])
                keyboard.append([InlineKeyboardButton("Punteggi partita 2", callback_data="campo_punteggi_partita2")])
                keyboard.append([InlineKeyboardButton("Punteggi partita 3", callback_data="campo_punteggi_partita3")])
                keyboard.append([InlineKeyboardButton("Mete partita 1", callback_data="campo_mete_partita1")])
                keyboard.append([InlineKeyboardButton("Mete partita 2", callback_data="campo_mete_partita2")])
                keyboard.append([InlineKeyboardButton("Mete partita 3", callback_data="campo_mete_partita3")])
            
            keyboard.append([InlineKeyboardButton("Arbitro", callback_data="campo_arbitro")])
            keyboard.append([InlineKeyboardButton("Sezione arbitrale", callback_data="campo_sezione_arbitrale")])
            
            keyboard.append([
                InlineKeyboardButton("✅ Conferma modifiche", callback_data="campo_conferma"),
                InlineKeyboardButton("❌ Annulla", callback_data="campo_annulla")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Mostra un messaggio di conferma
            await update.message.reply_html(
                f"✅ Valore aggiornato con successo!\n\n"
                f"Seleziona un altro campo da modificare o conferma le modifiche:",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
            return SELEZIONA_CAMPO
            
        except ValueError:
            await update.message.reply_html(
                "❌ <b>Errore</b>\n\n"
                "Formato non valido. Inserisci i valori nel formato 'numero-numero'.",
                parse_mode='HTML'
            )
            return INSERISCI_VALORE
    
    # Salva la modifica
    modifiche[campo] = nuovo_valore
    context.user_data['modifiche'] = modifiche
    
    # Verifica la congruenza tra punteggio e mete se entrambi sono stati modificati
    if campo in ["punteggio1", "punteggio2", "mete1", "mete2"]:
        # Ottieni i valori attuali o modificati
        punteggio1 = modifiche.get('punteggio1', risultato.get('punteggio1', 0))
        punteggio2 = modifiche.get('punteggio2', risultato.get('punteggio2', 0))
        mete1 = modifiche.get('mete1', risultato.get('mete1', 0))
        mete2 = modifiche.get('mete2', risultato.get('mete2', 0))
        
        # Verifica la congruenza
        congruente1, messaggio1 = verifica_congruenza_punteggio_mete(punteggio1, mete1)
        congruente2, messaggio2 = verifica_congruenza_punteggio_mete(punteggio2, mete2)
        
        if not congruente1 or not congruente2:
            avviso = "⚠️ <b>Attenzione</b>\n\n"
            if not congruente1:
                avviso += f"Squadra 1: {messaggio1}\n"
            if not congruente2:
                avviso += f"Squadra 2: {messaggio2}\n"
            
            await update.message.reply_html(
                avviso,
                parse_mode='HTML'
            )
    
    # Ricrea la tastiera per la selezione del campo
    tipo_partita = risultato.get('tipo_partita', 'normale')
    keyboard = []
    
    if tipo_partita == 'normale':
        keyboard.append([InlineKeyboardButton("Punteggio squadra 1", callback_data="campo_punteggio1")])
        keyboard.append([InlineKeyboardButton("Punteggio squadra 2", callback_data="campo_punteggio2")])
        keyboard.append([InlineKeyboardButton("Mete squadra 1", callback_data="campo_mete1")])
        keyboard.append([InlineKeyboardButton("Mete squadra 2", callback_data="campo_mete2")])
    else:
        keyboard.append([InlineKeyboardButton("Punteggi partita 1", callback_data="campo_punteggi_partita1")])
        keyboard.append([InlineKeyboardButton("Punteggi partita 2", callback_data="campo_punteggi_partita2")])
        keyboard.append([InlineKeyboardButton("Punteggi partita 3", callback_data="campo_punteggi_partita3")])
        keyboard.append([InlineKeyboardButton("Mete partita 1", callback_data="campo_mete_partita1")])
        keyboard.append([InlineKeyboardButton("Mete partita 2", callback_data="campo_mete_partita2")])
        keyboard.append([InlineKeyboardButton("Mete partita 3", callback_data="campo_mete_partita3")])
    
    keyboard.append([InlineKeyboardButton("Arbitro", callback_data="campo_arbitro")])
    keyboard.append([InlineKeyboardButton("Sezione arbitrale", callback_data="campo_sezione_arbitrale")])
    
    keyboard.append([
        InlineKeyboardButton("✅ Conferma modifiche", callback_data="campo_conferma"),
        InlineKeyboardButton("❌ Annulla", callback_data="campo_annulla")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Mostra un messaggio di conferma
    await update.message.reply_html(
        f"✅ Valore aggiornato con successo!\n\n"
        f"Seleziona un altro campo da modificare o conferma le modifiche:",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    return SELEZIONA_CAMPO

# Funzione per confermare le modifiche
async def conferma_modifiche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Conferma le modifiche e aggiorna il risultato."""
    # Importa le funzioni necessarie
    from bot_fixed_corrected import CHANNEL_ID
    from modules.db_manager import carica_risultati, salva_risultati
    from modules.message_manager import formatta_messaggio_triangolare, formatta_messaggio_partita_normale
    
    query = update.callback_query
    
    # Ottieni i dati necessari
    risultato = context.user_data.get('risultato_da_modificare', {})
    modifiche = context.user_data.get('modifiche', {})
    
    if not modifiche:
        await query.edit_message_text(
            "❌ <b>Nessuna modifica effettuata</b>\n\n"
            "Non hai apportato modifiche al risultato.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    # Carica tutti i risultati
    risultati = carica_risultati()
    
    # Trova l'indice reale del risultato da modificare
    risultato_id = risultato.get('id')
    indice_reale = -1
    
    for i, r in enumerate(risultati):
        if r.get('id') == risultato_id:
            indice_reale = i
            break
    
    if indice_reale == -1:
        await query.edit_message_text(
            "❌ <b>Errore</b>\n\n"
            "Impossibile trovare il risultato da modificare nel database.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    # Applica le modifiche
    for campo, valore in modifiche.items():
        risultati[indice_reale][campo] = valore
    
    # Aggiorna il timestamp della modifica
    risultati[indice_reale]['modificato_il'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    risultati[indice_reale]['modificato_da'] = query.from_user.full_name
    
    # Salva i risultati aggiornati
    salva_risultati(risultati)
    
    # Aggiorna il messaggio nel canale se possibile
    message_id = risultato.get('message_id')
    
    if message_id:
        try:
            # Genera il nuovo messaggio
            if risultato.get('tipo_partita') == 'triangolare':
                nuovo_messaggio = formatta_messaggio_triangolare(risultati[indice_reale])
            else:
                nuovo_messaggio = formatta_messaggio_partita_normale(risultati[indice_reale])
            
            # Aggiorna il messaggio nel canale
            await context.bot.edit_message_text(
                chat_id=CHANNEL_ID,
                message_id=message_id,
                text=nuovo_messaggio,
                parse_mode='HTML'
            )
            
            aggiornamento_canale = "✅ Il messaggio nel canale è stato aggiornato."
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento del messaggio nel canale: {e}")
            aggiornamento_canale = "⚠️ Non è stato possibile aggiornare il messaggio nel canale. È stato creato un nuovo messaggio."
            
            # Invia un nuovo messaggio al canale
            try:
                if risultato.get('tipo_partita') == 'triangolare':
                    nuovo_messaggio = formatta_messaggio_triangolare(risultati[indice_reale])
                else:
                    nuovo_messaggio = formatta_messaggio_partita_normale(risultati[indice_reale])
                
                # Invia il nuovo messaggio
                sent_message = await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=nuovo_messaggio + "\n\n<i>⚠️ Questo è un risultato aggiornato</i>",
                    parse_mode='HTML'
                )
                
                # Aggiorna l'ID del messaggio nel risultato
                risultati[indice_reale]['message_id'] = sent_message.message_id
                salva_risultati(risultati)
                
            except Exception as e2:
                logger.error(f"Errore nell'invio del nuovo messaggio al canale: {e2}")
                aggiornamento_canale = "❌ Non è stato possibile aggiornare o inviare un nuovo messaggio al canale."
    else:
        aggiornamento_canale = "⚠️ Non è stato possibile aggiornare il messaggio nel canale (ID messaggio non trovato)."
    
    # Mostra un messaggio di conferma
    await query.edit_message_text(
        f"✅ <b>Modifiche salvate con successo!</b>\n\n"
        f"{aggiornamento_canale}\n\n"
        f"Usa /menu per tornare al menu principale.",
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

# Funzione per registrare i gestori per la modifica dei risultati
def register_edit_handlers(application):
    """Registra i gestori per la modifica dei risultati."""
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
    
    # Aggiungi il ConversationHandler per la modifica dei risultati
    modifica_handler = ConversationHandler(
        entry_points=[CommandHandler("modifica", modifica_comando)],
        states={
            SELEZIONA_RISULTATO: [
                CallbackQueryHandler(seleziona_risultato_callback, pattern=r"^mod_")
            ],
            SELEZIONA_CAMPO: [
                CallbackQueryHandler(seleziona_campo_callback, pattern=r"^campo_")
            ],
            INSERISCI_VALORE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, inserisci_valore_callback)
            ],
        },
        fallbacks=[CommandHandler("annulla", lambda update, context: ConversationHandler.END)]
    )
    
    application.add_handler(modifica_handler)
    
    logger.info("Gestori per la modifica dei risultati registrati con successo")