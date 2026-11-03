"""Leitura e validação do formulário de Configurações (parâmetros do sistema).

Funções puras: recebem o que o navegador enviou (texto) e devolvem os dados prontos para o serviço,
ou levantam `ErroDeCampos` com uma mensagem por campo, para a tela mostrar o erro ao lado do campo."""

from src.domain.configuracoes import CAMPOS_INTEIROS, CAMPOS_MONETARIOS, LIMITE_INTEIRO
from src.domain.entradas import decimal_campo, inteiro_campo, texto_moeda
from src.domain.formulario_moto import ErroDeCampos, _coletar, _texto


def valores_iniciais(config: dict) -> dict:
    """Texto dos campos com o que está salvo (a multa de troca de óleo pode estar vazia em bancos antigos)."""
    return {
        **{campo: texto_moeda(config.get(campo) or 0) for campo in CAMPOS_MONETARIOS},
        **{campo: str(config.get(campo) if config.get(campo) is not None else 0) for campo in CAMPOS_INTEIROS},
    }


def texto_da_entrada(entrada: dict) -> dict:
    return {campo: _texto(entrada, campo) for campo in (*CAMPOS_MONETARIOS, *CAMPOS_INTEIROS)}


def ler_configuracao(entrada: dict) -> dict:
    """Parâmetros prontos para `configuracoes.atualizar`: valores em reais como Decimal não negativo com duas casas
    e quantidades como inteiros de 0 a 100.000."""
    erros: dict[str, str] = {}
    dados = {}
    for campo, rotulo in CAMPOS_MONETARIOS.items():
        dados[campo] = _coletar(erros, campo, decimal_campo, entrada.get(campo), rotulo)
    for campo, rotulo in CAMPOS_INTEIROS.items():
        dados[campo] = _coletar(erros, campo, inteiro_campo, _texto(entrada, campo), rotulo, 0, LIMITE_INTEIRO)
    if erros:
        raise ErroDeCampos(erros)
    return dados
