# Meccanismo Keep-Alive per CRV Bot

Questo documento spiega il meccanismo di keep-alive implementato per mantenere attivo il bot Telegram su Render con il piano gratuito.

## Problema

Con il piano gratuito di Render, i servizi web vengono disattivati dopo 15 minuti di inattività. Questo causa l'interruzione del bot Telegram, che deve essere riavviato manualmente o attendere una nuova richiesta per tornare attivo.

## Soluzione

Per risolvere questo problema, è stato implementato un meccanismo di keep-alive che invia richieste periodiche al server per mantenerlo attivo. Questo meccanismo è composto da due componenti principali:

1. **Script keep_alive.py**: Questo script avvia un thread che invia richieste HTTP GET al server ogni 5 minuti.
2. **Integrazione in bot_fixed.py**: Il bot è stato modificato per avviare automaticamente il meccanismo di keep-alive quando viene eseguito su Render.

## Come funziona

1. Quando il bot viene avviato su Render, viene rilevato l'ambiente Render tramite la variabile d'ambiente `RENDER`.
2. Il bot avvia il meccanismo di keep-alive, che crea un thread separato per inviare richieste periodiche al server.
3. Il thread invia una richiesta HTTP GET all'URL del servizio Render ogni 5 minuti.
4. Queste richieste mantengono il server attivo, evitando che venga disattivato dopo 15 minuti di inattività.
5. Se il meccanismo di keep-alive si interrompe per qualche motivo, il bot tenta di riavviarlo automaticamente.

## Configurazione

Per utilizzare il meccanismo di keep-alive, è necessario configurare le seguenti variabili d'ambiente su Render:

- `RENDER`: Impostata a "true" per indicare che il bot è in esecuzione su Render.
- `RENDER_URL`: L'URL del servizio Render, ad esempio "https://crv-rugby-bot.onrender.com".

Queste variabili sono già configurate nel file `render.yaml`.

## Monitoraggio

Il meccanismo di keep-alive registra i log delle richieste inviate al server. È possibile monitorare questi log nella console di Render per verificare che il meccanismo stia funzionando correttamente.

## Limitazioni

- Il meccanismo di keep-alive non può garantire al 100% che il bot rimanga sempre attivo, ma riduce significativamente la probabilità che venga disattivato.
- Se il server viene riavviato da Render per qualsiasi motivo, il bot potrebbe comunque essere temporaneamente non disponibile.

## Suggerimenti

Se il bot viene utilizzato frequentemente, è consigliabile considerare l'upgrade a un piano a pagamento di Render per garantire che il bot rimanga sempre attivo senza la necessità di un meccanismo di keep-alive.