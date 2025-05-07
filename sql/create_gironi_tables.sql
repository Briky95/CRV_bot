-- Tabella per i tornei
CREATE TABLE IF NOT EXISTS tornei (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    genere TEXT NOT NULL,
    data_inizio TEXT NOT NULL,
    data_fine TEXT NOT NULL,
    descrizione TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabella per i gironi
CREATE TABLE IF NOT EXISTS gironi (
    id INTEGER PRIMARY KEY,
    torneo_id INTEGER NOT NULL REFERENCES tornei(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    descrizione TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabella per le squadre nei gironi
CREATE TABLE IF NOT EXISTS girone_squadre (
    id SERIAL PRIMARY KEY,
    girone_id INTEGER NOT NULL REFERENCES gironi(id) ON DELETE CASCADE,
    squadra TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(girone_id, squadra)
);

-- Tabella per le partite dei gironi
CREATE TABLE IF NOT EXISTS partite_girone (
    id SERIAL PRIMARY KEY,
    girone_id INTEGER NOT NULL REFERENCES gironi(id) ON DELETE CASCADE,
    data_partita TEXT NOT NULL,
    ora TEXT,
    squadra1 TEXT NOT NULL,
    squadra2 TEXT NOT NULL,
    punteggio1 INTEGER,
    punteggio2 INTEGER,
    mete1 INTEGER,
    mete2 INTEGER,
    luogo TEXT,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indici per migliorare le prestazioni
CREATE INDEX IF NOT EXISTS idx_gironi_torneo_id ON gironi(torneo_id);
CREATE INDEX IF NOT EXISTS idx_girone_squadre_girone_id ON girone_squadre(girone_id);
CREATE INDEX IF NOT EXISTS idx_partite_girone_girone_id ON partite_girone(girone_id);

-- Trigger per aggiornare automaticamente il campo updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tornei_updated_at
BEFORE UPDATE ON tornei
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_gironi_updated_at
BEFORE UPDATE ON gironi
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_partite_girone_updated_at
BEFORE UPDATE ON partite_girone
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

-- Politiche di sicurezza Row Level Security (RLS)
-- Abilita RLS per tutte le tabelle
ALTER TABLE tornei ENABLE ROW LEVEL SECURITY;
ALTER TABLE gironi ENABLE ROW LEVEL SECURITY;
ALTER TABLE girone_squadre ENABLE ROW LEVEL SECURITY;
ALTER TABLE partite_girone ENABLE ROW LEVEL SECURITY;

-- Crea politiche che consentono l'accesso completo all'utente autenticato
-- Nota: in un ambiente di produzione, dovresti limitare l'accesso in base ai ruoli
CREATE POLICY tornei_policy ON tornei FOR ALL USING (true);
CREATE POLICY gironi_policy ON gironi FOR ALL USING (true);
CREATE POLICY girone_squadre_policy ON girone_squadre FOR ALL USING (true);
CREATE POLICY partite_girone_policy ON partite_girone FOR ALL USING (true);