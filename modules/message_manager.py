#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# Importa le costanti dal modulo di configurazione
from modules.config import CHANNEL_ID

# Funzione per creare i pulsanti di reazione
def crea_pulsanti_reazione(message_id=None, include_export=False):
    """Crea i pulsanti per le reazioni ai messaggi con UI migliorata."""
    # Definisci le reazioni disponibili con conteggio
    reazioni = [
        {"emoji": "👍", "name": "like", "text": "Mi piace (0)"},
        {"emoji": "❤️", "name": "love", "text": "Adoro (0)"},
        {"emoji": "🔥", "name": "fire", "text": "Fuoco (0)"},
        {"emoji": "👏", "name": "clap", "text": "Applauso (0)"},
        {"emoji": "🏉", "name": "rugby", "text": "Rugby (0)"}
    ]
    
    # Se message_id è specificato, carica i conteggi reali
    if message_id:
        try:
            from modules.data_manager import carica_reazioni
            reazioni_data = carica_reazioni()
            message_id_str = str(message_id)
            
            if message_id_str in reazioni_data:
                for i, reazione in enumerate(reazioni):
                    name = reazione["name"]
                    count = len(reazioni_data[message_id_str].get(name, []))
                    reazioni[i]["text"] = f"{reazione['text'].split(' (')[0]} ({count})"
        except Exception as e:
            print(f"Errore nel caricamento delle reazioni: {e}")
    
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
        
        # Crea una nuova riga ogni 2 pulsanti (per migliorare la leggibilità su mobile)
        if (i + 1) % 2 == 0 or i == len(reazioni) - 1:
            keyboard.append(row)
            row = []
    
    # Aggiungi un pulsante per visualizzare le reazioni
    if message_id:
        keyboard.append([InlineKeyboardButton(
            "👁️ Vedi chi ha reagito",
            callback_data=f"view_reactions:{message_id}"
        )])
    
    # Aggiungi pulsanti per esportazione se richiesto
    if include_export and message_id:
        keyboard.append([
            InlineKeyboardButton("📊 Excel", callback_data=f"export_excel:{message_id}"),
            InlineKeyboardButton("📄 PDF", callback_data=f"export_pdf:{message_id}")
        ])
    
    # Aggiungi pulsante per condividere
    if message_id:
        try:
            from modules.config import CHANNEL_ID
            keyboard.append([InlineKeyboardButton(
                "📤 Condividi",
                url=f"https://t.me/share/url?url=https://t.me/{CHANNEL_ID.replace('@', '')}/{message_id}"
            )])
        except Exception as e:
            print(f"Errore nella creazione del pulsante di condivisione: {e}")
    
    return keyboard

