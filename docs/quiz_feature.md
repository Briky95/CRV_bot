# Funzionalità Quiz Educativi sul Rugby

Questa documentazione descrive la funzionalità di quiz educativi sul rugby implementata nel bot CRV Rugby.

## Panoramica

La funzionalità di quiz permette di:

1. Inviare automaticamente quiz educativi sul rugby nel canale Telegram
2. Permettere agli utenti di rispondere direttamente nel canale
3. Tenere traccia delle risposte e dei punteggi degli utenti
4. Generare automaticamente nuovi quiz utilizzando l'intelligenza artificiale
5. Gestire i quiz attraverso un'interfaccia amministrativa

## Struttura dei Quiz

Ogni quiz è composto da:

- **Domanda**: Una domanda sul rugby
- **Opzioni**: Quattro possibili risposte
- **Risposta corretta**: L'indice dell'opzione corretta (0-3)
- **Spiegazione**: Una spiegazione dettagliata della risposta corretta
- **Categoria**: La categoria tematica del quiz (es. Regole, Storia, ecc.)

## Categorie di Quiz

I quiz sono organizzati nelle seguenti categorie:

1. **Regole del Rugby**: Domande sulle regole ufficiali del rugby
2. **Storia del Rugby**: Domande sulla storia del rugby mondiale e italiano
3. **Tecnica e Tattica**: Domande su tecniche di gioco e tattiche
4. **Rugby Veneto**: Domande specifiche sul rugby nella regione Veneto
5. **Giocatori Famosi**: Domande sui giocatori famosi del rugby
6. **Competizioni Internazionali**: Domande sulle competizioni internazionali
7. **Curiosità sul Rugby**: Domande curiose e interessanti sul rugby

## Funzionalità per gli Utenti

Gli utenti del canale possono:

1. **Rispondere ai quiz**: Selezionando una delle opzioni proposte
2. **Ricevere feedback**: Ricevere un messaggio privato con il risultato e la spiegazione
3. **Visualizzare la classifica**: Vedere la classifica dei partecipanti più attivi
4. **Guadagnare punti**: Accumulare punti rispondendo correttamente ai quiz

## Funzionalità per gli Amministratori

Gli amministratori del bot possono:

1. **Gestire i quiz**: Aggiungere, modificare o eliminare quiz
2. **Generare quiz con IA**: Creare automaticamente nuovi quiz utilizzando l'IA
3. **Approvare/rifiutare quiz**: Revisionare i quiz generati dall'IA prima di aggiungerli
4. **Inviare quiz manualmente**: Inviare quiz al canale in qualsiasi momento
5. **Visualizzare statistiche**: Vedere statistiche dettagliate sulla partecipazione

## Generazione Automatica di Quiz

La funzionalità di generazione automatica utilizza l'API di OpenAI per creare nuovi quiz educativi sul rugby. Il processo è il seguente:

1. L'amministratore seleziona quanti quiz generare
2. L'IA crea i quiz in base alle categorie predefinite
3. I quiz generati vengono salvati in una lista di attesa
4. L'amministratore può visualizzare, approvare o rifiutare i quiz generati
5. I quiz approvati vengono aggiunti al database principale

## Invio Automatico dei Quiz

I quiz vengono inviati automaticamente al canale Telegram:

- **Frequenza**: Un quiz al giorno
- **Orario**: Alle 12:00
- **Risultati**: I risultati del quiz precedente vengono mostrati prima del nuovo quiz

## Comandi Disponibili

- `/quiz`: Apre il menu di gestione dei quiz (solo per amministratori)
- `/test_quiz`: Invia un quiz di test al canale di test (solo per amministratori)

## Configurazione

Per utilizzare la funzionalità di quiz, è necessario configurare le seguenti variabili d'ambiente:

```
BOT_TOKEN=your_telegram_bot_token
CHANNEL_ID=@your_channel_name
TEST_CHANNEL_ID=@your_test_channel_id
OPENAI_API_KEY=your_openai_api_key
```

## Struttura dei File

- `modules/quiz_manager.py`: Gestione dei quiz e delle statistiche
- `modules/quiz_generator.py`: Generazione automatica di quiz con IA
- `modules/quiz_handlers.py`: Gestori per i comandi relativi ai quiz
- `test_quiz.py`: Script per testare la funzionalità dei quiz
- `data/quiz.json`: Database dei quiz approvati
- `data/quiz_stats.json`: Statistiche di partecipazione
- `data/quiz_pending.json`: Quiz in attesa di approvazione

## Estensioni Future

Possibili estensioni future della funzionalità:

1. **Quiz tematici**: Quiz speciali per eventi o tornei specifici
2. **Sfide tra utenti**: Permettere agli utenti di sfidarsi a vicenda
3. **Quiz multimediali**: Aggiungere immagini o video ai quiz
4. **Livelli di difficoltà**: Implementare diversi livelli di difficoltà
5. **Integrazione con l'interfaccia web**: Gestire i quiz anche dall'interfaccia web