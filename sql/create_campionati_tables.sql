-- Tabella per le stagioni sportive
CREATE TABLE IF NOT EXISTS stagioni (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    data_inizio DATE NOT NULL,
    data_fine DATE NOT NULL,
    attiva BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabella per i campionati
CREATE TABLE IF NOT EXISTS campionati (
    id SERIAL PRIMARY KEY,
    stagione_id INTEGER NOT NULL REFERENCES stagioni(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    genere TEXT NOT NULL,
    descrizione TEXT,
    formato TEXT NOT NULL, -- 'girone', 'eliminazione', 'misto'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabella per le squadre partecipanti ai campionati
CREATE TABLE IF NOT EXISTS campionato_squadre (
    id SERIAL PRIMARY KEY,
    campionato_id INTEGER NOT NULL REFERENCES campionati(id) ON DELETE CASCADE,
    squadra TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campionato_id, squadra)
);

-- Tabella per gli arbitri
CREATE TABLE IF NOT EXISTS arbitri (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    cognome TEXT NOT NULL,
    email TEXT,
    telefono TEXT,
    livello TEXT, -- 'regionale', 'nazionale', 'internazionale'
    attivo BOOLEAN DEFAULT TRUE,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabella per le partite dei campionati
CREATE TABLE IF NOT EXISTS partite_campionato (
    id SERIAL PRIMARY KEY,
    campionato_id INTEGER NOT NULL REFERENCES campionati(id) ON DELETE CASCADE,
    giornata INTEGER,
    data_partita DATE NOT NULL,
    ora TIME,
    squadra_casa TEXT NOT NULL,
    squadra_trasferta TEXT NOT NULL,
    punteggio_casa INTEGER,
    punteggio_trasferta INTEGER,
    mete_casa INTEGER,
    mete_trasferta INTEGER,
    luogo TEXT,
    note TEXT,
    stato TEXT DEFAULT 'programmata', -- 'programmata', 'in_corso', 'completata', 'rinviata', 'annullata'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabella per le designazioni arbitrali
CREATE TABLE IF NOT EXISTS designazioni_arbitrali (
    id SERIAL PRIMARY KEY,
    partita_id INTEGER NOT NULL REFERENCES partite_campionato(id) ON DELETE CASCADE,
    arbitro_id INTEGER NOT NULL REFERENCES arbitri(id) ON DELETE CASCADE,
    ruolo TEXT NOT NULL, -- 'primo', 'secondo', 'TMO', 'quarto_uomo', 'giudice_di_linea'
    confermata BOOLEAN DEFAULT FALSE,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(partita_id, arbitro_id, ruolo)
);

-- Tabella per la classifica dei campionati
CREATE TABLE IF NOT EXISTS classifica_campionato (
    id SERIAL PRIMARY KEY,
    campionato_id INTEGER NOT NULL REFERENCES campionati(id) ON DELETE CASCADE,
    squadra TEXT NOT NULL,
    punti INTEGER DEFAULT 0,
    partite_giocate INTEGER DEFAULT 0,
    vittorie INTEGER DEFAULT 0,
    pareggi INTEGER DEFAULT 0,
    sconfitte INTEGER DEFAULT 0,
    mete_fatte INTEGER DEFAULT 0,
    mete_subite INTEGER DEFAULT 0,
    punti_fatti INTEGER DEFAULT 0,
    punti_subiti INTEGER DEFAULT 0,
    bonus_offensivi INTEGER DEFAULT 0, -- Bonus per 4+ mete
    bonus_difensivi INTEGER DEFAULT 0, -- Bonus per sconfitta con meno di 8 punti
    penalizzazioni INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campionato_id, squadra)
);

-- Indici per migliorare le prestazioni
CREATE INDEX IF NOT EXISTS idx_campionati_stagione_id ON campionati(stagione_id);
CREATE INDEX IF NOT EXISTS idx_campionato_squadre_campionato_id ON campionato_squadre(campionato_id);
CREATE INDEX IF NOT EXISTS idx_partite_campionato_campionato_id ON partite_campionato(campionato_id);
CREATE INDEX IF NOT EXISTS idx_designazioni_arbitrali_partita_id ON designazioni_arbitrali(partita_id);
CREATE INDEX IF NOT EXISTS idx_designazioni_arbitrali_arbitro_id ON designazioni_arbitrali(arbitro_id);
CREATE INDEX IF NOT EXISTS idx_classifica_campionato_campionato_id ON classifica_campionato(campionato_id);

-- Trigger per aggiornare automaticamente il campo updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_stagioni_updated_at
BEFORE UPDATE ON stagioni
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_campionati_updated_at
BEFORE UPDATE ON campionati
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_arbitri_updated_at
BEFORE UPDATE ON arbitri
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_partite_campionato_updated_at
BEFORE UPDATE ON partite_campionato
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_designazioni_arbitrali_updated_at
BEFORE UPDATE ON designazioni_arbitrali
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_classifica_campionato_updated_at
BEFORE UPDATE ON classifica_campionato
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

-- Politiche di sicurezza Row Level Security (RLS)
ALTER TABLE stagioni ENABLE ROW LEVEL SECURITY;
ALTER TABLE campionati ENABLE ROW LEVEL SECURITY;
ALTER TABLE campionato_squadre ENABLE ROW LEVEL SECURITY;
ALTER TABLE arbitri ENABLE ROW LEVEL SECURITY;
ALTER TABLE partite_campionato ENABLE ROW LEVEL SECURITY;
ALTER TABLE designazioni_arbitrali ENABLE ROW LEVEL SECURITY;
ALTER TABLE classifica_campionato ENABLE ROW LEVEL SECURITY;

-- Crea politiche che consentono l'accesso completo all'utente autenticato
CREATE POLICY stagioni_policy ON stagioni FOR ALL USING (true);
CREATE POLICY campionati_policy ON campionati FOR ALL USING (true);
CREATE POLICY campionato_squadre_policy ON campionato_squadre FOR ALL USING (true);
CREATE POLICY arbitri_policy ON arbitri FOR ALL USING (true);
CREATE POLICY partite_campionato_policy ON partite_campionato FOR ALL USING (true);
CREATE POLICY designazioni_arbitrali_policy ON designazioni_arbitrali FOR ALL USING (true);
CREATE POLICY classifica_campionato_policy ON classifica_campionato FOR ALL USING (true);