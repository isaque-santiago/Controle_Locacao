"""Textos das mensagens de WhatsApp e o agrupamento por cliente (seção 20 do plano). Funções puras.

Todo o texto fica neste módulo (fixo no código, por decisão do dono; editável em Configurações só no futuro).
Os assuntos de um cliente saem juntos, em UMA mensagem.

**Cobranças e recibos** (o que vai ao grupo do locatário) têm tom leve, de conversa (decisão do dono, 26/11/2026):
recibos primeiro, depois a cobrança — com os valores um por linha quando é uma só, ou uma linha por cobrança e o total
quando são várias — e, no fim, o que fazer (mandar o comprovante no grupo). Todas entram, sem teto, para o total bater
com as linhas. Se a mesma cobrança está atrasada e virou inadimplência, ela aparece uma vez só (os dois assuntos são
marcados como enviados). A inadimplência é mais séria, sem ameaça.

**Os outros avisos** (documentos, óleo, CNH, portal; fora do envio por enquanto) seguem em blocos com título, os mais
urgentes primeiro; passando de `maximo_assuntos`, o resto sai no dia seguinte e não é marcado como enviado.

Nenhum texto leva senha. Dinheiro em `R$ 1.234,56`, datas em `dd/mm/aaaa`, placa `ABC-1D23`.
"""

from dataclasses import dataclass
from datetime import datetime

from src.domain.avisos_whatsapp import Aviso
from src.domain.formatadores import formatar_data, formatar_moeda, formatar_placa
from src.domain.grupo_whatsapp import TIPOS_NO_GRUPO, normalizar_grupo

# Mais urgente primeiro: cobranças, depois documentos, manutenção, CNH e portal.
ORDEM = (
    "inadimplencia", "atraso", "lembrete_vencimento", "lembrete_vespera", "recibo_pagamento",
    "documento_vencido", "documento_proximo", "oleo_vencida", "oleo_proxima",
    "cnh_vencida", "cnh_proxima", "portal_acesso", "portal_senha_alterada",
)
_POSICAO = {tipo: i for i, tipo in enumerate(ORDEM)}

_DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
# Nome de cada tipo de cobrança (todos femininos: "a parcela", "a caução", "a multa de trânsito").
_COBRANCA = {
    "locacao": "parcela", "caucao": "caução", "dano": "cobrança de danos",
    "multa_transito": "multa de trânsito", "multa_manutencao": "multa de manutenção", "outros": "cobrança",
}
_COMPROVANTE = "Depois de pagar, é só mandar o comprovante aqui no grupo."
_JA_PAGOU = "Se já pagou, pode desconsiderar. 🙏"
_DOCUMENTO = {
    "ipva": ("IPVA", "Providencie o pagamento da guia"),
    "licenciamento": ("Licenciamento", "Providencie o pagamento da guia"),
    "seguro": ("Seguro", "Providencie a renovação do seguro"),
    "vistoria_detran": ("Vistoria do Detran", "Agende e faça a vistoria"),
}


@dataclass(frozen=True)
class OpcoesTexto:
    empresa: str | None = None        # "LA Locadora": aparece na saudação
    contato: str | None = None        # como falar com o dono: "o Alisson, no (11) 99999-0000"
    pix: str | None = None            # chave Pix estática (decisão do dono adiada: sem ela, a linha não aparece)
    link_portal: str | None = None
    comprovante_no_portal: bool = False  # só vira True quando o envio de comprovante pelo portal existir (Etapa 6)
    maximo_assuntos: int = 5


# ------------------------------------------------------------------- blocos --


def _contato(op: OpcoesTexto) -> str:
    return op.contato or "a empresa"


def _moto(placa) -> str:
    return f" do veículo {formatar_placa(placa)}" if placa else ""


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


# ---------------------------------------------------- cobranças e recibos --


def _tipo(d) -> str:
    return _COBRANCA.get(d.get("tipo_cobranca"), "cobrança")


