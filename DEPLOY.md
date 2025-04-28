# Guida al Deployment su Render

Questa guida ti mostrerà come deployare il bot Telegram e l'interfaccia web su Render.com.

## Prerequisiti

1. Un account su [Render.com](https://render.com/)
2. Un repository Git (GitHub, GitLab, Bitbucket)
3. Token del bot Telegram (principale e web)
4. Credenziali Supabase

## Passaggi per il Deployment

### 1. Preparare il Repository Git

1. Crea un nuovo repository su GitHub, GitLab o Bitbucket
2. Inizializza il repository locale e carica il codice:

```bash
cd /percorso/al/progetto
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/username/repository.git
git push -u origin main
```

### 2. Configurare i Servizi su Render

#### Opzione 1: Utilizzare il file render.yaml (Blueprint)

1. Accedi a [Render.com](https://render.com/)
2. Vai su "Blueprints" nel dashboard
3. Clicca su "New Blueprint Instance"
4. Seleziona il repository Git
5. Render rileverà automaticamente il file `render.yaml` e configurerà i servizi
6. Configura le variabili d'ambiente richieste (vedi `.env.example`)
7. Clicca su "Apply" per creare i servizi

#### Opzione 2: Configurare Manualmente i Servizi

##### Bot Telegram

1. Accedi a [Render.com](https://render.com/)
2. Vai su "Web Services" nel dashboard
3. Clicca su "New Web Service"
4. Seleziona il repository Git
5. Configura il servizio:
   - **Nome**: crv-rugby-bot
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot_fixed.py`
   - **Piano**: Free
6. Configura le variabili d'ambiente:
   - `SUPABASE_URL`: URL del tuo database Supabase
   - `SUPABASE_KEY`: Chiave API del tuo database Supabase
   - `BOT_TOKEN`: Token del bot Telegram principale
   - `CHANNEL_ID`: ID del canale Telegram (es. @CRV_Rugby_Risultati_Partite)
7. Clicca su "Create Web Service"

##### Interfaccia Web

1. Accedi a [Render.com](https://render.com/)
2. Vai su "Web Services" nel dashboard
3. Clicca su "New Web Service"
4. Seleziona il repository Git
5. Configura il servizio:
   - **Nome**: crv-rugby-web-admin
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn web_admin.app:app`
   - **Piano**: Free
6. Configura le variabili d'ambiente:
   - `SUPABASE_URL`: URL del tuo database Supabase
   - `SUPABASE_KEY`: Chiave API del tuo database Supabase
   - `BOT_TOKEN_WEB`: Token del bot Telegram per l'interfaccia web
   - `FLASK_ENV`: production
   - `FLASK_APP`: web_admin/app.py
7. Clicca su "Create Web Service"

### 3. Verificare il Deployment

1. Attendi che i servizi siano deployati (può richiedere alcuni minuti)
2. Verifica che il bot Telegram sia attivo inviando il comando `/start`
3. Accedi all'interfaccia web utilizzando l'URL fornito da Render

### 4. Configurare il Webhook per il Bot (Opzionale)

Se preferisci utilizzare i webhook invece del polling per il bot Telegram:

1. Ottieni l'URL del tuo servizio web da Render (es. https://crv-rugby-bot.onrender.com)
2. Configura il webhook utilizzando l'API di Telegram:
   ```
   https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://crv-rugby-bot.onrender.com/webhook
   ```
3. Modifica il codice del bot per utilizzare i webhook invece del polling

## Risoluzione dei Problemi

### Il bot non risponde

1. Verifica che il servizio sia in esecuzione su Render
2. Controlla i log del servizio per eventuali errori
3. Assicurati che il token del bot sia corretto

### L'interfaccia web non funziona

1. Verifica che il servizio sia in esecuzione su Render
2. Controlla i log del servizio per eventuali errori
3. Assicurati che le variabili d'ambiente siano configurate correttamente

### Problemi con il database

1. Verifica che le credenziali Supabase siano corrette
2. Controlla che il database Supabase sia accessibile
3. Verifica che le tabelle necessarie esistano nel database