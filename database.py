import os
import sqlite3

# Nome do arquivo do banco de dados SQLite que será gerado automaticamente
DATABASE_NAME = "stockcontrol.db"


def get_connection():
    """
    Estabelece e retorna a conexão com o banco de dados SQLite.
    A propriedade row_factory permite acessar as colunas pelo nome (ex: row['nome']).
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Inicializa o banco de dados executando o script SQL contido em Database/schema.sql.
    """
    # Caminho apontando para a pasta Database criada por você
    schema_path = os.path.join("Database", "schema.sql")

    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            script = f.read()

        conn = get_connection()
        conn.executescript(script)
        conn.commit()
        conn.close()
        print(
            "✅ Banco de dados SQLite inicializado com sucesso em 'stockcontrol.db'!"
        )
    else:
        print(
            f"⚠️ Arquivo '{schema_path}' não foi encontrado. Verifique a pasta Database."
        )


if __name__ == "__main__":
    # Teste de execução direta no terminal do VS Code
    init_db()