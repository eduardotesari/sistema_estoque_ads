from abc import ABC, abstractmethod

class Produto(ABC):
    """
    Classe Abstrata Base que representa um Produto genérico no sistema.
    """

    def __init__(self, id_produto: int, nome: str, preco_custo: float, preco_base_venda: float, quantidade: int, ativo: bool = True):
        self.id_produto = id_produto
        self.nome = nome
        self.ativo = ativo

        # Atributos encapsulados (protegidos)
        self._preco_custo = 0.0
        self._preco_base_venda = 0.0
        self._quantidade = 0

        # Aplicação dos setters com validação
        self.preco_custo = preco_custo
        self.preco_base_venda = preco_base_venda
        self.quantidade = quantidade
    # --- GETTERS E SETTERS (Encapsulamento) ---

    @property
    def preco_custo(self) -> float:
        return self._preco_custo

    @preco_custo.setter
    def preco_custo(self, valor: float):
        if valor < 0:
            raise ValueError("O preço de custo não pode ser negativo.")
        self._preco_custo = float(valor)

    @property
    def preco_base_venda(self) -> float:
        return self._preco_base_venda

    @preco_base_venda.setter
    def preco_base_venda(self, valor: float):
        if valor < 0:
            raise ValueError("O preço de venda não pode ser negativo.")
        self._preco_base_venda = float(valor)

    @property
    def quantidade(self) -> int:
        return self._quantidade

    @quantidade.setter
    def quantidade(self, valor: int):
        if valor < 0:
            raise ValueError("A quantidade em estoque não pode ser negativa.")
        self._quantidade = int(valor)

    # --- MÉTODOS DE NEGÓCIO ---

    def adicionar_estoque(self, qtd: int):
        """Aumenta a quantidade em estoque."""
        if qtd <= 0:
            raise ValueError("A quantidade adicionada deve ser maior que zero.")
        self._quantidade += qtd

    def dar_baixa_estoque(self, qtd: int):
        """Reduz a quantidade em estoque caso haja saldo suficiente."""
        if qtd <= 0:
            raise ValueError("A quantidade de baixa deve ser maior que zero.")
        if qtd > self._quantidade:
            raise ValueError(
                f"Estoque insuficiente. Saldo atual: {self._quantidade}"
            )
        self._quantidade -= qtd

    def calcular_patrimonio_total(self) -> float:
        """Calcula o valor total investido no estoque deste produto."""
        return self._quantidade * self._preco_custo

    # --- MÉTODOS ABSTRATOS (Polimorfismo) ---

    @abstractmethod
    def calcular_valor_venda(self) -> float:
        """Polimorfismo: Cada tipo de produto calcula o preço final de venda de forma diferente."""
        pass

    @property
    @abstractmethod
    def alerta_reposicao(self) -> bool:
        """Polimorfismo: Regra de alerta de baixo estoque específica por tipo."""
        pass


class ProdutoFisico(Produto):
    """
    Representa produtos físicos armazenados em prateleira/depósito.
    Herda da classe Produto.
    """
    def __init__(self, id_produto: int, nome: str, preco_custo: float, preco_base_venda: float, quantidade: int, peso_kg: float = 1.0, estoque_minimo: int = 5, ativo: bool = True):
        super().__init__(id_produto, nome, preco_custo, preco_base_venda, quantidade, ativo=ativo)
        self.peso_kg = peso_kg
        self.estoque_minimo = estoque_minimo

    # Implementação Polimórfica: Adiciona taxa de manuseio/frete base ao valor
    def calcular_valor_venda(self) -> float:
        taxa_manuseio = 2.50 if self.peso_kg > 1.0 else 1.00
        return self.preco_base_venda + taxa_manuseio

    # Implementação Polimórfica: Alerta se a quantidade for menor ou igual ao estoque mínimo estipulado
    @property
    def alerta_reposicao(self) -> bool:
        return self.quantidade <= self.estoque_minimo


class ProdutoDigital(Produto):
    """
    Representa produtos digitais (softwares, e-books, licenças).
    Herda da classe Produto.
    """
    def __init__(self, id_produto: int, nome: str, preco_custo: float, preco_base_venda: float, quantidade: int, link_download: str = "", tamanho_mb: float = 0.0, ativo: bool = True):
        super().__init__(id_produto, nome, preco_custo, preco_base_venda, quantidade, ativo=ativo)
        self.link_download = link_download
        self.tamanho_mb = tamanho_mb

    # Implementação Polimórfica: Não possui taxas logísticas adicionais
    def calcular_valor_venda(self) -> float:
        return self.preco_base_venda

    # Implementação Polimórfica: Produtos digitais com licenças limitadas avisam reposição abaixo de 2 unidades
    @property
    def alerta_reposicao(self) -> bool:
        return self.quantidade <= 2


# ==============================================================================
# TESTE DAS CLASSES (Exemplo de execução)
# ==============================================================================
if __name__ == "__main__":
    print("--- TESTANDO REGRAS DE POO DO STOCKCONTROL WEB ---\n")

    # 1. Instanciando Produto Físico
    mouse = ProdutoFisico(
        id_produto=1,
        nome="Mouse Sem Fio Ergonomico",
        preco_custo=25.00,
        preco_base_venda=60.00,
        quantidade=4,  # Abaixo do estoque mínimo (5)
        peso_kg=0.25,
        estoque_minimo=5,
    )

    # 2. Instanciando Produto Digital
    ebook = ProdutoDigital(
        id_produto=2,
        nome="E-book Guia de Python e Flask",
        preco_custo=5.00,
        preco_base_venda=29.90,
        quantidade=10,
        link_download="https://empresa.com/downloads/ebook-python.pdf",
        tamanho_mb=15.4,
    )

    # Demonstrando Encapsulamento, Polimorfismo e Negócio
    produtos = [mouse, ebook]

    for p in produtos:
        print(f"Produto: {p.nome}")
        print(f"Tipo: {p.__class__.__name__}")
        print(f"Quantidade em estoque: {p.quantidade}")
        print(f"Preço Final de Venda: R$ {p.calcular_valor_venda():.2f}")
        print(
            f"Patrimônio Investido: R$ {p.calcular_patrimonio_total():.2f}"
        )
        print(f"Precisa de Reposição? {'SIM ⚠️' if p.alerta_reposicao else 'NÃO ✅'}")
        print("-" * 50)