"""Menu do painel do dono: grupos da barra lateral e destinos da barra inferior (celular)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ItemNavegacao:
    chave: str
    rotulo: str
    icone: str
    caminho: str


DASHBOARD = ItemNavegacao("dashboard", "Dashboard", "painel", "/")
CONTRATOS = ItemNavegacao("contratos", "Contratos", "contrato", "/contratos")
COBRANCAS = ItemNavegacao("cobrancas", "Cobranças", "cobranca", "/cobrancas")
MOTOS = ItemNavegacao("motos", "Motos", "moto", "/motos")
CLIENTES = ItemNavegacao("clientes", "Clientes", "cliente", "/clientes")
MANUTENCAO = ItemNavegacao("manutencao", "Manutenção", "manutencao", "/manutencao")
DOCUMENTOS = ItemNavegacao("documentos", "Documentos", "documento", "/documentos")
VISTORIAS = ItemNavegacao("vistorias", "Vistorias", "vistoria", "/vistorias")
RELATORIOS = ItemNavegacao("relatorios", "Relatórios", "relatorio", "/relatorios")
CONFIGURACOES = ItemNavegacao("configuracoes", "Configurações", "config", "/configuracoes")

GRUPOS: tuple[tuple[str, tuple[ItemNavegacao, ...]], ...] = (
    ("Operação", (DASHBOARD, CONTRATOS, COBRANCAS)),
    ("Cadastros", (MOTOS, CLIENTES)),
    ("Frota", (MANUTENCAO, DOCUMENTOS, VISTORIAS)),
    ("Gestão e sistema", (RELATORIOS, CONFIGURACOES)),
)

# Destinos frequentes na barra inferior; o restante vai para a folha "Mais".
BARRA_INFERIOR: tuple[ItemNavegacao, ...] = (DASHBOARD, CONTRATOS, COBRANCAS, MOTOS)
FOLHA_MAIS: tuple[ItemNavegacao, ...] = (
    CLIENTES, MANUTENCAO, DOCUMENTOS, VISTORIAS, RELATORIOS, CONFIGURACOES,
)

TODOS: tuple[ItemNavegacao, ...] = tuple(i for _, itens in GRUPOS for i in itens)


def item_ativo(caminho_atual: str) -> ItemNavegacao | None:
    """Item do menu que corresponde ao caminho (a ficha /motos/123 ativa 'Motos')."""
    for item in TODOS:
        if item.caminho == "/":
            if caminho_atual == "/":
                return item
        elif caminho_atual == item.caminho or caminho_atual.startswith(item.caminho + "/"):
            return item
    return None


def mais_esta_ativo(caminho_atual: str) -> bool:
    """O botão 'Mais' fica ativo quando a página atual só existe na folha."""
    ativo = item_ativo(caminho_atual)
    return ativo in FOLHA_MAIS
