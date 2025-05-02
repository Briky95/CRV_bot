#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# Importa le costanti dal modulo di configurazione
from modules.config import CHANNEL_ID

# Funzione per creare i pulsanti di reazione
def crea_pulsanti_reazione(message_id=None):
    """Crea i pulsanti per le reazioni ai messaggi."""
    # Definisci le reazioni disponibili
    reazioni = [
        {"emoji": "👍", "name": "like", "text": "Mi piace"},
        {"emoji": "❤️", "name": "love", "text": "Adoro"},
        {"emoji": "🔥", "name": "fire", "text": "Fuoco"},
        {"emoji": "👏", "name": "clap", "text": "Applauso"},
        {"emoji": "🏉", "name": "rugby", "text": "Rugby"}
    ]
    
    # Crea i pulsanti
    keyboard = []
    row = []
    
    for i, reazione in enumerate(reazioni):
        # Se message_id è specificato, aggiungi l'ID al callback_data
        callback_data = f"reaction:{reazione['name']}"
        if message_id:
            callback_data = f"reaction:{reazione['name']}:{message_id}"
        
        # Aggiungi il pulsante alla riga corrente
        row.append(InlineKeyboardButton(
            f"{reazione['emoji']} {reazione['text']}",
            callback_data=callback_data
        ))
        
        # Crea una nuova riga ogni 3 pulsanti
        if (i + 1) % 3 == 0 or i == len(reazioni) - 1:
            keyboard.append(row)
            row = []
    
    # Aggiungi un pulsante per visualizzare le reazioni
    if message_id:
        keyboard.append([InlineKeyboardButton(
            "👁️ Vedi chi ha reagito",
            callback_data=f"view_reactions:{message_id}"
        )])
    
    return keyboard

