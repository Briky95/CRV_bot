# Interfaccia Web di Amministrazione per Rugby Bot

Questa interfaccia web permette di gestire facilmente il bot Telegram per il rugby attraverso un'interfaccia grafica intuitiva.

## Funzionalità

- **Dashboard**: Panoramica generale con statistiche e attività recenti
- **Gestione Utenti**: Approvazione e gestione degli utenti del bot
- **Gestione Partite**: Visualizzazione, modifica ed eliminazione delle partite
- **Gestione Squadre**: Aggiunta e modifica delle squadre
- **Statistiche**: Visualizzazione di statistiche dettagliate sulle partite e le squadre
- **Gestione Amministratori**: Aggiunta e gestione degli amministratori dell'interfaccia web

## Requisiti

- Python 3.7+
- Flask
- Flask-Login
- Werkzeug
- Pandas
- Bootstrap 5 (incluso via CDN)
- Font Awesome (incluso via CDN)
- Chart.js (incluso via CDN)

## Installazione

1. Assicurati di aver installato tutte le dipendenze:
   ```
   pip install -r requirements.txt
   ```

2. Avvia l'applicazione:
   ```
   ./start_web_admin.sh
   ```
   
   Oppure manualmente:
   ```
   python web_admin/app.py
   ```

3. Accedi all'interfaccia web all'indirizzo `http://localhost:8080`

## Credenziali di default

- Username: `admin`
- Password: `admin123`

**Importante**: Cambia la password predefinita dopo il primo accesso!

## Integrazione con il Bot

L'interfaccia web utilizza gli stessi file di dati del bot Telegram, quindi tutte le modifiche effettuate tramite l'interfaccia web saranno immediatamente disponibili per il bot e viceversa.

## Sicurezza

- L'interfaccia web utilizza Flask-Login per la gestione dell'autenticazione
- Le password sono memorizzate in modo sicuro utilizzando l'hashing
- Le sessioni scadono automaticamente dopo 2 ore di inattività

## Sviluppi futuri

- Integrazione diretta con l'API di Telegram per inviare messaggi
- Generazione di immagini condivisibili per i risultati delle partite
- Dashboard personalizzabile
- Sistema di notifiche
- Backup automatico dei dati