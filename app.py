from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
from database import get_connection, init_db
from models import ProdutoFisico, ProdutoDigital

app = Flask(__name__)
app.secret_key = 'chave_secreta_stockcontrol_ads_anhanguera'

# Garante que o banco, as tabelas e o usuário admin existem ao iniciar
init_db()


# Decorador que exige login para acessar as páginas do sistema
def login_obrigatorio(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
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
        cursor.execute("SELECT id, username, senha_hash FROM usuarios WHERE username = ?", (username,))
        usuario = cursor.fetchone()
        conn.close()

        if usuario and check_password_hash(usuario['senha_hash'], senha):
            session['usuario_id'] = usuario['id']
            session['username'] = usuario['username']
            return redirect(url_for('index'))
        else:
            erro = 'Usuário ou senha inválidos.'

    return render_template('login.html', erro=erro)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


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
@login_obrigatorio
def deletar_produto(id_produto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM produtos WHERE id = ?", (id_produto,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)