async def invia_messaggio_canale(context, risultato, channel_id=None):
    """Invia un messaggio con il risultato della partita al canale Telegram."""
    try:
        # Importa le funzioni necessarie
        from modules.data_manager import carica_reazioni, salva_reazioni
        
        # Usa il channel_id passato come parametro o il valore predefinito
        channel_id = channel_id or CHANNEL_ID
        
        # Verifica che l'ID del canale sia stato configurato correttamente
        if channel_id == "@nome_canale" or not channel_id:
            logger.error("ID del canale Telegram non configurato correttamente. Modifica la costante CHANNEL_ID nel file bot.py.")
            return False, "ID del canale non configurato correttamente"
        
        # Ottieni il tipo di partita
        tipo_partita = risultato.get('tipo_partita', 'normale')
        
        # Usa le funzioni di formattazione migliorate per creare il messaggio
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
            
            # Usa la funzione di formattazione migliorata per triangolari
            messaggio = formatta_messaggio_triangolare(risultato)
        else:
            # Usa la funzione di formattazione migliorata per partite normali
            messaggio = formatta_messaggio_partita_normale(risultato)
        
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
    
    # Scegli emoji appropriate in base alla categoria
    if "Elite" in categoria:
        categoria_emoji = "🔝"
    elif "Serie A" in categoria:
        categoria_emoji = "🏆"
    elif "Serie B" in categoria:
        categoria_emoji = "🥈"
    elif "Serie C" in categoria:
        categoria_emoji = "🥉"
    elif "U18" in categoria:
        categoria_emoji = "👦"
    elif "U16" in categoria:
        categoria_emoji = "👦"
    elif "U14" in categoria:
        categoria_emoji = "👦"
    else:
        categoria_emoji = "🏉"
    
    # Determina il risultato con stile visivo migliorato
    if punteggio1 > punteggio2:
        risultato_emoji = "🏆 VITTORIA SQUADRA CASA"
        squadra1_style_open = "<b>"
        squadra1_style_close = "</b>"
        squadra2_style_open = ""
        squadra2_style_close = ""
        punteggio_style = f"<b>{punteggio1}</b> - {punteggio2}"
    elif punteggio2 > punteggio1:
        risultato_emoji = "🏆 VITTORIA SQUADRA OSPITE"
        squadra1_style_open = ""
        squadra1_style_close = ""
        squadra2_style_open = "<b>"
        squadra2_style_close = "</b>"
        punteggio_style = f"{punteggio1} - <b>{punteggio2}</b>"
    else:
        risultato_emoji = "🤝 PAREGGIO"
        squadra1_style_open = "<i>"
        squadra1_style_close = "</i>"
        squadra2_style_open = "<i>"
        squadra2_style_close = "</i>"
        punteggio_style = f"<b>{punteggio1} - {punteggio2}</b>"
    
    # Crea il messaggio con layout migliorato
    messaggio = f"{categoria_emoji} <b>{info_categoria.upper()}</b> {categoria_emoji}\n"
    messaggio += f"📅 <i>{data_partita}</i>\n"
    messaggio += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Box per il risultato
    messaggio += f"<code>  {risultato_emoji}  </code>\n\n"
    
    # Visualizzazione squadre e punteggio con stile migliorato
    messaggio += f"🏠 {squadra1_style_open}{risultato['squadra1']}{squadra1_style_close}\n"
    messaggio += f"🏁 {squadra2_style_open}{risultato['squadra2']}{squadra2_style_close}\n\n"
    messaggio += f"📊 <b>RISULTATO:</b> {punteggio_style}\n"
    messaggio += f"🏉 <b>METE:</b> {risultato['mete1']} - {risultato['mete2']}\n\n"
    
    # Informazioni aggiuntive
    if risultato.get('arbitro'):
        messaggio += f"👨‍⚖️ <b>ARBITRO:</b> {risultato['arbitro']}\n\n"
    
    # Footer con disclaimer e info
    messaggio += "━━━━━━━━━━━━━━━━━━━━\n"
    messaggio += f"<i>⚠️ Risultato in attesa di omologazione</i>\n"
    messaggio += f"<i>📱 Inserito tramite @CRV_Rugby_Bot</i>"
    
    return messaggio

