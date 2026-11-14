import csv
import io
import sqlite3
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, Response
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_connection, init_db
from models import ProdutoFisico, ProdutoDigital

app = Flask(__name__)
app.secret_key = 'chave_secreta_stockcontrol_ads_anhanguera'

FUSO_BR = timezone(timedelta(hours=-3))

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


def agora_br():
    return datetime.now(FUSO_BR)


def registrar_movimentacao(cursor, produto_nome, categoria, operacao, quantidade, observacao=""):
    agora = agora_br().strftime("%d/%m/%Y %H:%M")
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
        item_dict = dict(r)
        if item_dict['tipo'] == 'ProdutoFisico':
            p = ProdutoFisico(
                id_produto=item_dict['id'],
                nome=item_dict['nome'],
                preco_custo=item_dict['preco_custo'],
                preco_base_venda=item_dict['preco_base_venda'],
                quantidade=item_dict['quantidade'],
                peso_kg=item_dict.get('peso_kg') or 1.0,
                estoque_minimo=item_dict.get('estoque_minimo') or 5,
                ativo=bool(item_dict['ativo'])
            )
        else:
            p = ProdutoDigital(
                id_produto=item_dict['id'],
                nome=item_dict['nome'],
                preco_custo=item_dict['preco_custo'],
                preco_base_venda=item_dict['preco_base_venda'],
                quantidade=item_dict['quantidade'],
                link_download=item_dict.get('link_download') or '',
                tamanho_mb=item_dict.get('tamanho_mb') or 0.0,
                ativo=bool(item_dict['ativo'])
            )

        p.categoria = item_dict.get('categoria') or 'Escritório'

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


@app.route('/produto/editar/<int:id_produto>', methods=['GET', 'POST'])
@login_obrigatorio
def editar_produto(id_produto):
    if request.method == 'GET':
        return redirect(url_for('index'))

    nome = request.form.get('nome', '').strip()
    categoria = request.form.get('categoria', 'Escritório')
    estoque_minimo = int(request.form.get('estoque_minimo', 5))
    preco_custo = float(request.form.get('preco_custo', 0.0))
    preco_base_venda = float(request.form.get('preco_base_venda', preco_custo))

    if nome:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE produtos
            SET nome = ?, categoria = ?, estoque_minimo = ?, preco_custo = ?, preco_base_venda = ?
            WHERE id = ?
        """, (nome, categoria, estoque_minimo, preco_custo, preco_base_venda, id_produto))
        conn.commit()
        conn.close()

    return redirect(request.referrer or url_for('index'))


@app.route('/produto/ajustar_estoque/<int:id_produto>', methods=['GET', 'POST'])
@login_obrigatorio
def ajustar_estoque(id_produto):
    if request.method == 'GET':
        return redirect(url_for('index'))

    quantidade_ajuste = int(request.form.get('quantidade_ajuste', 0))
    operacao = request.form.get('operacao')
    observacao = request.form.get('observacao', '').strip()

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


# --- ROTA DE EXPORTAÇÃO CSV (SOMENTE DO HISTÓRICO, SEPARADO POR CATEGORIA) ---

@app.route('/exportar/historico')
@login_obrigatorio
def exportar_historico():
    categoria_filtro = request.args.get('categoria', '').strip()

    conn = get_connection()
    cursor = conn.cursor()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', lineterminator='\r\n')

    cabecalho = [
        'Data e Hora',
        'Operacao',
        'Item',
        'Categoria',
        'Quantidade',
        'Responsavel',
        'Observacao / Destino'
    ]

    if categoria_filtro and categoria_filtro != 'Todas':
        # Exporta apenas a categoria selecionada
        cursor.execute(
            "SELECT * FROM movimentacoes WHERE TRIM(categoria) = ? ORDER BY id DESC",
            (categoria_filtro,)
        )
        rows = cursor.fetchall()

        writer.writerow([f"RELATORIO DE MOVIMENTACOES - SETOR: {categoria_filtro.upper()}"])
        writer.writerow(cabecalho)

        for r in rows:
            m = dict(r)
            writer.writerow([
                m.get('data_hora'),
                m.get('operacao'),
                m.get('produto_nome'),
                m.get('categoria'),
                m.get('quantidade'),
                m.get('usuario'),
                m.get('observacao') or ''
            ])
    else:
        # Exporta TODAS já separadas em blocos por categoria
        categoria_filtro = 'Todas'
        cursor.execute("SELECT * FROM movimentacoes ORDER BY categoria ASC, id DESC")
        rows = [dict(r) for r in cursor.fetchall()]

        # Descobre todas as categorias presentes (mantendo a ordem principal primeiro)
        categorias_presentes = list(CATEGORIAS_CONFIG.keys())
        for m in rows:
            cat_item = (m.get('categoria') or 'Sem Categoria').strip()
            if cat_item not in categorias_presentes:
                categorias_presentes.append(cat_item)

        primeiro_bloco = True
        for cat in categorias_presentes:
            itens_cat = [m for m in rows if (m.get('categoria') or 'Sem Categoria').strip() == cat]
            if not itens_cat:
                continue

            if not primeiro_bloco:
                writer.writerow([])  # Linha em branco separando cada categoria
            primeiro_bloco = False

            writer.writerow([f"=== CATEGORIA: {cat.upper()} ==="])
            writer.writerow(cabecalho)

            for m in itens_cat:
                writer.writerow([
                    m.get('data_hora'),
                    m.get('operacao'),
                    m.get('produto_nome'),
                    m.get('categoria'),
                    m.get('quantidade'),
                    m.get('usuario'),
                    m.get('observacao') or ''
                ])

    conn.close()

    conteudo_bytes = output.getvalue().encode('utf-8-sig')
    nome_arquivo = f"historico_movimentacoes_{categoria_filtro.lower().replace(' ', '_')}_{agora_br().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        conteudo_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={nome_arquivo}",
            "Content-Length": str(len(conteudo_bytes)),
            "Cache-Control": "no-store"
        }
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