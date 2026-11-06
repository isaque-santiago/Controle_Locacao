"""Textos das mensagens de WhatsApp e o agrupamento por cliente (seção 20 do plano). Funções puras.

Todo o texto fica neste módulo (fixo no código, por decisão do dono; editável em Configurações só no futuro).
Quem recebe é sempre o locatário. Um cliente recebe UMA mensagem por dia de envio, com um bloco por assunto,
os mais urgentes primeiro e uma linha de ação em cada bloco. Passando de `maximo_assuntos`, os mais urgentes vão
na mensagem e o resto sai no dia seguinte (os assuntos que não entram não são marcados como enviados).

Nenhum texto leva senha. Dinheiro em `R$ 1.234,56`, datas em `dd/mm/aaaa`, placa `ABC-1D23`.
"""

from dataclasses import dataclass
from datetime import datetime

from src.domain.avisos_whatsapp import Aviso
from src.domain.formatadores import formatar_data, formatar_moeda, formatar_placa
from src.domain.numero_whatsapp import normalizar_numero

# Mais urgente primeiro: cobranças, depois documentos, manutenção, CNH e portal.
ORDEM = (
    "inadimplencia", "atraso", "lembrete_vencimento", "lembrete_vespera", "recibo_pagamento",
    "documento_vencido", "documento_proximo", "oleo_vencida", "oleo_proxima",
    "cnh_vencida", "cnh_proxima", "portal_acesso", "portal_senha_alterada",
)
_POSICAO = {tipo: i for i, tipo in enumerate(ORDEM)}

_DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
_COBRANCA = {
    "locacao": "A parcela da locação", "caucao": "A caução", "dano": "A cobrança de danos",
    "multa_transito": "A multa de trânsito", "multa_manutencao": "A multa de manutenção", "outros": "A cobrança",
}
_DOCUMENTO = {
    "ipva": ("IPVA", "Providencie o pagamento da guia"),
    "licenciamento": ("Licenciamento", "Providencie o pagamento da guia"),
    "seguro": ("Seguro", "Providencie a renovação do seguro"),
    "vistoria_detran": ("Vistoria do Detran", "Agende e faça a vistoria"),
}


@dataclass(frozen=True)
class OpcoesTexto:
    empresa: str | None = None        # "LA Motos": aparece na saudação
    contato: str | None = None        # como falar com o dono: "o Alisson, no (11) 99999-0000"
    pix: str | None = None            # chave Pix estática (decisão do dono adiada: sem ela, a linha não aparece)
    link_portal: str | None = None
    comprovante_no_portal: bool = False  # só vira True quando o envio de comprovante pelo portal existir (Etapa 6)
    maximo_assuntos: int = 5


# ------------------------------------------------------------------- blocos --


def _contato(op: OpcoesTexto) -> str:
    return op.contato or "a empresa"


def _moto(placa) -> str:
    return f" da moto {formatar_placa(placa)}" if placa else ""


def _quando(vencimento, dias_ate) -> str:
    if dias_ate == 0:
        return "hoje"
    if dias_ate == 1:
        return f"amanhã ({formatar_data(vencimento)})"
    return f"{_DIAS_SEMANA[vencimento.weekday()]} ({formatar_data(vencimento)})"


def _linha_pix(op: OpcoesTexto) -> list[str]:
    return [f"Pix para pagar: {op.pix}"] if op.pix else []


def _cobranca_nome(d) -> str:
    return _COBRANCA.get(d.get("tipo_cobranca"), "A cobrança")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _bloco_lembrete(a: Aviso, op: OpcoesTexto):
    d = a.dados
    ate = d.get("dias_ate_vencer", 0)
    titulo = "Parcela vence hoje" if ate == 0 else "Parcela perto de vencer"
    linhas = [f"{_cobranca_nome(d)}{_moto(d['placa'])} vence {_quando(d['vencimento'], ate)}. Valor: {formatar_moeda(d['saldo'])}."]
    return titulo, linhas + _linha_pix(op)


def _bloco_atraso(a: Aviso, op: OpcoesTexto):
    d = a.dados
    linhas = [
        f"{_cobranca_nome(d)}{_moto(d['placa'])}, que venceu em {formatar_data(d['vencimento'])}, está atrasada "
        f"há {_plural(d['dias_atraso'], 'dia', 'dias')}.",
        f"Valor: {formatar_moeda(d['saldo'])}",
    ]
    if d["encargos"] > 0:
        linhas += [f"Multa e adicional por atraso: {formatar_moeda(d['encargos'])}",
                   f"*Total hoje: {formatar_moeda(d['total'])}* (o valor aumenta a cada dia de atraso)"]
    return "Pagamento em atraso", linhas + _linha_pix(op)