# Funzione per formattare il messaggio di risultato per un triangolare
def formatta_messaggio_triangolare(risultato):
    genere = risultato.get('genere', '')
    categoria = risultato.get('categoria', '')
    info_categoria = f"{categoria} {genere}".strip()
    data_partita = risultato.get('data_partita', 'N/D')
    
    # Scegli emoji appropriate in base alla categoria
    if "Elite" in categoria:
        categoria_emoji = "🔝"
    elif "Serie A" in categoria:
        categoria_emoji = "🏆"
    elif "Serie B" in categoria:
        categoria_emoji = "🥈"
    elif "Serie C" in categoria:
        categoria_emoji = "🥉"
    elif "U18" in categoria:
        categoria_emoji = "👦"
    elif "U16" in categoria:
        categoria_emoji = "👦"
    elif "U14" in categoria:
        categoria_emoji = "👦"
    else:
        categoria_emoji = "🏉"
    
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
    
    # Crea il messaggio con layout migliorato
    messaggio = f"{categoria_emoji} <b>{info_categoria.upper()}</b> {categoria_emoji}\n"
    messaggio += f"📅 <i>{data_partita}</i> - <code>TRIANGOLARE</code>\n"
    messaggio += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Squadre partecipanti con stile migliorato
    messaggio += f"<b>🏟️ SQUADRE PARTECIPANTI</b>\n"
    messaggio += f"• 1️⃣ {squadra1}\n"
    messaggio += f"• 2️⃣ {squadra2}\n"
    messaggio += f"• 3️⃣ {squadra3}\n\n"
    
    # Risultati delle partite con stile migliorato
    messaggio += f"<b>📊 RISULTATI INCONTRI</b>\n"
    
    # Partita 1: Squadra1 vs Squadra2
    punteggio1 = int(risultato['partita1_punteggio1'])
    punteggio2 = int(risultato['partita1_punteggio2'])
    
    if punteggio1 > punteggio2:
        messaggio += f"• <b>{squadra1}</b> <code>{punteggio1}:{punteggio2}</code> {squadra2} 🏆\n"
    elif punteggio2 > punteggio1:
        messaggio += f"• {squadra1} <code>{punteggio1}:{punteggio2}</code> <b>{squadra2}</b> 🏆\n"
    else:
        messaggio += f"• {squadra1} <code>{punteggio1}:{punteggio2}</code> {squadra2} 🤝\n"
    
    # Partita 2: Squadra1 vs Squadra3
    punteggio1 = int(risultato['partita2_punteggio1'])
    punteggio2 = int(risultato['partita2_punteggio2'])
    
    if punteggio1 > punteggio2:
        messaggio += f"• <b>{squadra1}</b> <code>{punteggio1}:{punteggio2}</code> {squadra3} 🏆\n"
    elif punteggio2 > punteggio1:
        messaggio += f"• {squadra1} <code>{punteggio1}:{punteggio2}</code> <b>{squadra3}</b> 🏆\n"
    else:
        messaggio += f"• {squadra1} <code>{punteggio1}:{punteggio2}</code> {squadra3} 🤝\n"
    
    # Partita 3: Squadra2 vs Squadra3
    punteggio1 = int(risultato['partita3_punteggio1'])
    punteggio2 = int(risultato['partita3_punteggio2'])
    
    if punteggio1 > punteggio2:
        messaggio += f"• <b>{squadra2}</b> <code>{punteggio1}:{punteggio2}</code> {squadra3} 🏆\n"
    elif punteggio2 > punteggio1:
        messaggio += f"• {squadra2} <code>{punteggio1}:{punteggio2}</code> <b>{squadra3}</b> 🏆\n"
    else:
        messaggio += f"• {squadra2} <code>{punteggio1}:{punteggio2}</code> {squadra3} 🤝\n"
    
    # Mostra le mete per ogni partita con stile migliorato
    messaggio += f"\n<b>🏉 METE PER PARTITA</b>\n"
    messaggio += f"• {squadra1} vs {squadra2}: <code>{risultato['partita1_mete1']}:{risultato['partita1_mete2']}</code>\n"
    messaggio += f"• {squadra1} vs {squadra3}: <code>{risultato['partita2_mete1']}:{risultato['partita2_mete2']}</code>\n"
    messaggio += f"• {squadra2} vs {squadra3}: <code>{risultato['partita3_mete1']}:{risultato['partita3_mete2']}</code>\n"
    
    # Calcola il totale dei punti per ogni squadra
    punti_squadra1 = int(risultato.get('punteggio1', 0))
    punti_squadra2 = int(risultato.get('punteggio2', 0))
    punti_squadra3 = int(risultato.get('punteggio3', 0))
    
    # Calcola il totale delle mete per ogni squadra
    mete_squadra1 = int(risultato.get('mete1', 0))
    mete_squadra2 = int(risultato.get('mete2', 0))
    mete_squadra3 = int(risultato.get('mete3', 0))
    
    # Aggiungi riepilogo punti e mete
    messaggio += f"\n<b>📈 RIEPILOGO TOTALI</b>\n"
    messaggio += f"• {squadra1}: <b>{punti_squadra1}</b> punti, <b>{mete_squadra1}</b> mete\n"
    messaggio += f"• {squadra2}: <b>{punti_squadra2}</b> punti, <b>{mete_squadra2}</b> mete\n"
    messaggio += f"• {squadra3}: <b>{punti_squadra3}</b> punti, <b>{mete_squadra3}</b> mete\n"
    
    # Aggiungi informazioni sull'arbitro se disponibili
    arbitro = risultato.get('arbitro', '')
    if arbitro:
        messaggio += f"\n👨‍⚖️ <b>ARBITRO:</b> {arbitro}\n"
    
    # Footer con disclaimer e info
    messaggio += "\n━━━━━━━━━━━━━━━━━━━━\n"
    messaggio += f"<i>⚠️ Risultato in attesa di omologazione</i>\n"
    messaggio += f"<i>📱 Inserito tramite @CRV_Rugby_Bot</i>"
    
    return messaggio

