CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL,
    preco_custo REAL NOT NULL,
    preco_base_venda REAL NOT NULL,
    quantidade INTEGER NOT NULL DEFAULT 0,
    peso_kg REAL,
    estoque_minimo INTEGER DEFAULT 5,
    link_download TEXT,
    tamanho_mb REAL,
    ativo INTEGER NOT NULL DEFAULT 1
);