def _bloco_inadimplencia(a: Aviso, op: OpcoesTexto):
    d = a.dados
    return "Aviso importante: atraso prolongado", [
        f"{_cobranca_nome(d)}{_moto(d['placa'])} de {formatar_data(d['vencimento'])} está atrasada há "
        f"{_plural(d['dias_atraso'], 'dia', 'dias')} e seu contrato passa a constar como inadimplente.",
        f"Total hoje: {formatar_moeda(d['total'])}",
        f"Fale com {_contato(op)} ainda hoje para regularizar.",
    ] + _linha_pix(op)


def _bloco_recibo(a: Aviso, op: OpcoesTexto):
    d = a.dados
    referente = f" referente à parcela de {formatar_data(d['vencimento'])}" if d.get("vencimento") else ""
    fim = (f"Ainda falta {formatar_moeda(d['saldo_restante'])} desta parcela."
           if d["saldo_restante"] > 0 else "Está tudo certo com essa parcela. Obrigado!")
    return "Pagamento recebido", [f"Recebemos {formatar_moeda(d['valor'])}{referente}{_moto(d['placa'])}.", fim]


def _como_enviar_comprovante(op: OpcoesTexto) -> str:
    if op.comprovante_no_portal and op.link_portal:
        return f"pelo portal ({op.link_portal}) ou para {_contato(op)}"
    return f"para {_contato(op)}"


def _bloco_documento(a: Aviso, op: OpcoesTexto):
    d = a.dados
    nome, instrucao = _DOCUMENTO.get(d["tipo_documento"], (d.get("descricao") or "Documento", "Providencie a regularização"))
    if d["tipo_documento"] == "outro" and d.get("descricao"):
        nome = d["descricao"]
    dias = d["dias"]
    if a.tipo == "documento_proximo":
        titulo = "Documento perto de vencer"
        situacao = f"vence em {formatar_data(d['vencimento'])} ({_plural(dias, 'dia', 'dias')})"
    else:
        titulo = "Documento vencido"
        situacao = f"venceu em {formatar_data(d['vencimento'])} (há {_plural(-dias, 'dia', 'dias')})"
    return titulo, [
        f"{nome}{_moto(d['placa'])} {situacao}.",
        f"{instrucao}. Se o custo for do proprietário, combine com {_contato(op)}.",
        f"Depois de regularizar, envie o comprovante {_como_enviar_comprovante(op)}.",
    ]


def _faltam(d) -> str:
    partes = []
    if d.get("km_restantes") is not None:
        partes.append(f"{d['km_restantes']} km")
    if d.get("dias_restantes") is not None:
        partes.append(_plural(d["dias_restantes"], "dia", "dias"))
    return " ou ".join(partes)


def _passou(d) -> str:
    partes = []
    if d.get("km_restantes") is not None and d["km_restantes"] <= 0:
        partes.append(f"{-d['km_restantes']} km")
    if d.get("dias_restantes") is not None and d["dias_restantes"] <= 0:
        partes.append(_plural(-d["dias_restantes"], "dia", "dias"))
    return " e ".join(partes)


def _bloco_oleo(a: Aviso, op: OpcoesTexto):
    d = a.dados
    registro = ("Faça a troca e registre pelo portal, com a foto do painel e a nota fiscal"
                + (f": {op.link_portal}" if op.link_portal else "."))
    if a.tipo == "oleo_proxima":
        return "Troca de óleo próxima", [f"A moto {formatar_placa(d['placa'])} está perto da troca de óleo (faltam {_faltam(d)}).", registro]
    passou = _passou(d)
    atraso = f" (passou {passou})" if passou else ""
    return "Troca de óleo atrasada", [
        f"A troca de óleo da moto {formatar_placa(d['placa'])} passou do prazo{atraso}. Trocas fora do intervalo podem gerar multa.",
        registro,
    ]


def _bloco_cnh(a: Aviso, op: OpcoesTexto):
    d = a.dados
    if a.tipo == "cnh_proxima":
        return "CNH perto de vencer", [
            f"Sua CNH vence em {formatar_data(d['validade'])} ({_plural(d['dias'], 'dia', 'dias')}).",
            f"Depois de renovar, envie a nova CNH para {_contato(op)} atualizar o cadastro.",
        ]
    return "CNH vencida", [
        f"Sua CNH venceu em {formatar_data(d['validade'])} (há {_plural(-d['dias'], 'dia', 'dias')}). "
        "Não é permitido conduzir com a CNH vencida.",
        f"Regularize e envie a nova CNH para {_contato(op)}.",
    ]