def _dia_do_vencimento(vencimento, dias_ate: int) -> str:
    """"hoje", "amanhã" ou o dia da semana (o lembrete de um vencimento de segunda sai no sábado)."""
    if dias_ate == 0:
        return "hoje"
    if dias_ate == 1:
        return "amanhã"
    return _DIAS_SEMANA[vencimento.weekday()]


def _linha_pix(op: OpcoesTexto) -> list[str]:
    return [f"🔑 Pix: {op.pix}"] if op.pix else []


def _valores(d, op: OpcoesTexto) -> str:
    """Valores de uma cobrança só, um por linha; com encargos, mostra a conta e o total."""
    encargos = d.get("encargos") or 0
    if encargos > 0:
        rotulo = "Parcela" if _tipo(d) == "parcela" else "Valor"
        linhas = [f"💰 {rotulo}: {formatar_moeda(d['saldo'])}",
                  f"➕ Multa e adicional: {formatar_moeda(encargos)}",
                  f"✅ *Total hoje: {formatar_moeda(d['total'])}*"]
    else:
        linhas = [f"💰 *Valor: {formatar_moeda(d['saldo'])}*"]
    return "\n".join(linhas + _linha_pix(op))


def _fechamento_inadimplencia() -> str:
    return ("Precisamos regularizar isso *hoje*. Responda aqui no grupo pra gente resolver.\n"
            "Se já pagou, envie o comprovante aqui.")


def _uma_cobranca(a: Aviso, op: OpcoesTexto) -> list[str]:
    d = a.dados
    nome, veiculo = _tipo(d), _moto(d.get("placa"))
    if a.tipo in ("lembrete_vespera", "lembrete_vencimento"):
        dia = _dia_do_vencimento(d["vencimento"], d.get("dias_ate_vencer", 0))
        data = formatar_data(d["vencimento"])
        if a.tipo == "lembrete_vencimento":
            return [f"Passando pra lembrar que a {nome}{veiculo} vence hoje ({data}).", _valores(d, op),
                    f"{_COMPROVANTE}\n{_JA_PAGOU}"]
        return [f"Passando pra lembrar que {dia} ({data}) vence a {nome}{veiculo}.", _valores(d, op),
                f"{_COMPROVANTE} 😊"]
    abertura = (f"a {nome}{veiculo} que venceu em {formatar_data(d['vencimento'])} está em aberto há "
                f"{_plural(d['dias_atraso'], 'dia', 'dias')}")
    if a.tipo == "inadimplencia":
        return [f"⚠️ {abertura[0].upper()}{abertura[1:]}, e o contrato passa a constar como inadimplente.",
                _valores(d, op), _fechamento_inadimplencia()]
    aumenta = "O valor aumenta a cada dia. " if d.get("encargos", 0) > 0 else ""
    return [f"{abertura[0].upper()}{abertura[1:]}.", _valores(d, op), f"{aumenta}{_COMPROVANTE}\n{_JA_PAGOU}"]


def _linha_da_cobranca(a: Aviso, com_tipo: bool, com_placa: bool) -> str:
    d = a.dados
    if a.tipo in ("atraso", "inadimplencia"):
        situacao = f"{_plural(d['dias_atraso'], 'dia', 'dias')} de atraso"
        if a.tipo == "inadimplencia":
            situacao += ", inadimplente"
    else:
        situacao = f"vence {_dia_do_vencimento(d['vencimento'], d.get('dias_ate_vencer', 0))}"
    detalhes = [f"*{formatar_data(d['vencimento'])}*"]
    if com_tipo:
        detalhes.append(_tipo(d).capitalize())
    if com_placa and d.get("placa"):
        detalhes.append(formatar_placa(d["placa"]))
    linha = f"• {' · '.join(detalhes)} ({situacao}): {formatar_moeda(d['saldo'])}"
    if (d.get("encargos") or 0) > 0:
        linha += f" + {formatar_moeda(d['encargos'])} de multa e adicional"
    return linha


