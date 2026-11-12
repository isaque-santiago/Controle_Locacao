"""«Esqueci minha senha» do portal do locatário (pendência da Fase 7). Funções puras.

O e-mail do portal é fictício, então não há link de redefinição: o locatário informa o CPF na tela de login, isso registra um pedido
e o dono gera a senha nova e a entrega pessoalmente. A resposta ao locatário é sempre a mesma, para não revelar quais CPFs são clientes."""

from src.domain.formulario_moto import ErroDeCampos, _texto
from src.domain.painel import TOM_ATENCAO, ItemAlerta
from src.domain.validadores import validar_cpf

MENSAGEM_PEDIDO = (
    "Pedido registrado. Se o CPF tiver acesso ao portal, o proprietário foi avisado e entrega a senha nova pessoalmente."
)


def ler_cpf(entrada: dict) -> str:
    """CPF do pedido, só com dígitos. Levanta `ErroDeCampos` se estiver vazio ou for inválido (nada de consultar o banco antes)."""
    digitos = "".join(c for c in _texto(entrada, "cpf") if c.isdigit())
    if not digitos:
        raise ErroDeCampos({"cpf": "CPF: informe o CPF do seu acesso."})
    if not validar_cpf(digitos):
        raise ErroDeCampos({"cpf": "CPF: informe um CPF válido."})
    return digitos


def alertas_de_pedidos(pedidos: list[dict]) -> list[ItemAlerta]:
    """Item do Dashboard: locatários que pediram senha nova e esperam o dono (leva para Clientes)."""
    if not pedidos:
        return []
    primeiro = pedidos[0]
    resto = f" e mais {len(pedidos) - 1}" if len(pedidos) > 1 else ""
    descricao = f"{primeiro.get('cliente') or 'Locatário'}{resto}"
    return [ItemAlerta(len(pedidos), "Nova senha do portal pedida", descricao, TOM_ATENCAO, "clientes")]
