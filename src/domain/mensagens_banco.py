"""Mensagens de regra de negócio que vêm do banco (`raise exception` das RPCs) com "moto" trocado por "veículo".

O sistema trata de veículos em geral, não só de motos (decisão do dono em 16/11/2026). Reescrever as RPCs exigiria uma
migration com 18 funções; aqui o texto é ajustado na hora de mostrar. Função pura: o que não é conhecido volta igual."""

import re

_TROCAS = (
    (r"^Moto (.+) não está disponível \(status atual: (.+)\)\.$", r"Veículo \1 não está disponível (status atual: \2)."),
    (r"^Um contrato aceita até (\d+) motos\.$", r"Um contrato aceita até \1 veículos."),
    (r"^Moto não encontrada\.$", "Veículo não encontrado."),
    (r"^Moto vinculada não encontrada\.$", "Veículo vinculado não encontrado."),
    (r"^Moto da vistoria não encontrada\.$", "Veículo da vistoria não encontrado."),
    (r"^Contrato e moto incompatíveis\.$", "Contrato e veículo incompatíveis."),
    (r"^Reative a moto antes de registrar manutenção\.$", "Reative o veículo antes de registrar manutenção."),
    (r"^Encerre os contratos e manutenções antes de inativar a moto\.$", "Encerre os contratos e manutenções antes de inativar o veículo."),
    (r"^Não é possível cobrar do cliente: a moto não tem contrato ativo\.$", "Não é possível cobrar do cliente: o veículo não tem contrato ativo."),
    (r"^A quilometragem da vistoria não pode ser menor que a atual da moto\.$", "A quilometragem da vistoria não pode ser menor que a atual do veículo."),
    (r"^O plano de troca de óleo desta moto não está configurado\. Avise o proprietário\.$", "O plano de troca de óleo deste veículo não está configurado. Avise o proprietário."),
    (r"^A moto principal não pode estar na lista de motos vinculadas\.$", "O veículo principal não pode estar na lista de veículos vinculados."),
    (r"^A moto principal do contrato não pode ser listada como vinculada\.$", "O veículo principal do contrato não pode ser listado como vinculado."),
    (r"^A moto já está vinculada a outro contrato ativo\.$", "O veículo já está vinculado a outro contrato ativo."),
    (r"^A moto já está em outro contrato ativo\.$", "O veículo já está em outro contrato ativo."),
    (r"^A moto da vistoria não é uma moto vinculada do contrato\.$", "O veículo da vistoria não é um veículo vinculado do contrato."),
    (r"^A moto da vistoria não pertence ao contrato\.$", "O veículo da vistoria não pertence ao contrato."),
    (r"^A mesma moto foi informada mais de uma vez\.$", "O mesmo veículo foi informado mais de uma vez."),
)
_REGRAS = tuple((re.compile(padrao), troca) for padrao, troca in _TROCAS)


def para_o_usuario(mensagem: str) -> str:
    """Texto da regra de negócio do banco, com "veículo" no lugar de "moto". Mensagens desconhecidas voltam iguais."""
    texto = str(mensagem or "")
    for regra, troca in _REGRAS:
        if regra.match(texto):
            return regra.sub(troca, texto)
    return texto