def _varias_cobrancas(cobrancas: list[Aviso], op: OpcoesTexto) -> list[str]:
    """Uma linha por cobrança e o total das que aparecem. A frase não diz "você tem N em aberto": a mensagem traz só as
    cobranças com aviso devido no dia, e pode haver outra em aberto esperando o próximo aviso da escala."""
    so_parcelas = all(_tipo(a.dados) == "parcela" for a in cobrancas)
    placas = {a.dados.get("placa") for a in cobrancas}
    mesma_placa = len(placas) == 1 and None not in placas
    nome = "parcelas" if so_parcelas else "cobranças"
    veiculo = _moto(next(iter(placas))) if mesma_placa else ""
    linhas = [_linha_da_cobranca(a, not so_parcelas, not mesma_placa) for a in cobrancas]
    total = sum(a.dados["saldo"] + (a.dados.get("encargos") or 0) for a in cobrancas)
    soma = "\n".join([f"✅ *Total destas {nome}: {formatar_moeda(total)}*"] + _linha_pix(op))

    if any(a.tipo == "inadimplencia" for a in cobrancas):
        abertura = f"⚠️ Seguem {len(cobrancas)} {nome}{veiculo}, e o contrato passa a constar como inadimplente:"
        fim = _fechamento_inadimplencia()
    else:
        abertura = f"Seguem {len(cobrancas)} {nome}{veiculo}:"
        aumenta = ("O valor aumenta a cada dia de atraso. "
                   if any((a.dados.get("encargos") or 0) > 0 for a in cobrancas) else "")
        tudo_a_vencer = all(a.tipo == "lembrete_vespera" for a in cobrancas)
        fim = f"{aumenta}{_COMPROVANTE}" + (" 😊" if tudo_a_vencer else f"\n{_JA_PAGOU}")
    return [abertura, "\n".join(linhas), soma, fim]


def _recibo(a: Aviso) -> str:
    d = a.dados
    referente = f" da parcela de {formatar_data(d['vencimento'])}" if d.get("vencimento") else ""
    placa = f" ({formatar_placa(d['placa'])})" if d.get("placa") else ""
    fim = (f"Ainda faltam {formatar_moeda(d['saldo_restante'])}. Obrigado! 🙏"
           if d["saldo_restante"] > 0 else "Está tudo certo. Obrigado! 🙏")
    return f"Recebemos {formatar_moeda(d['valor'])}{referente}{placa}. {fim}"


def _partes_do_grupo(nome: str, avisos: list[Aviso], op: OpcoesTexto) -> list[str]:
    inadimplentes = {a.referencia_id for a in avisos if a.tipo == "inadimplencia"}
    recibos = [a for a in avisos if a.tipo == "recibo_pagamento"]
    cobrancas = sorted(
        (a for a in avisos if a.tipo != "recibo_pagamento"
         and not (a.tipo == "atraso" and a.referencia_id in inadimplentes)),  # a mesma dívida aparece uma vez só
        key=lambda a: (a.dados["vencimento"], a.referencia_id))
    saudacao = f"Olá, {_primeiro_nome(nome)}." if inadimplentes else f"Oi, {_primeiro_nome(nome)}! 👋"
    if op.empresa:
        saudacao += f" Aqui é da {op.empresa}."
    partes = [saudacao] + [_recibo(a) for a in recibos]
    if len(cobrancas) == 1:
        partes += _uma_cobranca(cobrancas[0], op)
    elif cobrancas:
        partes += _varias_cobrancas(cobrancas, op)
    return partes


