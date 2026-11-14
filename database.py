import os
import sqlite3
from werkzeug.security import generate_password_hash

DATABASE_NAME = "stockcontrol.db"


def get_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    schema_path = os.path.join("database", "schema.sql")

    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            script = f.read()

        conn = get_connection()
        conn.executescript(script)
        cursor = conn.cursor()

        # Garante que a coluna 'perfil' exista mesmo em bancos já criados anteriormente
        cursor.execute("PRAGMA table_info(usuarios)")
        colunas = [col[1] for col in cursor.fetchall()]
        if "perfil" not in colunas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN perfil TEXT NOT NULL DEFAULT 'operador'")

        # Garante que o usuário 'admin' exista com perfil 'admin' (root)
        cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
        if not cursor.fetchone():
            senha_criptografada = generate_password_hash("1234")
            cursor.execute(
                "INSERT INTO usuarios (username, senha_hash, perfil) VALUES (?, ?, ?)",
                ("admin", senha_criptografada, "admin"),
            )
        else:
            cursor.execute("UPDATE usuarios SET perfil = 'admin' WHERE username = 'admin'")

        conn.commit()
        conn.close()
        print("✅ Banco de dados e perfil root inicializados com sucesso!")
    else:
        print(f"⚠️ Arquivo '{schema_path}' não encontrado.")


if __name__ == "__main__":
    init_db()