CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL,
    categoria TEXT NOT NULL DEFAULT 'Escritório',
    quantidade INTEGER NOT NULL DEFAULT 0,
    preco_custo REAL NOT NULL DEFAULT 0.0,
    preco_base_venda REAL NOT NULL DEFAULT 0.0,
    peso_kg REAL DEFAULT 1.0,
    estoque_minimo INTEGER DEFAULT 5,
    link_download TEXT,
    tamanho_mb REAL DEFAULT 0.0,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL DEFAULT 'operador'
);
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL DEFAULT 'operador'
);

CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL,
    categoria TEXT NOT NULL DEFAULT 'Escritório',
    quantidade INTEGER NOT NULL DEFAULT 0,
    preco_custo REAL NOT NULL DEFAULT 0.0,
    preco_base_venda REAL NOT NULL DEFAULT 0.0,
    peso_kg REAL DEFAULT 1.0,
    estoque_minimo INTEGER DEFAULT 5,
    link_download TEXT,
    tamanho_mb REAL DEFAULT 0.0,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS movimentacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    operacao TEXT NOT NULL,
    quantidade INTEGER NOT NULL,
    usuario TEXT NOT NULL,
    observacao TEXT,
    data_hora TEXT NOT NULL
);