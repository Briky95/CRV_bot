# Telegram Rugby Bot

## 🚀 Istruzioni per l'uso (macOS + VS Code)

### 1. Scompatta il pacchetto ZIP
Apri il terminale e posizionati dove vuoi salvare il progetto, poi esegui:
```
unzip telegram_rugby_bot.zip
cd telegram_rugby_bot
```

### 2. Configura l'ambiente di sviluppo
Usa lo script di configurazione per creare l'ambiente virtuale e installare le dipendenze:
```
chmod +x setup_dev.sh
./setup_dev.sh
source .venv/bin/activate
```

### 3. Inserisci il token del tuo bot
Crea un file `.env` nella directory principale e aggiungi:
```
BOT_TOKEN=il_tuo_token_telegram
```
Sostituisci `il_tuo_token_telegram` con il token che ti ha dato BotFather.

### 4. Avvia il bot
```
python bot_fixed.py
```

### 5. Provalo in Telegram
Apri la chat con il tuo bot e invia `/start`. Dovrebbe rispondere con "Ciao! Il bot è attivo."

## 🚀 Deploy su AWS Lambda

Per deployare il bot su AWS Lambda, consulta il file `README_AWS_DEPLOY.md`.

### Configurazione per il deploy
```
chmod +x setup_lambda.sh
./setup_lambda.sh
source .venv_lambda/bin/activate
```

## ℹ️ Nota sulle versioni

Questo progetto utilizza `python-telegram-bot==20.7` (la versione più recente) sia per l'ambiente di sviluppo che per AWS Lambda per garantire l'accesso a tutte le funzionalità più recenti.

I file di requisiti separati (`requirements-dev.txt` e `requirements-lambda.txt`) contengono configurazioni leggermente diverse ottimizzate per i rispettivi ambienti, ma mantengono la stessa versione delle librerie principali.

**Nota**: L'utilizzo della versione 20.x su AWS Lambda potrebbe richiedere configurazioni aggiuntive per gestire le funzionalità asincrone.