# ----------------------------------------------------------- outros avisos --


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
        return "Troca de óleo próxima", [f"O veículo {formatar_placa(d['placa'])} está perto da troca de óleo (faltam {_faltam(d)}).", registro]
    passou = _passou(d)
    atraso = f" (passou {passou})" if passou else ""
    return "Troca de óleo atrasada", [
        f"A troca de óleo do veículo {formatar_placa(d['placa'])} passou do prazo{atraso}. Trocas fora do intervalo podem gerar multa.",
        registro,
    ]


def _bloco_cnh(a: Aviso, op: OpcoesTexto):
    d = a.dados
    if a.tipo == "cnh_proxima":
        return "CNH perto de vencer", [
            f"Sua CNH vence em {formatar_data(d['validade'])} ({_plural(d['dias'], 'dia', 'dias')}).",
            f"Depois de renovar, envie a nova CNH para {_contato(op)}, para atualizar o cadastro.",
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
            f"{onde} com seu e-mail de acesso e a senha informada pela empresa.",
        ]
    return "Senha do portal alterada", [
        "A senha do seu acesso ao portal foi alterada.",
        f"Se não foi você, avise {_contato(op)} agora.",
    ]


_CONSTRUTORES = {
    "documento_proximo": _bloco_documento, "documento_vencido": _bloco_documento,
    "oleo_proxima": _bloco_oleo, "oleo_vencida": _bloco_oleo,
    "cnh_proxima": _bloco_cnh, "cnh_vencida": _bloco_cnh,
    "portal_acesso": _bloco_portal, "portal_senha_alterada": _bloco_portal,
}


def texto_bloco(aviso: Aviso, opcoes: OpcoesTexto | None = None) -> tuple[str, list[str]]:
    """(título, linhas) de um aviso que não é cobrança nem recibo."""
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
    do_grupo = [a for a in ordenados if a.tipo in TIPOS_NO_GRUPO]
    outros = [a for a in ordenados if a.tipo not in TIPOS_NO_GRUPO]
    vagas = max(op.maximo_assuntos - len(do_grupo), 0)
    blocos, sobram = outros[:vagas], outros[vagas:]

    if do_grupo:
        partes = _partes_do_grupo(nome, do_grupo, op)
    else:
        saudacao = f"Olá, {_primeiro_nome(nome)}!" + (f" Aqui é da {op.empresa}." if op.empresa else "")
        abertura = "Segue um aviso:" if len(blocos) == 1 else f"Seguem {len(blocos)} avisos:"
        partes = [f"{saudacao} {abertura}"]
    for i, aviso in enumerate(blocos, start=1):
        titulo, linhas = texto_bloco(aviso, op)
        cabecalho = f"*{titulo}*" if len(blocos) == 1 else f"*{i}. {titulo}*"
        partes.append("\n".join([cabecalho] + linhas))
    if sobram:
        partes.append(f"Há mais {_plural(len(sobram), 'assunto', 'assuntos')} pendente(s). Fale com {_contato(op)} para ver tudo.")
    elif not do_grupo:
        partes.append(f"Dúvidas? Fale com {_contato(op)}.")
    return "\n\n".join(partes), do_grupo + blocos, sobram


def montar_payload(clientes: dict, avisos, momento: datetime, opcoes: OpcoesTexto | None = None) -> list[dict]:
    """Mensagens no formato de `rpc_whatsapp_enfileirar`, uma por cliente.

    `clientes`: `{cliente_id: {"nome", "grupo"}}`. `momento`: quando a mensagem pode sair (com fuso; já dentro de um
    disparo). O destino é o grupo de WhatsApp do cliente (vai no campo `numero`, que guarda número ou grupo). Cliente
    sem grupo válido vai com `numero: None` e a RPC grava como `ignorada`.
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
            "numero": normalizar_grupo(cliente.get("grupo")),
            "texto": texto,
            "enviar_apos": momento.isoformat(),
            "itens": [
                {"tipo": a.tipo, "referencia_id": a.referencia_id, "data_referencia": a.data_referencia.isoformat()}
                for a in entram
            ],
        })
    return mensagens
