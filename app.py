import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_connection, init_db
from models import ProdutoFisico, ProdutoDigital

app = Flask(__name__)
app.secret_key = 'chave_secreta_stockcontrol_ads_anhanguera'

CATEGORIAS_CONFIG = {
    'Escritório': {'cor': 'primary', 'icone': '📎', 'texto': 'text-white'},
    'Copa e Cozinha': {'cor': 'warning', 'icone': '☕', 'texto': 'text-dark'},
    'Limpeza': {'cor': 'info', 'icone': '🧼', 'texto': 'text-dark'},
    'TI': {'cor': 'success', 'icone': '💻', 'texto': 'text-white'},
}

init_db()


@app.context_processor
def inject_categorias():
    return dict(categorias_config=CATEGORIAS_CONFIG)


def registrar_movimentacao(cursor, produto_nome, categoria, operacao, quantidade, observacao=""):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    usuario_logado = session.get('username', 'sistema')
    cursor.execute("""
        INSERT INTO movimentacoes (produto_nome, categoria, operacao, quantidade, usuario, observacao, data_hora)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (produto_nome, categoria, operacao, quantidade, usuario_logado, observacao.strip(), agora))


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
    categoria_filtro = request.args.get('categoria', 'Todas')
    busca = request.args.get('busca', '').strip()

    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM produtos WHERE 1=1"
    params = []

    if categoria_filtro and categoria_filtro != 'Todas':
        query += " AND categoria = ?"
        params.append(categoria_filtro)

    if busca:
        query += " AND nome LIKE ?"
        params.append(f"%{busca}%")

    query += " ORDER BY categoria ASC, nome ASC"
    cursor.execute(query, params)
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

        p.categoria = r['categoria'] if 'categoria' in r.keys() and r['categoria'] else 'Escritório'

        produtos.append(p)
        patrimonio_total += p.quantidade * p._preco_custo

        if getattr(p, 'alerta_reposicao', False):
            alertas_count += 1

    tema = CATEGORIAS_CONFIG.get(categoria_filtro, {'cor': 'primary', 'icone': '📦', 'texto': 'text-white'})

    return render_template(
        'index.html',
        produtos=produtos,
        patrimonio_total=patrimonio_total,
        alertas_count=alertas_count,
        categoria_filtro=categoria_filtro,
        busca=busca,
        tema=tema
    )


@app.route('/produto/novo', methods=['GET', 'POST'])
@login_obrigatorio
def novo_produto():
    categoria_inicial = request.args.get('categoria', 'Escritório')
    if categoria_inicial not in CATEGORIAS_CONFIG:
        categoria_inicial = 'Escritório'

    if request.method == 'POST':
        nome = request.form.get('nome')
        categoria = request.form.get('categoria', 'Escritório')
        tipo = request.form.get('tipo', 'ProdutoFisico')
        quantidade = int(request.form.get('quantidade', 0))
        estoque_minimo = int(request.form.get('estoque_minimo', 5))
        preco_custo = float(request.form.get('preco_custo', 0.0))
        preco_base_venda = float(request.form.get('preco_base_venda', preco_custo))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO produtos (nome, categoria, tipo, quantidade, estoque_minimo, preco_custo, preco_base_venda, ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (nome, categoria, tipo, quantidade, estoque_minimo, preco_custo, preco_base_venda))

        if quantidade > 0:
            registrar_movimentacao(cursor, nome, categoria, 'ENTRADA', quantidade, 'Saldo inicial no cadastro')

        conn.commit()
        conn.close()

        return redirect(url_for('index', categoria=categoria))

    tema = CATEGORIAS_CONFIG.get(categoria_inicial, {'cor': 'primary', 'icone': '📦', 'texto': 'text-white'})
    return render_template('produto_form.html', categoria_inicial=categoria_inicial, tema=tema)


@app.route('/produto/ajustar_estoque/<int:id_produto>', methods=['POST'])
@login_obrigatorio
def ajustar_estoque(id_produto):
    quantidade_ajuste = int(request.form.get('quantidade_ajuste', 0))
    operacao = request.form.get('operacao')
    observacao = request.form.get('observacao', '').strip()

    # Bloqueia movimentação caso a observação esteja vazia
    if not observacao:
        return redirect(request.referrer or url_for('index'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nome, categoria, quantidade FROM produtos WHERE id = ?", (id_produto,))
    row = cursor.fetchone()

    if row and quantidade_ajuste > 0:
        qtd_atual = row['quantidade']
        qtd_efetiva = min(qtd_atual, quantidade_ajuste) if operacao == 'SAIDA' else quantidade_ajuste
        nova_qtd = max(0, qtd_atual - quantidade_ajuste) if operacao == 'SAIDA' else qtd_atual + quantidade_ajuste

        cursor.execute("UPDATE produtos SET quantidade = ? WHERE id = ?", (nova_qtd, id_produto))
        if qtd_efetiva > 0:
            registrar_movimentacao(cursor, row['nome'], row['categoria'], operacao, qtd_efetiva, observacao)
        conn.commit()

    conn.close()
    return redirect(request.referrer or url_for('index'))


@app.route('/historico')
@login_obrigatorio
def historico():
    categoria_filtro = request.args.get('categoria', 'Todas')

    conn = get_connection()
    cursor = conn.cursor()

    if categoria_filtro and categoria_filtro != 'Todas':
        cursor.execute(
            "SELECT * FROM movimentacoes WHERE categoria = ? ORDER BY id DESC LIMIT 200",
            (categoria_filtro,)
        )
    else:
        cursor.execute("SELECT * FROM movimentacoes ORDER BY id DESC LIMIT 200")

    movimentacoes = cursor.fetchall()
    conn.close()

    tema = CATEGORIAS_CONFIG.get(categoria_filtro, {'cor': 'primary', 'icone': '📦', 'texto': 'text-white'})
    return render_template(
        'historico.html',
        movimentacoes=movimentacoes,
        categoria_filtro=categoria_filtro,
        tema=tema
    )


@app.route('/produto/inativar/<int:id_produto>', methods=['POST'])
@login_obrigatorio
def inativar_produto(id_produto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (id_produto,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))


@app.route('/produto/ativar/<int:id_produto>', methods=['POST'])
@login_obrigatorio
def ativar_produto(id_produto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE produtos SET ativo = 1 WHERE id = ?", (id_produto,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))


@app.route('/produto/deletar/<int:id_produto>', methods=['POST'])
@admin_obrigatorio
def deletar_produto(id_produto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM produtos WHERE id = ?", (id_produto,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)