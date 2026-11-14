import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_connection, init_db
from models import ProdutoFisico, ProdutoDigital

app = Flask(__name__)
app.secret_key = 'chave_secreta_stockcontrol_ads_anhanguera'

# Garante que o banco, as tabelas e o usuário admin existem ao iniciar
init_db()


def login_obrigatorio(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_obrigatorio(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        if session.get('perfil') != 'admin':
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        username = request.form.get('username')
        senha = request.form.get('senha')

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, senha_hash, perfil FROM usuarios WHERE username = ?", (username,))
        usuario = cursor.fetchone()
        conn.close()

        if usuario and check_password_hash(usuario['senha_hash'], senha):
            session['usuario_id'] = usuario['id']
            session['username'] = usuario['username']
            session['perfil'] = usuario['perfil']
            return redirect(url_for('index'))
        else:
            erro = 'Usuário ou senha inválidos.'

    return render_template('login.html', erro=erro)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- ROTAS DE GERENCIAMENTO DE USUÁRIOS (ROOT) ---

@app.route('/usuarios', methods=['GET', 'POST'])
@admin_obrigatorio
def gerenciar_usuarios():
    mensagem = None
    tipo_alerta = "success"

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        novo_username = request.form.get('username', '').strip()
        nova_senha = request.form.get('senha', '')
        perfil = request.form.get('perfil', 'operador')

        if novo_username and nova_senha:
            try:
                senha_hash = generate_password_hash(nova_senha)
                cursor.execute(
                    "INSERT INTO usuarios (username, senha_hash, perfil) VALUES (?, ?, ?)",
                    (novo_username, senha_hash, perfil)
                )
                conn.commit()
                mensagem = f"Usuário '{novo_username}' criado com sucesso!"
            except sqlite3.IntegrityError:
                mensagem = f"Erro: o usuário '{novo_username}' já existe."
                tipo_alerta = "danger"

    cursor.execute("SELECT id, username, perfil FROM usuarios ORDER BY id ASC")
    usuarios = cursor.fetchall()
    conn.close()

    return render_template('usuarios.html', usuarios=usuarios, mensagem=mensagem, tipo_alerta=tipo_alerta)


@app.route('/usuarios/editar/<int:id_usuario>', methods=['POST'])
@admin_obrigatorio
def editar_usuario(id_usuario):
    username = request.form.get('username', '').strip()
    nova_senha = request.form.get('nova_senha', '')
    perfil = request.form.get('perfil', 'operador')

    conn = get_connection()
    cursor = conn.cursor()

    # Impede rebaixar ou renomear o root principal 'admin'
    cursor.execute("SELECT username FROM usuarios WHERE id = ?", (id_usuario,))
    alvo = cursor.fetchone()

    if alvo:
        if alvo['username'] == 'admin':
            username = 'admin'
            perfil = 'admin'

        if nova_senha:
            senha_hash = generate_password_hash(nova_senha)
            cursor.execute(
                "UPDATE usuarios SET username = ?, senha_hash = ?, perfil = ? WHERE id = ?",
                (username, senha_hash, perfil, id_usuario)
            )
        else:
            cursor.execute(
                "UPDATE usuarios SET username = ?, perfil = ? WHERE id = ?",
                (username, perfil, id_usuario)
            )
        conn.commit()

    conn.close()
    return redirect(url_for('gerenciar_usuarios'))


@app.route('/usuarios/deletar/<int:id_usuario>', methods=['POST'])
@admin_obrigatorio
def deletar_usuario(id_usuario):
    conn = get_connection()
    cursor = conn.cursor()

    # Protege o root principal 'admin' e impede autoexclusão
    cursor.execute("SELECT username FROM usuarios WHERE id = ?", (id_usuario,))
    alvo = cursor.fetchone()

    if alvo and alvo['username'] != 'admin' and id_usuario != session.get('usuario_id'):
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (id_usuario,))
        conn.commit()

    conn.close()
    return redirect(url_for('gerenciar_usuarios'))


# --- ROTAS DO ESTOQUE ---

@app.route('/')
@login_obrigatorio
def index():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM produtos")
    rows = cursor.fetchall()
    conn.close()

    produtos = []
    patrimonio_total = 0.0
    alertas_count = 0

    for r in rows:
        if r['tipo'] == 'ProdutoFisico':
            p = ProdutoFisico(
                id_produto=r['id'],
                nome=r['nome'],
                preco_custo=r['preco_custo'],
                preco_base_venda=r['preco_base_venda'],
                quantidade=r['quantidade'],
                peso_kg=r['peso_kg'] or 1.0,
                estoque_minimo=r['estoque_minimo'] or 5,
                ativo=bool(r['ativo'])
            )
        else:
            p = ProdutoDigital(
                id_produto=r['id'],
                nome=r['nome'],
                preco_custo=r['preco_custo'],
                preco_base_venda=r['preco_base_venda'],
                quantidade=r['quantidade'],
                link_download=r['link_download'] or '',
                tamanho_mb=r['tamanho_mb'] or 0.0,
                ativo=bool(r['ativo'])
            )

        produtos.append(p)
        patrimonio_total += p.quantidade * p._preco_custo

        if getattr(p, 'alerta_reposicao', False):
            alertas_count += 1

    return render_template('index.html', produtos=produtos, patrimonio_total=patrimonio_total, alertas_count=alertas_count)


@app.route('/produto/novo', methods=['GET', 'POST'])
@login_obrigatorio
def novo_produto():
    if request.method == 'POST':
        nome = request.form.get('nome')
        tipo = request.form.get('tipo')
        quantidade = int(request.form.get('quantidade', 0))
        preco_custo = float(request.form.get('preco_custo', 0.0))
        preco_base_venda = float(request.form.get('preco_base_venda', 0.0))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO produtos (nome, tipo, quantidade, preco_custo, preco_base_venda, ativo)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (nome, tipo, quantidade, preco_custo, preco_base_venda))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    return render_template('produto_form.html')


@app.route('/produto/ajustar_estoque/<int:id_produto>', methods=['POST'])
@login_obrigatorio
def ajustar_estoque(id_produto):
    quantidade_ajuste = int(request.form.get('quantidade_ajuste', 0))
    operacao = request.form.get('operacao')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT quantidade FROM produtos WHERE id = ?", (id_produto,))
    row = cursor.fetchone()

    if row:
        qtd_atual = row['quantidade']
        nova_qtd = max(0, qtd_atual - quantidade_ajuste) if operacao == 'SAIDA' else qtd_atual + quantidade_ajuste
        cursor.execute("UPDATE produtos SET quantidade = ? WHERE id = ?", (nova_qtd, id_produto))
        conn.commit()

    conn.close()
    return redirect(url_for('index'))


@app.route('/produto/inativar/<int:id_produto>', methods=['POST'])
@login_obrigatorio
def inativar_produto(id_produto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (id_produto,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


@app.route('/produto/ativar/<int:id_produto>', methods=['POST'])
@login_obrigatorio
def ativar_produto(id_produto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE produtos SET ativo = 1 WHERE id = ?", (id_produto,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


@app.route('/produto/deletar/<int:id_produto>', methods=['POST'])
@admin_obrigatorio
def deletar_produto(id_produto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM produtos WHERE id = ?", (id_produto,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)