def _bloco_portal(a: Aviso, op: OpcoesTexto):
    if a.tipo == "portal_acesso":
        onde = f"Entre em {op.link_portal}" if op.link_portal else "Entre no portal"
        return "Acesso ao portal", [
            "Seu acesso ao portal do locatário foi criado.",
            f"{onde} com seu CPF e a senha informada pela empresa.",
        ]
    return "Senha do portal alterada", [
        "A senha do seu acesso ao portal foi alterada.",
        f"Se não foi você, avise {_contato(op)} agora.",
    ]


_CONSTRUTORES = {
    "lembrete_vespera": _bloco_lembrete, "lembrete_vencimento": _bloco_lembrete,
    "atraso": _bloco_atraso, "inadimplencia": _bloco_inadimplencia, "recibo_pagamento": _bloco_recibo,
    "documento_proximo": _bloco_documento, "documento_vencido": _bloco_documento,
    "oleo_proxima": _bloco_oleo, "oleo_vencida": _bloco_oleo,
    "cnh_proxima": _bloco_cnh, "cnh_vencida": _bloco_cnh,
    "portal_acesso": _bloco_portal, "portal_senha_alterada": _bloco_portal,
}


def texto_bloco(aviso: Aviso, opcoes: OpcoesTexto | None = None) -> tuple[str, list[str]]:
    """(título, linhas) de um assunto."""
    return _CONSTRUTORES[aviso.tipo](aviso, opcoes or OpcoesTexto())


# --------------------------------------------------------------- mensagem --


def _primeiro_nome(nome: str) -> str:
    partes = (nome or "").split()
    return partes[0].capitalize() if partes else "cliente"


def montar_mensagem(nome: str, avisos, opcoes: OpcoesTexto | None = None) -> tuple[str, list[Aviso], list[Aviso]]:
    """(texto, avisos que entraram, avisos que ficaram de fora por passar do teto) de um cliente.
    Os que ficaram de fora não devem ser marcados como enviados."""
    op = opcoes or OpcoesTexto()
    if not avisos:
        raise ValueError("Não há avisos para montar a mensagem.")
    ordenados = sorted(avisos, key=lambda a: (_POSICAO[a.tipo], a.referencia_id))
    entram, sobram = ordenados[:op.maximo_assuntos], ordenados[op.maximo_assuntos:]

    saudacao = f"Olá, {_primeiro_nome(nome)}!" + (f" Aqui é da {op.empresa}." if op.empresa else "")
    n = len(entram)
    abertura = "Segue um aviso:" if n == 1 else f"Seguem {n} avisos:"
    partes = [f"{saudacao} {abertura}"]
    for i, aviso in enumerate(entram, start=1):
        titulo, linhas = texto_bloco(aviso, op)
        cabecalho = f"*{titulo}*" if n == 1 else f"*{i}. {titulo}*"
        partes.append("\n".join([cabecalho] + linhas))
    if sobram:
        partes.append(f"Há mais {_plural(len(sobram), 'assunto', 'assuntos')} pendente(s). Fale com {_contato(op)} para ver tudo.")
    else:
        partes.append(f"Dúvidas? Fale com {_contato(op)}.")
    return "\n\n".join(partes), entram, sobram


def montar_payload(clientes: dict, avisos, momento: datetime, opcoes: OpcoesTexto | None = None) -> list[dict]:
    """Mensagens no formato de `rpc_whatsapp_enfileirar`, uma por cliente.

    `clientes`: `{cliente_id: {"nome", "whatsapp"}}`. `momento`: quando a mensagem pode sair (com fuso; já dentro da
    janela). Cliente sem número válido vai com `numero: None` e a RPC grava como `ignorada`.
    """
    por_cliente: dict[str, list[Aviso]] = {}
    for aviso in avisos:
        por_cliente.setdefault(aviso.cliente_id, []).append(aviso)
    mensagens = []
    for cliente_id, lista in por_cliente.items():
        if cliente_id not in clientes:
            raise ValueError(f"Cliente {cliente_id} sem dados para a mensagem.")
        cliente = clientes[cliente_id]
        texto, entram, _ = montar_mensagem(cliente["nome"], lista, opcoes)
        mensagens.append({
            "cliente_id": cliente_id,
            "numero": normalizar_numero(cliente.get("whatsapp")),
            "texto": texto,
            "enviar_apos": momento.isoformat(),
            "itens": [
                {"tipo": a.tipo, "referencia_id": a.referencia_id, "data_referencia": a.data_referencia.isoformat()}
                for a in entram
            ],
        })
    return mensagens
