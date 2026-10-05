"""Mensagens de confirmação que dizem o que mudou (Plano de melhorias, Etapa 7).

Funções puras: recebem os dados já formatados pela tela (placa `ABC-1D23`, nome) e dinheiro
como `Decimal`, e devolvem um `Aviso` com o texto e o tom:

- `TOAST`: confirmação simples, some sozinha;
- `ALERTA`: o que exige atenção ou um próximo passo; fica na tela até a próxima ação
  (`atencao=True` quando algo ficou incompleto, e não só há o que fazer em seguida).
"""

from collections import namedtuple
from decimal import Decimal

from src.domain.entradas import texto_moeda

TOAST = "toast"
ALERTA = "alerta"

Aviso = namedtuple("Aviso", "texto tom atencao", defaults=(False,))


def moeda(valor) -> str:
    """Dinheiro no padrão brasileiro: Decimal('450') -> 'R$ 450,00'."""
    return "R$ " + texto_moeda(valor)


def _km(valor) -> str:
    return f"{int(valor):,} km".replace(",", ".")


def _toast(texto):
    return Aviso(texto, TOAST)


def _alerta(texto, atencao=False):
    return Aviso(texto, ALERTA, atencao)


# -------------------------------------------------------------------- motos --


def moto_salva(placa, nova):
    return _toast(f"Moto {placa} cadastrada." if nova else f"Dados da moto {placa} atualizados.")


def moto_status_alterado(placa, inativada):
    return _toast(f"Moto {placa} inativada." if inativada else f"Moto {placa} reativada.")


def km_atualizado(placa, km):
    return _toast(f"Quilometragem da moto {placa} registrada: {_km(km)}.")


# ----------------------------------------------------------------- clientes --


def cliente_salvo(nome, novo):
    return _toast(f"Cliente {nome} cadastrado." if novo else f"Dados de {nome} atualizados.")


def acesso_portal_removido(nome):
    return _toast(f"Acesso de {nome} ao portal removido.")


# ---------------------------------------------------------------- contratos --


def contrato_criado(nome, placa):
    return _alerta(
        f"Contrato de {nome} com a moto {placa} criado. Anexe as fotos da vistoria de entrega na página Vistorias."
    )


def contrato_encerrado(nome, placa):
    return _toast(f"Contrato de {nome} encerrado. A moto {placa} está disponível.")


# --------------------------------------------------------------- cobranças --


def pagamento_registrado(principal, extras, quitada):
    """`Pagamento de R$ 450,00 registrado.` + encargos (se houver) + situação da cobrança."""
    texto = f"Pagamento de {moeda(principal)} registrado."
    if Decimal(str(extras or 0)) > 0:
        texto += f" Multa e adicional de {moeda(extras)} incluídos."
    texto += " Cobrança quitada." if quitada else " A cobrança continua em aberto com o saldo restante."
    return _toast(texto)


# ---------------------------------------------------------------- documentos --


def documento_salvo(descricao, novo):
    return _toast(f"Documento {descricao} cadastrado." if novo else f"Documento {descricao} atualizado.")


def documento_regularizado(descricao, cadastrar_proximo=False):
    texto = f"Documento {descricao} marcado como regularizado."
    if cadastrar_proximo:
        return _alerta(texto + " O cadastro do próximo já está aberto para você preencher o vencimento.")
    return _toast(texto)


# --------------------------------------------------------------- manutenção --


def manutencao_registrada(placa, concluida, custo_total=None):
    situacao = "concluída" if concluida else "aberta; a moto fica em manutenção"
    texto = f"Manutenção da moto {placa} registrada como {situacao}."
    if custo_total is not None and Decimal(str(custo_total)) > 0:
        texto += f" Custo de {moeda(custo_total)}."
    return _toast(texto)


def manutencao_finalizada(placa, concluida):
    return _toast(f"Manutenção da moto {placa} {'concluída' if concluida else 'cancelada'}.")


def item_catalogo_salvo(nome, novo):
    return _toast(f"Item {nome} adicionado ao catálogo." if novo else f"Item {nome} atualizado.")


# ---------------------------------------------------------------- vistorias --


def vistoria_registrada(tipo, placa, falhas_fotos=0):
    texto = f"Vistoria de {tipo} da moto {placa} registrada."
    if falhas_fotos:
        return _alerta(texto + _aviso_fotos(falhas_fotos), atencao=True)
    return _toast(texto)


def fotos_anexadas(quantidade, falhas_fotos=0):
    texto = "1 foto anexada." if quantidade == 1 else f"{quantidade} fotos anexadas."
    if falhas_fotos:
        return _alerta(texto + _aviso_fotos(falhas_fotos), atencao=True)
    return _toast(texto)


def _aviso_fotos(falhas):
    quantas = "1 foto não foi enviada" if falhas == 1 else f"{falhas} fotos não foram enviadas"
    return f" Atenção: {quantas}. Use “Adicionar fotos” para tentar de novo."


# ------------------------------------------------------------ configurações --


def configuracoes_salvas(alterados):
    """`alterados`: nomes dos campos que mudaram (podem ser vazios)."""
    if not alterados:
        return _toast("Configurações salvas. Nenhum valor foi alterado.")
    return _toast("Configurações salvas: " + ", ".join(alterados) + ".")


# ------------------------------------------------------------------- portal --


def troca_oleo_registrada(excedeu=False, multa=None):
    if not excedeu:
        return _toast("Troca de óleo registrada. Obrigado!")
    complemento = (
        f" Foi gerada uma cobrança de multa de {moeda(multa)}." if multa else " O proprietário foi avisado do atraso."
    )
    return _alerta("Troca registrada, mas passou do intervalo previsto." + complemento, atencao=True)


def senha_alterada():
    return _toast("Senha alterada. Use a nova senha no próximo acesso.")
