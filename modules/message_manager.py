#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# Importa le costanti dal modulo di configurazione
from modules.config import CHANNEL_ID

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