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


def km_atualizado(placa, km, km_atual=None):
    """`km_atual` é o km da moto antes do lançamento: se a leitura for menor, ela só entra no histórico."""
    if km_atual is not None and km < km_atual:
        return _toast(
            f"Leitura de {_km(km)} registrada no histórico da moto {placa}. O km atual continua {_km(km_atual)}."
        )
    return _toast(f"Quilometragem da moto {placa} registrada: {_km(km)}.")


# ----------------------------------------------------------------- clientes --


def cliente_salvo(nome, novo):
    return _toast(f"Cliente {nome} cadastrado." if novo else f"Dados de {nome} atualizados.")


def acesso_portal_removido(nome):
    return _toast(f"Acesso de {nome} ao portal removido.")


# ---------------------------------------------------------------- contratos --


def contrato_criado(nome, placa, enviadas=0, falhas_fotos=0):
    """`enviadas` fotos da entrega foram anexadas; sem fotos, o aviso diz onde adicioná-las depois."""
    texto = f"Contrato de {nome} com a moto {placa} criado."
    if falhas_fotos:
        return _alerta(texto + _aviso_fotos(falhas_fotos), atencao=True)
    if enviadas:
        return _alerta(texto + (" Foto da vistoria de entrega anexada." if enviadas == 1 else f" {enviadas} fotos da vistoria de entrega anexadas."))
    return _alerta(texto + " Para anexar fotos da vistoria de entrega, abra Vistorias e use “Adicionar fotos”.")


def contrato_encerrado(nome, placa, devolucao=None, desconto=None, excedente=None):
    """Confirma o encerramento. Com caução recebida (`devolucao` informada), diz quanto devolver
    e quanto foi descontado de danos; danos acima da caução geram cobrança e pedem atenção."""
    texto = f"Contrato de {nome} encerrado. A moto {placa} está disponível."
    if devolucao is not None:
        texto += f" Devolver {moeda(devolucao)} de caução ao cliente."
    if Decimal(str(desconto or 0)) > 0:
        texto += f" Danos descontados da caução: {moeda(desconto)}."
    if Decimal(str(excedente or 0)) > 0:
        return _alerta(
            texto + f" Os danos passaram da caução: foi gerada uma cobrança de {moeda(excedente)} contra o cliente."
        )
    return _toast(texto)


# --------------------------------------------------------------- cobranças --


def pagamento_registrado(principal, extras, quitada):
    """`Pagamento de R$ 450,00 registrado.` + encargos (se houver) + situação da cobrança."""
    texto = f"Pagamento de {moeda(principal)} registrado."
    if Decimal(str(extras or 0)) > 0:
        texto += f" Multa e adicional de {moeda(extras)} incluídos."
    texto += " Cobrança quitada." if quitada else " A cobrança continua em aberto com o saldo restante."
    return _toast(texto)


def cobranca_cancelada(tipo, cliente, valor):
    """`Cobrança de Locação de Ana Souza (R$ 450,00) cancelada.` — sai da dívida e das listas; o motivo fica guardado."""
    return _toast(f"Cobrança de {tipo} de {cliente} ({moeda(valor)}) cancelada. O motivo ficou registrado.")


def parcela_divida_paga(valor, numero, quitada):
    """`Pagamento de R$ 1.000,00 registrado na parcela 7.` + situação da parcela."""
    parte = f" na parcela {numero}" if numero else ""
    texto = f"Pagamento de {moeda(valor)} registrado{parte}."
    texto += " Parcela quitada." if quitada else " A parcela continua em aberto com o saldo restante."
    return _toast(texto)


def compra_parcelada_cadastrada(credor, numero_parcelas, valor_total):
    """`Compra parcelada de Celta cadastrada: 9 parcelas, total de R$ 14.000,00.`"""
    plural = "parcela" if int(numero_parcelas) == 1 else "parcelas"
    return _toast(f"Compra parcelada de {credor} cadastrada: {numero_parcelas} {plural}, total de {moeda(valor_total)}.")


def divida_cadastrada(credor, tipo_rotulo):
    return _toast(f"Dívida cadastrada: {tipo_rotulo} com {credor}.")


def pagamento_divida_registrado(valor, quitada):
    """`Pagamento de R$ 300,00 registrado.` + situação da dívida."""
    texto = f"Pagamento de {moeda(valor)} registrado."
    texto += " Dívida quitada." if quitada else " A dívida continua em aberto com o saldo restante."
    return _toast(texto)


def divida_atualizada(credor):
    return _toast(f"Dívida de {credor} atualizada.")


def saldo_confirmado(valor):
    return _toast(f"Saldo confirmado em {moeda(valor)}. Ele passa a valer no lugar do saldo calculado.")


def confirmacao_removida():
    return _toast("Confirmação removida. Volta a valer o saldo calculado.")


def divida_apagada(credor):
    return _toast(f"Dívida de {credor} apagada, com as parcelas e os pagamentos.")


def parcela_atualizada(numero):
    return _toast(f"Parcela {numero} atualizada." if numero else "Parcela atualizada.")


def pagamento_atualizado(valor):
    return _toast(f"Pagamento corrigido: {moeda(valor)}.")


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
    return f" Atenção: {quantas}. Abra Vistorias e use “Adicionar fotos” para tentar de novo."


# ------------------------------------------------------------ configurações --


def arquivos_orfaos_apagados(apagados, tamanho, falhas):
    """`3 arquivo(s) órfão(s) apagado(s) (5,0 KB).` Com falha em algum lote, vira alerta: o resto continua no Storage e pode ser tentado de novo."""
    texto = f"{apagados} arquivo(s) órfão(s) apagado(s) ({tamanho})."
    if falhas:
        return _alerta(f"{texto} {falhas} arquivo(s) não puderam ser apagados agora; procure de novo para tentar outra vez.", atencao=True)
    return _toast(texto)


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


# ----------------------------------------------------------------- WhatsApp --


def whatsapp_cancelada():
    return _toast("Mensagem cancelada: ela não será enviada.")


def whatsapp_reenviada():
    return _toast("Mensagem devolvida à fila: ela sai na próxima rodada, dentro do horário de envio.")


def whatsapp_cliente_bloqueado(nome):
    return _alerta(f"{nome} não receberá mais mensagens automáticas de WhatsApp. Os avisos dele passam a depender de você.", atencao=True)


def whatsapp_cliente_liberado(nome):
    return _toast(f"{nome} voltou a receber mensagens automáticas de WhatsApp.")


def whatsapp_controles_salvos(ativo, modo_teste):
    if not ativo:
        return _toast("Envio automático de WhatsApp desligado.")
    if modo_teste:
        return _alerta("Envio ligado em modo teste: as mensagens vão só para o número de teste, não para os clientes.")
    return _alerta("Envio ligado: a partir da próxima rodada as mensagens vão para os clientes.", atencao=True)


# ------------------------------------------------- comprovante de documento (portal) --


def comprovante_enviado(documento):
    return _toast(f"Comprovante de {documento} enviado. O proprietário vai conferir e dar baixa no documento.")


def comprovante_recusado(documento):
    return _toast(f"Comprovante de {documento} recusado. O locatário vê o motivo no portal e pode enviar outro.")