async def invia_messaggio_canale(context, risultato, channel_id=None):
    """Invia un messaggio con il risultato della partita al canale Telegram."""
    try:
        # Importa le funzioni necessarie
        from modules.db_manager import carica_reazioni, salva_reazioni
        
        # Usa il channel_id passato come parametro o il valore predefinito
        channel_id = channel_id or CHANNEL_ID
        
        # Verifica che l'ID del canale sia stato configurato correttamente
        if channel_id == "@nome_canale" or not channel_id:
            logger.error("ID del canale Telegram non configurato correttamente. Modifica la costante CHANNEL_ID nel file bot.py.")
            return False, "ID del canale non configurato correttamente"
        
        # Formatta il messaggio
        genere = risultato.get('genere', '')
        categoria = risultato.get('categoria', '')
        tipo_partita = risultato.get('tipo_partita', 'normale')
        info_categoria = f"{categoria} {genere}".strip()
        
        # Ottieni la data della partita, se disponibile
        data_partita = risultato.get('data_partita', 'N/D')
        
        # Crea il messaggio con un layout più compatto e chiaro
        messaggio = f"🏉 <b>{info_categoria}</b> 🏉\n"
        if tipo_partita == 'triangolare':
            messaggio += f"📅 <i>{data_partita}</i> - <b>TRIANGOLARE</b>\n"
        else:
            messaggio += f"📅 <i>{data_partita}</i>\n"
        messaggio += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        
        # Gestione diversa per triangolari e partite normali
        if tipo_partita == 'triangolare':
            # Log per debug
            logger.info(f"Formattazione messaggio per triangolare: {risultato['squadra1']} vs {risultato['squadra2']} vs {risultato['squadra3']}")
            
            # Verifica che tutti i dati necessari siano presenti
            for key in ['partita1_punteggio1', 'partita1_punteggio2', 'partita2_punteggio1', 'partita2_punteggio2', 
                       'partita3_punteggio1', 'partita3_punteggio2', 'partita1_mete1', 'partita1_mete2', 
                       'partita2_mete1', 'partita2_mete2', 'partita3_mete1', 'partita3_mete2']:
                if key not in risultato:
                    logger.error(f"Manca il campo {key} nei dati del triangolare")
                    return False, f"Manca il campo {key} nei dati del triangolare"
                
                # Assicurati che i valori siano numeri interi
                if key.startswith('partita') and key.endswith(('punteggio1', 'punteggio2', 'mete1', 'mete2')):
                    try:
                        risultato[key] = int(risultato[key])
                    except (ValueError, TypeError):
                        logger.error(f"Il campo {key} non è un numero valido: {risultato[key]}")
                        return False, f"Il campo {key} non è un numero valido"
            
            # Formatta le partite del triangolare
            messaggio += f"<b>Squadre partecipanti:</b>\n"
            messaggio += f"• {risultato['squadra1']}\n"
            messaggio += f"• {risultato['squadra2']}\n"
            messaggio += f"• {risultato['squadra3']}\n\n"
            
            messaggio += f"<b>Risultati:</b>\n"
            
            # Partita 1: Squadra1 vs Squadra2
            punteggio1 = risultato['partita1_punteggio1']
            punteggio2 = risultato['partita1_punteggio2']
            mete1 = risultato['partita1_mete1']
            mete2 = risultato['partita1_mete2']
            
            if punteggio1 > punteggio2:
                messaggio += f"• <b>{risultato['squadra1']}</b> <code>{punteggio1}:{punteggio2}</code> {risultato['squadra2']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"• {risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> <b>{risultato['squadra2']}</b> 🏆\n"
            else:
                messaggio += f"• {risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> {risultato['squadra2']} 🤝\n"
            
            # Partita 2: Squadra1 vs Squadra3
            punteggio1 = risultato['partita2_punteggio1']
            punteggio2 = risultato['partita2_punteggio2']
            mete1 = risultato['partita2_mete1']
            mete2 = risultato['partita2_mete2']
            
            if punteggio1 > punteggio2:
                messaggio += f"• <b>{risultato['squadra1']}</b> <code>{punteggio1}:{punteggio2}</code> {risultato['squadra3']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"• {risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> <b>{risultato['squadra3']}</b> 🏆\n"
            else:
                messaggio += f"• {risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> {risultato['squadra3']} 🤝\n"
            
            # Partita 3: Squadra2 vs Squadra3
            punteggio1 = risultato['partita3_punteggio1']
            punteggio2 = risultato['partita3_punteggio2']
            mete1 = risultato['partita3_mete1']
            mete2 = risultato['partita3_mete2']
            
            if punteggio1 > punteggio2:
                messaggio += f"• <b>{risultato['squadra2']}</b> <code>{punteggio1}:{punteggio2}</code> {risultato['squadra3']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"• {risultato['squadra2']} <code>{punteggio1}:{punteggio2}</code> <b>{risultato['squadra3']}</b> 🏆\n"
            else:
                messaggio += f"• {risultato['squadra2']} <code>{punteggio1}:{punteggio2}</code> {risultato['squadra3']} 🤝\n"
            
        else:
            # Partita normale
            punteggio1 = int(risultato.get('punteggio1', 0))
            punteggio2 = int(risultato.get('punteggio2', 0))
            mete1 = int(risultato.get('mete1', 0))
            mete2 = int(risultato.get('mete2', 0))
            
            # Determina il vincitore
            if punteggio1 > punteggio2:
                messaggio += f"<b>{risultato['squadra1']}</b> <code>{punteggio1}:{punteggio2}</code> {risultato['squadra2']} 🏆\n"
            elif punteggio2 > punteggio1:
                messaggio += f"{risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> <b>{risultato['squadra2']}</b> 🏆\n"
            else:
                messaggio += f"{risultato['squadra1']} <code>{punteggio1}:{punteggio2}</code> {risultato['squadra2']} 🤝\n"
            
            # Aggiungi informazioni sulle mete
            messaggio += f"<i>Mete:</i> {mete1} - {mete2}\n"
        
        # Aggiungi informazioni sull'arbitro se disponibili
        arbitro = risultato.get('arbitro', '')
        if arbitro:
            messaggio += f"\n<i>Arbitro:</i> {arbitro}\n"
        
        # Aggiungi un disclaimer
        messaggio += "\n<i>⚠️ Risultato in attesa di omologazione ufficiale</i>"
        
        # Crea i pulsanti di reazione
        keyboard = crea_pulsanti_reazione()
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Verifica che il bot abbia accesso al canale prima di inviare il messaggio
        try:
            # Verifica che il canale esista e che il bot abbia i permessi necessari
            chat = await context.bot.get_chat(channel_id)
            bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
            
            if not bot_member.can_post_messages:
                return False, "Il bot non ha i permessi per inviare messaggi al canale"
                
            logger.info(f"Canale verificato: {chat.title}, Bot ha permessi di invio: {bot_member.can_post_messages}")
        except Exception as e:
            logger.error(f"Errore nella verifica del canale: {e}")
            return False, f"Impossibile accedere al canale: {e}"
        
        # Invia il messaggio al canale
        sent_message = await context.bot.send_message(
            chat_id=channel_id,
            text=messaggio,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Salva l'ID del messaggio e aggiorna i pulsanti con l'ID
        message_id = sent_message.message_id
        keyboard = crea_pulsanti_reazione(message_id)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.edit_message_reply_markup(
            chat_id=channel_id,
            message_id=message_id,
            reply_markup=reply_markup
        )
        
        # Inizializza le reazioni per questo messaggio
        reazioni = carica_reazioni()
        message_id_str = str(message_id)
        if message_id_str not in reazioni:
            reazioni[message_id_str] = {
                "like": [],
                "love": [],
                "fire": [],
                "clap": [],
                "rugby": []
            }
            salva_reazioni(reazioni)
        
        logger.info(f"Messaggio inviato al canale {channel_id} con ID {message_id}")
        return True, message_id
    
    except Exception as e:
        logger.error(f"Errore nell'invio del messaggio al canale: {e}")
        return False, str(e)

# Funzione per creare una tastiera inline con categorie
def crea_tastiera_categorie(categorie):
    keyboard = []
    for categoria in categorie:
        keyboard.append([InlineKeyboardButton(categoria, callback_data=f"cat_{categoria}")])
    return InlineKeyboardMarkup(keyboard)

# Funzione per creare una tastiera inline con generi
def crea_tastiera_generi():
    keyboard = [
        [InlineKeyboardButton("Maschile", callback_data="gen_Maschile")],
        [InlineKeyboardButton("Femminile", callback_data="gen_Femminile")],
        [InlineKeyboardButton("Misto", callback_data="gen_Misto")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Funzione per creare una tastiera inline con tipi di partita
def crea_tastiera_tipo_partita():
    keyboard = [
        [InlineKeyboardButton("Partita normale", callback_data="tipo_normale")],
        [InlineKeyboardButton("Triangolare", callback_data="tipo_triangolare")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Funzione per creare una tastiera inline con squadre
def crea_tastiera_squadre(squadre, prefix="sq"):
    keyboard = []
    for squadra in squadre:
        keyboard.append([InlineKeyboardButton(squadra, callback_data=f"{prefix}_{squadra}")])
    keyboard.append([InlineKeyboardButton("Altra squadra (inserisci manualmente)", callback_data=f"{prefix}_altra")])
    return InlineKeyboardMarkup(keyboard)

# Funzione per formattare il messaggio di risultato per una partita normale
def formatta_messaggio_partita_normale(risultato):
    genere = risultato.get('genere', '')
    categoria = risultato.get('categoria', '')
    info_categoria = f"{categoria} {genere}".strip()
    data_partita = risultato.get('data_partita', 'N/D')
    
    # Determina l'emoji per il vincitore o pareggio
    punteggio1 = int(risultato['punteggio1'])
    punteggio2 = int(risultato['punteggio2'])
    
    if punteggio1 > punteggio2:
        risultato_emoji = "🏆 VITTORIA SQUADRA CASA 🏆"
        squadra1_prefix = "🏆 "
        squadra2_prefix = ""
    elif punteggio2 > punteggio1:
        risultato_emoji = "🏆 VITTORIA SQUADRA OSPITE 🏆"
        squadra1_prefix = ""
        squadra2_prefix = "🏆 "
    else:
        risultato_emoji = "🤝 PAREGGIO 🤝"
        squadra1_prefix = ""
        squadra2_prefix = ""
    
    # Crea il messaggio
    messaggio = f"🏉 <b>{info_categoria}</b> 🏉\n"
    messaggio += f"📅 <i>{data_partita}</i>\n"
    messaggio += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
    messaggio += f"<b>{risultato_emoji}</b>\n\n"
    messaggio += f"{squadra1_prefix}<b>{risultato['squadra1']}</b> {punteggio1}\n"
    messaggio += f"{squadra2_prefix}<b>{risultato['squadra2']}</b> {punteggio2}\n\n"
    messaggio += f"<b>Mete:</b> {risultato['mete1']} - {risultato['mete2']}\n"
    messaggio += f"<b>Arbitro:</b> {risultato['arbitro']}\n\n"
    messaggio += f"<i>Risultato inserito tramite @CRV_Rugby_Bot</i>"
    
    return messaggio

# Funzione per formattare il messaggio di risultato per un triangolare
def formatta_messaggio_triangolare(risultato):
    genere = risultato.get('genere', '')
    categoria = risultato.get('categoria', '')
    info_categoria = f"{categoria} {genere}".strip()
    data_partita = risultato.get('data_partita', 'N/D')
    
    # Abbrevia i nomi delle squadre se sono troppo lunghi
    squadra1 = risultato['squadra1']
    squadra2 = risultato['squadra2']
    squadra3 = risultato['squadra3']
    
    if len(squadra1) > 25:
        squadra1 = squadra1[:22] + "..."
    if len(squadra2) > 25:
        squadra2 = squadra2[:22] + "..."
    if len(squadra3) > 25:
        squadra3 = squadra3[:22] + "..."
    
    # Crea il messaggio
    messaggio = f"🏉 <b>{info_categoria}</b> 🏉\n"
    messaggio += f"📅 <i>{data_partita}</i> - <b>TRIANGOLARE</b>\n"
    messaggio += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
    
    # Mostra le tre squadre e i loro punteggi
    messaggio += f"<b>Squadra 1:</b> {squadra1}\n"
    messaggio += f"<b>Squadra 2:</b> {squadra2}\n"
    messaggio += f"<b>Squadra 3:</b> {squadra3}\n\n"
    
    # Mostra i risultati delle partite
    messaggio += f"<b>Risultati:</b>\n"
    messaggio += f"• {squadra1} vs {squadra2}: {risultato['partita1_punteggio1']} - {risultato['partita1_punteggio2']}\n"
    messaggio += f"• {squadra1} vs {squadra3}: {risultato['partita2_punteggio1']} - {risultato['partita2_punteggio2']}\n"
    messaggio += f"• {squadra2} vs {squadra3}: {risultato['partita3_punteggio1']} - {risultato['partita3_punteggio2']}\n\n"
    
    # Mostra le mete per ogni partita
    messaggio += f"<b>Mete per partita:</b>\n"
    messaggio += f"• {squadra1} vs {squadra2}: {risultato['partita1_mete1']} - {risultato['partita1_mete2']}\n"
    messaggio += f"• {squadra1} vs {squadra3}: {risultato['partita2_mete1']} - {risultato['partita2_mete2']}\n"
    messaggio += f"• {squadra2} vs {squadra3}: {risultato['partita3_mete1']} - {risultato['partita3_mete2']}\n\n"
    
    # Mostra le mete totali
    messaggio += f"<b>Mete totali:</b>\n"
    messaggio += f"• {squadra1}: {risultato['mete1']}\n"
    messaggio += f"• {squadra2}: {risultato['mete2']}\n"
    messaggio += f"• {squadra3}: {risultato['mete3']}\n"
    messaggio += f"<b>Arbitro:</b> {risultato['arbitro']}\n\n"
    messaggio += f"<i>Risultato inserito tramite @CRV_Rugby_Bot</i>"
    
    return messaggio

# Funzione per formattare il messaggio di riepilogo del weekend
def formatta_messaggio_riepilogo_weekend(risultati_weekend):
    if not risultati_weekend:
        return "Non ci sono risultati da mostrare per questo weekend."
    
    messaggio = f"🏉 <b>RIEPILOGO PARTITE DEL WEEKEND</b> 🏉\n"
    messaggio += f"📅 <i>{datetime.now().strftime('%d/%m/%Y')}</i>\n"
    messaggio += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
    
    # Raggruppa i risultati per categoria e genere
    risultati_per_categoria = {}
    for risultato in risultati_weekend:
        categoria = risultato.get('categoria', 'Altra categoria')
        genere = risultato.get('genere', '')
        chiave = f"{categoria} {genere}".strip()
        
        if chiave not in risultati_per_categoria:
            risultati_per_categoria[chiave] = []
        
        risultati_per_categoria[chiave].append(risultato)
    
    # Formatta i risultati per ogni categoria
    for categoria, risultati in risultati_per_categoria.items():
        messaggio += f"<b>{categoria}</b>\n"
        
        for risultato in risultati:
            tipo_partita = risultato.get('tipo_partita', 'normale')
            
            if tipo_partita == 'triangolare':
                messaggio += f"• <b>TRIANGOLARE</b> - {risultato['data_partita']}\n"
                messaggio += f"  {risultato['squadra1']} - {risultato['squadra2']} - {risultato['squadra3']}\n"
                messaggio += f"  Partita 1: {risultato['partita1_punteggio1']} - {risultato['partita1_punteggio2']}\n"
                messaggio += f"  Partita 2: {risultato['partita2_punteggio1']} - {risultato['partita2_punteggio2']}\n"
                messaggio += f"  Partita 3: {risultato['partita3_punteggio1']} - {risultato['partita3_punteggio2']}\n"
            else:
                messaggio += f"• {risultato['squadra1']} {risultato['punteggio1']} - {risultato['punteggio2']} {risultato['squadra2']} ({risultato['data_partita']})\n"
        
        messaggio += "\n"
    
    # Aggiungi statistiche del weekend
    totale_partite = len(risultati_weekend)
    totale_punti = sum(int(r.get('punteggio1', 0)) + int(r.get('punteggio2', 0)) for r in risultati_weekend)
    totale_mete = sum(int(r.get('mete1', 0)) + int(r.get('mete2', 0)) for r in risultati_weekend)
    
    messaggio += f"<b>📊 Statistiche del weekend:</b>\n"
    messaggio += f"• Partite giocate: {totale_partite}\n"
    messaggio += f"• Punti totali: {totale_punti}\n"
    messaggio += f"• Mete totali: {totale_mete}\n\n"
    messaggio += f"<i>Riepilogo generato tramite @CRV_Rugby_Bot</i>"
    
    return messaggio