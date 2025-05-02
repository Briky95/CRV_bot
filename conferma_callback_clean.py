


import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
# Configura il logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

async def conferma_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la conferma dell'inserimento della partita."""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "conferma":
            # Prepara il nuovo risultato
            nuovo_risultato = {
                "categoria": context.user_data['categoria'],
                "genere": context.user_data['genere'],
                "tipo_partita": context.user_data.get('tipo_partita', 'normale'),
                "data_partita": context.user_data['data_partita'],
                "squadra1": context.user_data['squadra1'],
                "squadra2": context.user_data['squadra2'],
                "arbitro": context.user_data['arbitro'],
                "inserito_da": update.effective_user.full_name,
                "timestamp": datetime.now().isoformat(),
                "id": int(datetime.now().timestamp())  # Genera un ID univoco basato sul timestamp
            }
            
            # Gestione diversa per partite normali e triangolari
            if context.user_data.get('tipo_partita') == 'triangolare':
                # Aggiungi la terza squadra
                nuovo_risultato["squadra3"] = context.user_data.get('squadra3', '')
                
                # Aggiungi i punteggi e le mete per ogni partita del triangolare
                # Partita 1: squadra1 vs squadra2
                nuovo_risultato["partita1_punteggio1"] = int(context.user_data.get('punteggio1', 0))
                nuovo_risultato["partita1_punteggio2"] = int(context.user_data.get('punteggio2', 0))
                nuovo_risultato["partita1_mete1"] = int(context.user_data.get('mete1', 0))
                nuovo_risultato["partita1_mete2"] = int(context.user_data.get('mete2', 0))
                
                # Partita 2: squadra1 vs squadra3
                nuovo_risultato["partita2_punteggio1"] = int(context.user_data.get('punteggio1_vs_3', 0))
                nuovo_risultato["partita2_punteggio2"] = int(context.user_data.get('punteggio3_vs_1', 0))
                nuovo_risultato["partita2_mete1"] = int(context.user_data.get('mete1_vs_3', 0))
                nuovo_risultato["partita2_mete2"] = int(context.user_data.get('mete3_vs_1', 0))
                
                # Partita 3: squadra2 vs squadra3
                nuovo_risultato["partita3_punteggio1"] = int(context.user_data.get('punteggio2_vs_3', 0))
                nuovo_risultato["partita3_punteggio2"] = int(context.user_data.get('punteggio3_vs_2', 0))
                nuovo_risultato["partita3_mete1"] = int(context.user_data.get('mete2_vs_3', 0))
                nuovo_risultato["partita3_mete2"] = int(context.user_data.get('mete3_vs_2', 0))
                
                # Calcola i totali per ogni squadra
                nuovo_risultato["punteggio1"] = nuovo_risultato["partita1_punteggio1"] + nuovo_risultato["partita2_punteggio1"]
                nuovo_risultato["punteggio2"] = nuovo_risultato["partita1_punteggio2"] + nuovo_risultato["partita3_punteggio1"]
                nuovo_risultato["punteggio3"] = nuovo_risultato["partita2_punteggio2"] + nuovo_risultato["partita3_punteggio2"]
                
                nuovo_risultato["mete1"] = nuovo_risultato["partita1_mete1"] + nuovo_risultato["partita2_mete1"]
                nuovo_risultato["mete2"] = nuovo_risultato["partita1_mete2"] + nuovo_risultato["partita3_mete1"]
                nuovo_risultato["mete3"] = nuovo_risultato["partita2_mete2"] + nuovo_risultato["partita3_mete2"]
            else:
                # Per le partite normali, aggiungi i punteggi e le mete standard
                nuovo_risultato["punteggio1"] = int(context.user_data['punteggio1'])
                nuovo_risultato["punteggio2"] = int(context.user_data['punteggio2'])
                nuovo_risultato["mete1"] = int(context.user_data['mete1'])
                nuovo_risultato["mete2"] = int(context.user_data['mete2'])
            
            # Verifica che la connessione al database sia attiva
            from modules.db_manager import is_supabase_configured
            db_connesso = is_supabase_configured()
            
            # Carica i risultati esistenti
            from modules.db_manager import carica_risultati  # Import the function
            risultati = carica_risultati()
            
            # Aggiungi il nuovo risultato
            risultati.append(nuovo_risultato)
            
            # Salva i risultati aggiornati
            from modules.db_manager import salva_risultati  # Import the function
            salva_risultati(risultati)
            
            # Avvisa l'utente se il database non è connesso
            if not db_connesso:
                logger.warning("Database Supabase non configurato. I dati sono stati salvati solo localmente.")
                await query.edit_message_text(
                    "⚠️ <b>Attenzione</b>\n\n"
                    "Impossibile connettersi al database remoto. I dati sono stati salvati solo localmente.\n\n"
                    "Contatta un amministratore per risolvere il problema.",
                    parse_mode='HTML'
                )
                return ConversationHandler.END
            
            # Invia il messaggio al canale Telegram
            from modules.config import CHANNEL_ID
            from modules.message_manager import invia_messaggio_canale  # Import the function
            invio_riuscito, messaggio_errore = await invia_messaggio_canale(context, nuovo_risultato, CHANNEL_ID)
            
            # Se l'invio è riuscito, aggiorna il risultato con l'ID del messaggio e salva nuovamente
            if invio_riuscito and isinstance(messaggio_errore, int):  # messaggio_errore contiene l'ID del messaggio
                # Aggiorna il risultato con l'ID del messaggio
                nuovo_risultato["message_id"] = messaggio_errore
                
                # Aggiorna il risultato nell'elenco
                for i, r in enumerate(risultati):
                    if r.get('id') == nuovo_risultato.get('id'):
                        risultati[i] = nuovo_risultato
                        break
                
                # Salva nuovamente i risultati
                salva_risultati(risultati)
            
            messaggio_successo = "✅ <b>Partita registrata con successo!</b>\n\n"
            
            if invio_riuscito:
                messaggio_successo += "✅ Risultato pubblicato anche sul canale Telegram.\n\n"
            else:
                messaggio_successo += f"⚠️ Non è stato possibile pubblicare il risultato sul canale Telegram.\n"
                messaggio_successo += f"<i>Errore: {messaggio_errore}</i>\n\n"
                messaggio_successo += "Verifica che:\n"
                messaggio_successo += "1. L'ID del canale sia configurato correttamente\n"
                messaggio_successo += "2. Il bot sia stato aggiunto come amministratore del canale\n"
                messaggio_successo += "3. Il bot abbia i permessi per inviare messaggi\n\n"
            
            messaggio_successo += "Usa /nuova per inserire un'altra partita o /risultati per vedere le ultime partite."
            
            await query.edit_message_text(
                messaggio_successo,
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                "❌ <b>Inserimento annullato.</b>\n\n"
                "Usa /nuova per iniziare di nuovo.",
                parse_mode='HTML'
            )
        
        # Pulisci i dati utente
        context.user_data.clear()
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Errore nella conferma dell'inserimento: {e}")
        await query.edit_message_text(
            "❌ <b>Si è verificato un errore durante il salvataggio della partita.</b>\n\n"
            f"Errore: {str(e)}\n\n"
            "Usa /nuova per riprovare.",
            parse_mode='HTML'
        )
        # Pulisci i dati utente
        context.user_data.clear()
        return ConversationHandler.END