# Funzione per formattare il messaggio di riepilogo del weekend
def formatta_messaggio_riepilogo_weekend(risultati_weekend, inizio_weekend_str=None, fine_weekend_str=None):
    """Formatta il messaggio di riepilogo del weekend con UI migliorata."""
    if not risultati_weekend:
        return "Non ci sono risultati da mostrare per questo weekend."
    
    # Se non sono fornite le date, usa la data corrente
    if not inizio_weekend_str or not fine_weekend_str:
        oggi = datetime.now()
        inizio_weekend_str = oggi.strftime('%d/%m/%Y')
        fine_weekend_str = oggi.strftime('%d/%m/%Y')
    
    # Crea il messaggio con il riepilogo in formato più accattivante
    messaggio = f"🏆 <b>RIEPILOGO WEEKEND RUGBY</b> 🏆\n"
    messaggio += f"📅 <i>Weekend del {inizio_weekend_str} - {fine_weekend_str}</i>\n"
    messaggio += "━━━━━━━━━━━━━━━━━━━━\n\n"
    messaggio += f"<i>Ecco i risultati delle partite disputate questo weekend nel Comitato Regionale Veneto.</i>\n\n"
    
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
    for categoria, partite in risultati_per_categoria.items():
        # Aggiungi un'icona diversa in base alla categoria
        if "Elite" in categoria:
            icona = "🔝"
        elif "Serie A" in categoria:
            icona = "🏆"
        elif "Serie B" in categoria:
            icona = "🥈"
        elif "Serie C" in categoria:
            icona = "🥉"
        elif "U18" in categoria:
            icona = "👦"
        elif "U16" in categoria:
            icona = "👦"
        elif "U14" in categoria:
            icona = "👦"
        else:
            icona = "📋"
            
        messaggio += f"\n<b>{icona} {categoria.upper()}</b>\n"
        messaggio += "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        
        for p in partite:
            # Determina il vincitore
            tipo_partita = p.get('tipo_partita', 'normale')
            
            if tipo_partita == 'triangolare':
                messaggio += f"• <code>TRIANGOLARE</code> - <i>{p['data_partita']}</i>\n"
                messaggio += f"  {p['squadra1']} - {p['squadra2']} - {p['squadra3']}\n"
                
                # Formatta i risultati delle partite del triangolare
                punteggio1 = int(p['partita1_punteggio1'])
                punteggio2 = int(p['partita1_punteggio2'])
                
                if punteggio1 > punteggio2:
                    messaggio += f"  • <b>{p['squadra1']}</b> <code>{punteggio1}:{punteggio2}</code> {p['squadra2']}\n"
                elif punteggio2 > punteggio1:
                    messaggio += f"  • {p['squadra1']} <code>{punteggio1}:{punteggio2}</code> <b>{p['squadra2']}</b>\n"
                else:
                    messaggio += f"  • {p['squadra1']} <code>{punteggio1}:{punteggio2}</code> {p['squadra2']} 🤝\n"
                
                punteggio1 = int(p['partita2_punteggio1'])
                punteggio2 = int(p['partita2_punteggio2'])
                
                if punteggio1 > punteggio2:
                    messaggio += f"  • <b>{p['squadra1']}</b> <code>{punteggio1}:{punteggio2}</code> {p['squadra3']}\n"
                elif punteggio2 > punteggio1:
                    messaggio += f"  • {p['squadra1']} <code>{punteggio1}:{punteggio2}</code> <b>{p['squadra3']}</b>\n"
                else:
                    messaggio += f"  • {p['squadra1']} <code>{punteggio1}:{punteggio2}</code> {p['squadra3']} 🤝\n"
                
                punteggio1 = int(p['partita3_punteggio1'])
                punteggio2 = int(p['partita3_punteggio2'])
                
                if punteggio1 > punteggio2:
                    messaggio += f"  • <b>{p['squadra2']}</b> <code>{punteggio1}:{punteggio2}</code> {p['squadra3']}\n"
                elif punteggio2 > punteggio1:
                    messaggio += f"  • {p['squadra2']} <code>{punteggio1}:{punteggio2}</code> <b>{p['squadra3']}</b>\n"
                else:
                    messaggio += f"  • {p['squadra2']} <code>{punteggio1}:{punteggio2}</code> {p['squadra3']} 🤝\n"
            else:
                # Partita normale
                punteggio1 = int(p.get('punteggio1', 0))
                punteggio2 = int(p.get('punteggio2', 0))
                
                # Abbrevia i nomi delle squadre se sono troppo lunghi
                squadra1 = p.get('squadra1', '')
                squadra2 = p.get('squadra2', '')
                
                if len(squadra1) > 20:
                    squadra1 = squadra1[:17] + "..."
                if len(squadra2) > 20:
                    squadra2 = squadra2[:17] + "..."
                
                # Formatta il risultato in modo più leggibile con stile migliorato
                if punteggio1 > punteggio2:
                    risultato = f"🏠 <b>{squadra1}</b> <code>{punteggio1}:{punteggio2}</code> {squadra2}"
                elif punteggio2 > punteggio1:
                    risultato = f"🏁 {squadra1} <code>{punteggio1}:{punteggio2}</code> <b>{squadra2}</b>"
                else:
                    risultato = f"🤝 {squadra1} <code>{punteggio1}:{punteggio2}</code> {squadra2}"
                
                # Aggiungi la data della partita se disponibile
                data_partita = p.get('data_partita', '')
                if data_partita:
                    data_display = f"<i>({data_partita})</i> "
                else:
                    data_display = ""
                
                messaggio += f"• {data_display}{risultato}\n"
    
    # Calcola statistiche del weekend
    totale_partite = len(risultati_weekend)
    totale_punti = sum(int(r.get('punteggio1', 0)) + int(r.get('punteggio2', 0)) for r in risultati_weekend)
    totale_mete = sum(int(r.get('mete1', 0)) + int(r.get('mete2', 0)) for r in risultati_weekend)
    
    # Calcola la media di punti e mete per partita
    media_punti = round(totale_punti / totale_partite, 1) if totale_partite > 0 else 0
    media_mete = round(totale_mete / totale_partite, 1) if totale_partite > 0 else 0
    
    # Calcola statistiche aggiuntive per vittorie casa/trasferta/pareggi
    partite_casa = 0
    partite_trasferta = 0
    partite_pareggio = 0
    
    for r in risultati_weekend:
        if r.get('tipo_partita', 'normale') == 'normale':
            punteggio1 = int(r.get('punteggio1', 0))
            punteggio2 = int(r.get('punteggio2', 0))
            
            if punteggio1 > punteggio2:
                partite_casa += 1
            elif punteggio2 > punteggio1:
                partite_trasferta += 1
            else:
                partite_pareggio += 1
    
    messaggio += "\n━━━━━━━━━━━━━━━━━━━━\n"
    messaggio += f"<b>📊 STATISTICHE WEEKEND</b>\n\n"
    
    # Aggiungi grafico a barre semplice per vittorie casa/trasferta
    total_matches = partite_casa + partite_trasferta + partite_pareggio
    if total_matches > 0:
        casa_percent = int((partite_casa / total_matches) * 10)
        trasferta_percent = int((partite_trasferta / total_matches) * 10)
        pareggio_percent = int((partite_pareggio / total_matches) * 10)
        
        casa_bar = "🟩" * casa_percent
        trasferta_bar = "🟦" * trasferta_percent
        pareggio_bar = "⬜" * pareggio_percent
        
        messaggio += f"🏠 <b>Vittorie casa:</b> {partite_casa} {casa_bar}\n"
        messaggio += f"🏁 <b>Vittorie trasferta:</b> {partite_trasferta} {trasferta_bar}\n"
        messaggio += f"🤝 <b>Pareggi:</b> {partite_pareggio} {pareggio_bar}\n\n"
    
    # Altre statistiche
    messaggio += f"🏟️ <b>Partite giocate:</b> {totale_partite}\n"
    messaggio += f"🔢 <b>Punti totali:</b> {totale_punti} (media: {media_punti} per partita)\n"
    messaggio += f"🏉 <b>Mete totali:</b> {totale_mete} (media: {media_mete} per partita)\n\n"
    
    # Footer con disclaimer e info
    messaggio += "━━━━━━━━━━━━━━━━━━━━\n"
    messaggio += "<i>⚠️ Tutti i risultati sono in attesa di omologazione ufficiale</i>\n"
    messaggio += "<i>📱 Riepilogo generato da @CRV_Rugby_Bot</i>"
    
    return messaggio