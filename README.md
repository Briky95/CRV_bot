# CRV Rugby Bot

Bot Telegram e interfaccia web per la gestione dei risultati delle partite di rugby del Comitato Regionale Veneto.

## Funzionalità

- Inserimento risultati delle partite
- Visualizzazione degli ultimi risultati
- Statistiche sulle partite
- Riepilogo weekend
- Gestione utenti
- Interfaccia web di amministrazione

## Struttura del progetto

- `bot_fixed.py`: Bot Telegram principale
- `web_admin/`: Interfaccia web di amministrazione
- `modules/`: Moduli condivisi tra bot e interfaccia web
- `start_bot.sh`: Script per avviare il bot
- `start_web_admin.sh`: Script per avviare l'interfaccia web

## Requisiti

- Python 3.9+
- Telegram Bot Token
- Database Supabase

## Installazione

1. Clona il repository
2. Crea un ambiente virtuale: `python -m venv .venv`
3. Attiva l'ambiente virtuale:
   - Windows: `.venv\Scripts\activate`
   - Linux/Mac: `source .venv/bin/activate`
4. Installa le dipendenze: `pip install -r requirements.txt`
5. Crea un file `.env` con le seguenti variabili:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   BOT_TOKEN=your_telegram_bot_token
   BOT_TOKEN_WEB=your_telegram_web_bot_token
   ```

## Avvio

- Bot Telegram: `./start_bot.sh` o `python bot_fixed.py`
- Interfaccia web: `./start_web_admin.sh` o `python web_admin/app.py`

## Deployment

Il progetto è configurato per essere deployato su Render.com:
- Bot Telegram: Web Service con comando `python bot_fixed.py`
- Interfaccia web: Web Service con comando `python web_admin/app.py`

## Licenza

Tutti i diritti riservati.