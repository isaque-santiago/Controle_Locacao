"""Modelo dos contratos da L.A Aluguel de Motos (funções puras): locação COM promessa de compra e venda e locação simples.

O contrato com promessa reproduz o contrato preenchido de 16/11/2026 (13 cláusulas, quadros de dados e resumo de multas). A
locação simples é o mesmo documento sem o que é da promessa (propriedade futura, quitação e transferência, desistência da
compra): 12 cláusulas e quadro de preço por período. A variante vem de `contrato["tipo_contrato"]`. O que muda de um
contrato para outro (partes, veículo, preço, parcelas, datas) vem dos dados; as multas e os prazos fixos ficam em
TERMOS, num só lugar, para facilitar a revisão. O resumo de multas é montado a partir de TERMOS, então nunca destoa
das cláusulas. Tudo em Latin-1 (fonte padrão do PDF): sem travessão, aspas curvas ou marcadores tipográficos.

Blocos (tipo): titulo | texto | legenda | quadro (linhas = (rótulo, valor), ...) | clausula | item | subitem |
resumo (linhas = (situação, valor, cláusula), ...) | fecho | assinatura (numero = papel e CPF, texto = nome).
"""

from datetime import date
from decimal import Decimal
from typing import NamedTuple

from src.domain.agenda_cobrancas import gerar_agenda
from src.domain.extenso import data_por_extenso, inteiro_por_extenso, moeda_por_extenso

class Bloco(NamedTuple):
    """tipo: ver o docstring do módulo. `linhas`: só nos quadros e no resumo."""

    tipo: str
    numero: str
    texto: str
    linhas: tuple = ()


_EM_BRANCO = "..............................."


def _limpa(valor) -> str:
    """Remove marcações de formatação do PDF (**, __, --) de textos vindos do cadastro."""
    texto = " ".join(str(valor or "").split())
    return texto.replace("**", "*").replace("__", "_").replace("--", "-")


def _v(valor, em_branco: str = _EM_BRANCO) -> str:
    texto = _limpa(valor)
    return texto if texto else em_branco


def _moeda(valor) -> str:
    texto = f"{Decimal(str(valor or 0)):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _r(valor) -> str:
    """'R$ 500,00 (quinhentos reais)'."""
    return f"{_moeda(valor)} ({moeda_por_extenso(valor)})"


def _milhar(numero) -> str:
    return f"{int(numero or 0):,}".replace(",", ".")


def _cpf(valor) -> str:
    digitos = "".join(c for c in str(valor or "") if c.isdigit())
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    return _v(valor)


def _data(valor) -> str:
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    texto = str(valor or "")
    if len(texto) >= 10 and texto[4] == "-":
        return f"{texto[8:10]}/{texto[5:7]}/{texto[:4]}"
    return texto


def _como_data(valor) -> date:
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


TERMOS = {
    "multa_terceiro_conduzir": Decimal("500.00"),
    "multa_vistoria_por_dia": Decimal("20.00"),
    "protecao_terceiros_limite": Decimal("10000.00"),
    "multa_pontos_cnh": Decimal("200.00"),
    "multa_deposito_por_dia": Decimal("30.00"),
    "multa_acionar_protecao": Decimal("200.00"),
    "multa_fora_perimetro": Decimal("150.00"),
    "perimetro_permitido": "Grande Cariri",
    "orgao_transito": "DETRAN-CE",
    "troca_oleo_km": 1000,
    "multa_troca_oleo": Decimal("10.00"),
    "apreensao_prazo_dias": 30,
    "atraso_multa": Decimal("15.00"),
    "atraso_juros_por_dia": Decimal("7.00"),
    "atraso_dias_rescisao": 15,
    "lavagem_simples": Decimal("15.00"),
    "lavagem_especial": Decimal("45.00"),
    "divida_limite_retomada": Decimal("100.00"),
    "multa_retomada_por_dia": Decimal("150.00"),
    "multa_devolucao_por_dia": Decimal("50.00"),
    "devolucao_horas": 24,
    "transferencia_prazo_dias_uteis": 10,
    "transferencia_prazo_dias": 30,
    "foro_padrao": "Crato/CE",
}

TITULO_PROMESSA = "CONTRATO DE LOCAÇÃO DE VEÍCULO COM\nPROMESSA DE COMPRA E VENDA"
TITULO_LOCACAO = "CONTRATO DE LOCAÇÃO DE VEÍCULO"
_TRACO = "________________"
_ADJETIVO = {"diario": "Diária", "semanal": "Semanal", "quinzenal": "Quinzenal", "mensal": "Mensal"}
_LOCADOR = "LOCADOR"
_LOCATARIO = "LOCATÁRIO"
_DIAS_DA_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
_PLURAL = {"diario": "diárias", "semanal": "semanais", "quinzenal": "quinzenais", "mensal": "mensais"}


def _n(numero) -> str:
    """'130 (cento e trinta)'."""
    return f"{int(numero)} ({inteiro_por_extenso(int(numero))})"


def _p(valor) -> str:
    """Valor para os quadros: o texto ou a linha em branco para preencher à mão."""
    return _v(valor, _TRACO)


def _contato(*numeros) -> str:
    vistos = []
    for numero in numeros:
        texto = _limpa(numero)
        if texto and texto not in vistos:
            vistos.append(texto)
    return " / ".join(vistos)


def _vencimento_texto(periodicidade: str, primeira: date) -> str:
    if periodicidade == "semanal":
        dia = _DIAS_DA_SEMANA[primeira.weekday()]
        return f"Toda {dia}" if dia.endswith("feira") else f"Todo {dia}"
    if periodicidade == "mensal":
        return f"Todo dia {primeira.day}"
    if periodicidade == "quinzenal":
        return f"A cada 15 dias, a partir de {_data(primeira)}"
    return "Todos os dias"


def _datas_das_parcelas(contrato: dict, inicio: date) -> tuple[date, date, int]:
    """Vencimento da 1ª e da última parcela do contrato e o número de parcelas a vencer (a partir da agenda)."""
    total = int(contrato.get("numero_parcelas") or 0)
    pagas = int(contrato.get("parcelas_pagas_inicial") or 0)
    primeira = _como_data(contrato["primeira_cobranca"]) if contrato.get("primeira_cobranca") else inicio
    if not total:
        return primeira, primeira, 0
    agenda = gerar_agenda(
        inicio, contrato["periodicidade"], Decimal("1"), date(2200, 1, 1),
        numero_parcelas=total, parcelas_pagas_inicial=pagas, primeira_cobranca=primeira,
    )
    if not agenda:
        return primeira, primeira, 0
    return agenda[0]["vencimento"], agenda[-1]["vencimento"], len(agenda)


def _partes(locador: dict, cliente: dict, promessa: bool) -> list[Bloco]:
    nome = _limpa(locador.get("nome"))
    representante = _limpa(locador.get("representante_nome"))
    papel_locador = "LOCADOR / PROMITENTE VENDEDOR" if promessa else "LOCADOR"
    if locador.get("cnpj"):
        titular = (
            f"**{papel_locador}: {_v(nome).upper()}**, pessoa jurídica inscrita no CNPJ nº "
            f"{_v(locador.get('cnpj'))}"
            + (f", inscrição estadual nº {_limpa(locador.get('inscricao_estadual'))}" if locador.get("inscricao_estadual") else "")
            + f", com sede em {_v(locador.get('endereco'))}, representada por **{_v(representante).upper()}**, "
            f"{_v(locador.get('representante_qualificacao'), '')}".rstrip(", ")
            + f", RG nº {_v(locador.get('representante_rg'))}, CPF nº {_cpf(locador.get('representante_cpf'))}"
        )
    else:
        titular = (
            f"**{papel_locador}: {_v(representante or nome).upper()}**, "
            + (f"{_limpa(locador.get('representante_qualificacao'))}, " if locador.get("representante_qualificacao") else "")
            + f"portador da cédula de identidade RG nº {_v(locador.get('representante_rg'))}, inscrito no CPF nº "
            f"{_cpf(locador.get('representante_cpf'))}, residente e domiciliado em {_v(locador.get('endereco'))}"
        )
    contato_locador = _contato(locador.get("telefones"))
    titular += (
        (f", telefone {contato_locador}" if contato_locador else "")
        + (f", e-mail {_limpa(locador.get('email'))}" if locador.get("email") else "")
        + ", proprietário do veículo descrito na Cláusula 1ª, doravante denominado LOCADOR; e, de outro lado,"
    )

    cnh = _limpa(cliente.get("cnh_numero"))
    if cnh:
        cnh += f" - Categoria {_limpa(cliente.get('cnh_categoria')) or _TRACO}"
        if cliente.get("cnh_validade"):
            cnh += f" (validade {_data(cliente['cnh_validade'])})"
    telefones = _contato(cliente.get("telefone"), cliente.get("whatsapp"))
    if _limpa(cliente.get("referencias")):
        telefones = (telefones + " " if telefones else "") + f"· Referências: {_limpa(cliente['referencias'])}"
    rg = _limpa(cliente.get("rg"))
    rg_orgao = _limpa(cliente.get("rg_orgao"))
    quadro = (
        ("Nome completo", _p(_limpa(cliente.get("nome")))),
        ("Nacionalidade", _p(cliente.get("nacionalidade"))),
        ("Naturalidade", _p(cliente.get("naturalidade"))),
        ("Estado civil", _p(cliente.get("estado_civil"))),
        ("Profissão", _p(cliente.get("profissao"))),
        ("Data de nascimento", _p(_data(cliente.get("data_nascimento")))),
        ("RG / Órgão emissor", _p(f"{rg} {rg_orgao}".strip())),
        ("CPF", _cpf(cliente.get("cpf"))),
        ("CNH", _p(cnh)),
        ("E-mail", _p(cliente.get("email"))),
        ("Telefone / WhatsApp", _p(telefones)),
        ("Endereço", _p(cliente.get("endereco"))),
        ("CEP", _p(cliente.get("cep"))),
    )
    return [
        Bloco("texto", "", "Pelo presente instrumento particular, de um lado:"),
        Bloco("texto", "", titular),
        Bloco("texto", "", "**LOCATÁRIO / PROMITENTE COMPRADOR:**" if promessa else "**LOCATÁRIO:**"),
        Bloco("quadro", "", "", quadro),
        Bloco("texto", "", "doravante denominado **LOCATÁRIO**, têm entre si como justo e contratado o que segue:"),
    ]


def _quadro_veiculo(moto: dict, km) -> Bloco:
    ano_fab, ano_mod = moto.get("ano_fabricacao"), moto.get("ano_modelo")
    ano = f"{ano_fab} / {ano_mod}" if ano_fab and ano_mod else _p(ano_fab or ano_mod)
    cor = " / ".join(x for x in (_limpa(moto.get("cor")), _limpa(moto.get("combustivel"))) if x)
    marca_modelo = " ".join(x for x in (_limpa(moto.get("marca")), _limpa(moto.get("modelo"))) if x)
    tipo = "Automóvel" if moto.get("tipo") == "carro" else "Motocicleta"
    return Bloco("quadro", "", "", (
        ("Tipo", tipo),
        ("Marca / Modelo", _p(marca_modelo)),
        ("Ano fabricação / modelo", ano),
        ("Placa", _p(_limpa(moto.get("placa")).upper())),
        ("Renavam", _p(moto.get("renavam"))),
        ("Chassi", _p(_limpa(moto.get("chassi")).upper())),
        ("Motor", _p(_limpa(moto.get("motor")).upper())),
        ("Cor / Combustível", _p(cor)),
        ("Quilometragem na entrega", f"{_milhar(km)} km" if km else f"{_TRACO} km"),
    ))


def _quadro_preco(contrato: dict, inicio: date, primeira: date, ultima: date, restantes: int) -> Bloco:
    t = TERMOS
    periodicidade = contrato.get("periodicidade")
    valor = Decimal(str(contrato["valor_periodo"]))
    total_parcelas = int(contrato.get("numero_parcelas") or 0)
    entrada = Decimal(str(contrato.get("valor_entrada") or 0))
    total = contrato.get("valor_total")
    total = Decimal(str(total)) if total is not None else entrada + valor * total_parcelas
    caucao = Decimal(str(contrato.get("caucao_valor") or 0))
    plural = _PLURAL.get(periodicidade, "")
    parcelas = f"{_n(total_parcelas)} parcelas {plural} de {_r(valor)} cada" if total_parcelas else f"Parcelas {plural} de {_r(valor)}"
    pagamento_inicial = primeira == inicio and restantes > 1
    vencimento = _vencimento_texto(periodicidade, primeira) + "."
    if pagamento_inicial:
        vencimento += f" A 1ª parcela ({_moeda(valor)}) é paga no ato da assinatura, restando {_n(restantes - 1)} parcelas de {_moeda(valor)}"
    marco = f"1ª em {_data(primeira)}"
    if pagamento_inicial:
        marco += " (paga na assinatura)"
    if total_parcelas:
        marco += f" · {restantes}ª em {_data(ultima)}"
    return Bloco("quadro", "", "", (
        ("Entrada", _r(entrada) if entrada > 0 else "Sem entrada"),
        ("Parcelas", parcelas),
        ("Vencimento das parcelas", vencimento),
        ("1ª e última parcela", marco),
        ("Valor total do contrato", _r(total)),
        ("Caução", f"{_r(caucao)}, paga na retirada do veículo; não abate parcelas e garante multas, danos e débitos"
                   if caucao > 0 else "Sem caução"),
        ("Forma de pagamento", "PIX ou outro meio combinado com o LOCADOR, sempre com envio do comprovante"),
    ))


def _quadro_preco_locacao(contrato: dict, inicio: date) -> Bloco:
    """Preço da locação simples: valor por período, vencimento e vigência (sem entrada, total nem número de parcelas)."""
    periodicidade = contrato.get("periodicidade")
    valor = Decimal(str(contrato["valor_periodo"]))
    caucao = Decimal(str(contrato.get("caucao_valor") or 0))
    primeira = _como_data(contrato["primeira_cobranca"]) if contrato.get("primeira_cobranca") else inicio
    fim = contrato.get("data_fim_prevista")
    primeiro = f"{_data(primeira)} (na assinatura)" if primeira == inicio else _data(primeira)
    return Bloco("quadro", "", "", (
        ("Periodicidade", _ADJETIVO.get(periodicidade, _TRACO)),
        ("Valor de cada parcela", _r(valor)),
        ("Vencimento das parcelas", _vencimento_texto(periodicidade, primeira) + ", sempre de forma antecipada ao período"),
        ("Primeiro pagamento", primeiro),
        ("Vigência", f"De {_data(inicio)} até {_data(fim)}" if fim else f"A partir de {_data(inicio)}, por prazo indeterminado"),
        ("Caução", f"{_r(caucao)}, paga na retirada do veículo; não abate parcelas e garante multas, danos e débitos"
                   if caucao > 0 else "Sem caução"),
        ("Forma de pagamento", "PIX ou outro meio combinado com o LOCADOR, sempre com envio do comprovante"),
    ))


def _resumo_de_multas() -> Bloco:
    t = TERMOS
    return Bloco("resumo", "", "", (
        ("Outra pessoa conduzindo o veículo sem autorização", _moeda(t["multa_terceiro_conduzir"]), "1.2"),
        ("Não apresentar o veículo para vistoria mensal", f"{_moeda(t['multa_vistoria_por_dia'])} por dia", "3.3"),
        ("Perder o prazo para transferência de pontos", _moeda(t["multa_pontos_cnh"]), "5.3"),
        ("Veículo no depósito por culpa do locatário", f"{_moeda(t['multa_deposito_por_dia'])} por dia + custos", "5.4"),
        ("Acionar a Proteção Veicular sem permissão", _moeda(t["multa_acionar_protecao"]), "5.6"),
        (f"Sair do {t['perimetro_permitido']} sem autorização", f"{_moeda(t['multa_fora_perimetro'])} + custos", "5.8"),
        ("Erro na troca de óleo (prazo, óleo errado ou sem foto/nota)", f"{_moeda(t['multa_troca_oleo'])} por ocorrência", "5.13.1"),
        (f"Veículo apreendido e não liberado em {t['apreensao_prazo_dias']} dias", "Rescisão e retomada do veículo", "7.4"),
        ("Atraso no pagamento", f"{_moeda(t['atraso_multa'])} + {_moeda(t['atraso_juros_por_dia'])} por dia", "8.2"),
        (f"Atraso de parcela acima de {t['atraso_dias_rescisao']} dias", "Rescisão e retomada do veículo", "8.4"),
        (f"Dívida acima de {_moeda(t['divida_limite_retomada'])} sem quitar", f"{_moeda(t['multa_retomada_por_dia'])} por dia sem devolver", "10.2.5"),
        ("Atraso na devolução após rescisão", f"{_moeda(t['multa_devolucao_por_dia'])} por dia", "11.1"),
    ))


def montar(contrato: dict, cliente: dict, moto: dict | list, locador: dict) -> list[Bloco]:
    """Contrato completo, na ordem do documento, como lista de blocos.

    `moto` é uma moto ou a lista das motos do contrato (a principal primeiro): cada uma ganha o seu quadro."""
    motos = list(moto) if isinstance(moto, (list, tuple)) else [moto]
    t = TERMOS
    promessa = contrato.get("tipo_contrato") == "promessa_compra"
    inicio = _como_data(contrato["data_inicio"])
    primeira, ultima, restantes = _datas_das_parcelas(contrato, inicio)
    foro = _limpa(locador.get("foro")) or t["foro_padrao"]
    cidade = _limpa(locador.get("cidade")) or foro
    b: list[Bloco] = [Bloco("titulo", "", TITULO_PROMESSA if promessa else TITULO_LOCACAO)]
    b += _partes(locador, cliente, promessa)

    def clausula(numero: int, titulo: str):
        b.append(Bloco("clausula", "", f"CLÁUSULA {numero}ª - {titulo}"))

    def item(numero: str, texto: str):
        b.append(Bloco("item", numero, texto))

    def subitem(numero: str, texto: str):
        b.append(Bloco("subitem", numero, texto))

    clausula(1, "DO OBJETO DO CONTRATO")
    plural = len(motos) > 1
    item("1.1.", "Por meio deste contrato regula-se a locação, " + ("com promessa de compra e venda ao final, " if promessa else "")
         + ("dos veículos abaixo descritos" if plural else "do veículo abaixo descrito")
         + ", de propriedade do LOCADOR:")
    km_inicial = contrato.get("km_inicial") or 0
    for indice, veiculo in enumerate(motos):
        if plural:
            b.append(Bloco("legenda", "", f"Veículo {indice + 1} de {len(motos)}"))
        # `km_inicial` é o da moto principal; as demais saem para preencher à mão.
        b.append(_quadro_veiculo(veiculo, km_inicial if indice == 0 else None))
    item("1.2.", f"{'Os veículos descritos acima serão utilizados' if plural else 'O veículo descrito acima será utilizado'} "
         "exclusivamente pelo LOCATÁRIO, não sendo permitido sub-rogar para terceiros os direitos por ele obtidos através do "
         "presente contrato, nem permitir que outra pessoa conduza o referido veículo sem a inequívoca e expressa autorização "
         f"do LOCADOR, sob pena de rescisão contratual, multa de {_r(t['multa_terceiro_conduzir'])}, bem como responsabilização "
         "total por qualquer ato ou dano em relação ao veículo, inclusive os provenientes de caso fortuito ou força maior.")
    item("1.3.", "O LOCATÁRIO declara ter vistoriado o veículo no ato da entrega, recebendo-o em perfeitas condições de uso e funcionamento.")

    clausula(2, "DA NATUREZA DO CONTRATO E DA PROPRIEDADE")
    if promessa:
        item("2.1.", "A posse direta do veículo é transferida ao LOCATÁRIO na data da assinatura deste contrato, permanecendo a "
             "propriedade com o LOCADOR até a quitação integral da entrada, de todas as parcelas e demais obrigações deste instrumento.")
        item("2.2.", "As partes reconhecem que os valores pagos durante a vigência deste contrato correspondem à remuneração pela "
             "locação e pelo uso do veículo. A transferência da propriedade é condição futura, que somente ocorrerá com o pagamento "
             "integral, não se operando de forma antecipada ou proporcional.")
    else:
        item("2.1.", "A posse direta do veículo é transferida ao LOCATÁRIO na data da assinatura deste contrato, permanecendo a "
             "propriedade com o LOCADOR durante toda a vigência do contrato e após o seu término.")
        item("2.2.", "As partes reconhecem que os valores pagos durante a vigência deste contrato correspondem à remuneração pela "
             "locação e pelo uso do veículo, não gerando ao LOCATÁRIO qualquer direito à aquisição do bem.")
    item("2.3.", ("Enquanto não houver quitação integral, é" if promessa else "Durante a vigência deste contrato, é")
         + " proibido ao LOCATÁRIO vender, prometer vender, trocar, emprestar, "
         "ceder, sublocar, dar em garantia ou de qualquer forma negociar o veículo.")

    clausula(3, "DA VISTORIA DO VEÍCULO")
    item("3.1.", "O veículo em questão permanecerá na posse do LOCATÁRIO por período integral, de segunda a domingo.")
    item("3.2.", "O LOCATÁRIO deverá apresentar o veículo ao LOCADOR 01 (uma) vez por mês para a realização de vistoria, "
         "em data e endereço por este designados.")
    item("3.3.", "A não apresentação do veículo no prazo e local supracitados acarretará ao LOCATÁRIO multa de "
         f"{_r(t['multa_vistoria_por_dia'])} por dia de atraso, além de possível rescisão contratual.")

    clausula(4, "DAS OBRIGAÇÕES DO LOCADOR")
    item("4.1.", "O veículo objeto do presente contrato será submetido à manutenção preventiva periódica, ou em decorrência de "
         "problemas mecânicos e/ou elétricos aos quais o LOCATÁRIO não deu causa, em oficina mecânica designada pelo LOCADOR, "
         "nos termos a seguir:")
    subitem("4.1.1.", "Troca do kit de tração: sempre que houver barulho anormal e/ou apresentar desgaste excessivo;")
    subitem("4.1.2.", "Troca de pneus: quando estiverem no nível do indicador de desgaste (TWI - Tread Wear Indicator).")
    item("4.2.", "Caso alguma das manutenções supracitadas seja necessária antes ou durante o período estipulado, deverá ser "
         "arcada integralmente pelo LOCADOR, salvo nos casos em que o LOCATÁRIO tenha dado causa ao evento, por mau uso.")
    item("4.3.", "Os gastos decorrentes da manutenção preventiva periódica supracitada, bem como o valor pago pela mão de obra "
         "do profissional que realizará o serviço, serão suportados pelo LOCADOR.")
    item("4.4.", "As manutenções que não foram citadas no item 4.1 também serão arcadas pelo LOCADOR, quando forem necessárias "
         "e atestadas pelo mecânico do mesmo.")
    item("4.5.", "No caso de problemas mecânicos e/ou elétricos (quebra, defeito e/ou desgaste) percebidos em ocasião diversa da "
         "manutenção preventiva periódica, o LOCATÁRIO deverá informar imediatamente ao LOCADOR, bem como apresentar o veículo "
         "a este, no prazo de 24 horas, para reparo a ser realizado em oficina mecânica designada pelo LOCADOR.")
    item("4.6.", "O LOCADOR obriga-se a manter Proteção Veicular contratada para o veículo objeto do presente contrato, com "
         f"proteção para terceiros limitada a {_r(t['protecao_terceiros_limite'])}, observadas as regras e exclusões da "
         "associação/seguradora (inclusive a Cláusula 6ª).")
    subitem("4.6.1.", "É de responsabilidade do LOCADOR o pagamento do IPVA, do Licenciamento e do Seguro Obrigatório do veículo "
            "durante a vigência do presente contrato.")
    item("4.7.", "O LOCADOR não se obriga a disponibilizar veículo reserva e não se responsabiliza caso o LOCATÁRIO não possa "
         "dirigir devido à indisponibilidade do veículo.")

    clausula(5, "DAS OBRIGAÇÕES DO LOCATÁRIO")
    item("5.1.", "É de responsabilidade do LOCATÁRIO a observância básica dos itens do veículo, como calibragem dos pneus, nível "
         "de óleo do motor, nível de fluido de freio, sistema de iluminação e sinalização, entre outros.")
    subitem("5.1.1.", "Quaisquer danos/avarias ao veículo serão apurados e os custos de reparação serão arcados pelo LOCATÁRIO.")
    subitem("5.1.2.", "Os custos de revisões reparatórias causadas pelo mau uso do veículo correrão por conta do LOCATÁRIO. Caso "
            "a bomba de combustível queime ou se danifique por falta de combustível ou negligência quando o veículo estiver em "
            "posse do LOCATÁRIO, este deverá arcar com o valor integral da peça, mão de obra, reboque do veículo e demais valores "
            "inerentes ao reparo.")
    item("5.2.", "É de responsabilidade do LOCATÁRIO o pagamento de quaisquer multas relativas às infrações de trânsito "
         "inerentes à utilização do veículo cometidas na vigência deste contrato.")
    subitem("5.2.1.", f"O pagamento das multas pelo LOCATÁRIO deve ser feito imediatamente após a constatação no sistema do "
            f"{t['orgao_transito']}, independentemente de qualquer procedimento, seja transferência de pontos ou recurso.")
    subitem("5.2.2.", "O LOCATÁRIO concorda que o LOCADOR irá indicá-lo como condutor/infrator responsável pelas infrações de "
            "trânsito apuradas durante a locação, nos termos do artigo 257, §§ 1º, 3º, 7º e 8º, do Código de Trânsito Brasileiro. "
            "A partir da indicação, o LOCATÁRIO terá legitimidade para se defender perante o órgão autuador.")
    subitem("5.2.3.", "Qualquer questionamento sobre eventual improcedência de infração de trânsito deverá ser feito "
            "exclusivamente pelo LOCATÁRIO perante o órgão autuador.")
    subitem("5.2.4.", "Caso o LOCATÁRIO opte por recorrer da autuação e o recurso seja vitorioso, o LOCADOR lhe fornecerá cópia "
            "da guia de pagamento para que ele solicite ao órgão o reembolso.")
    item("5.3.", "Ocorrendo as multas acima mencionadas, quando a autuação da infração chegar ao LOCADOR, deverá o LOCATÁRIO "
         "comparecer em local e data estipulados pelo LOCADOR para a assinatura do auto de infração, com o intuito de "
         f"transferência dos pontos, sob pena de pagar ao LOCADOR a quantia de {_r(t['multa_pontos_cnh'])} em caso de perda do "
         "prazo para a transferência dos pontos.")
    item("5.4.", "Caso o veículo seja rebocado por estacionamento irregular, ou outra hipótese à qual o LOCATÁRIO tenha dado "
         "causa, este deverá arcar com todos os custos necessários para a recuperação do veículo junto ao respectivo depósito "
         f"público, além de multa contratual de {_r(t['multa_deposito_por_dia'])} por dia em que o veículo permanecer no depósito, "
         "a título de lucro cessante, observado o disposto na Cláusula 7ª.")
    item("5.5.", "Caso o LOCATÁRIO estacione em local diferente do informado ao LOCADOR, conforme declaração assinada, deverá "
         "arcar com qualquer dano ou prejuízo pecuniário ao veículo, inclusive os inerentes a caso fortuito ou força maior.")
    item("5.6.", "É proibido ao LOCATÁRIO acionar o serviço de Proteção Veicular do veículo objeto deste contrato sem a expressa "
         f"permissão do LOCADOR, sob pena de multa de {_r(t['multa_acionar_protecao'])}, além da obrigação de arcar com "
         "eventuais custos de reboques e/ou transportes necessários, caso o serviço de Proteção Veicular não mais os "
         "disponibilize devido ao limite de utilizações mensais.")
    item("5.7.", "O LOCATÁRIO se responsabiliza por quaisquer acessórios do veículo que estiverem em sua posse, como chave de "
         "ignição, documento do veículo etc. Caso algum acessório seja perdido ou danificado, o LOCATÁRIO deverá arcar com todos "
         "os custos necessários à reposição.")
    item("5.8.", f"É proibido ao LOCATÁRIO sair do perímetro urbano denominado {t['perimetro_permitido']} com o veículo objeto "
         f"deste contrato sem a autorização expressa e por escrito do LOCADOR, sob pena de multa de {_r(t['multa_fora_perimetro'])}, "
         "além do pagamento dos custos para o retorno do veículo a Crato e de eventuais danos ocorridos com o veículo, "
         "inclusive por caso fortuito e força maior.")
    item("5.9.", "Em caso de roubo ou furto do veículo, o LOCATÁRIO se compromete a avisar imediatamente o LOCADOR, bem como a "
         "comparecer à delegacia de polícia para registrar a ocorrência no mesmo dia.")
    item("5.10.", "O LOCATÁRIO se compromete a comparecer à sede da empresa de Proteção Veicular, ou a outro local especificado "
         "por ela, a fim de cumprir o procedimento de indenização do veículo.")
    item("5.11.", "Caso o LOCATÁRIO se envolva em sinistro estando sob efeito de álcool/entorpecentes, ou se recusar o teste de "
         "embriaguez requerido pela autoridade, deverá pagar ao LOCADOR o valor da tabela FIPE do veículo, caso a indenização "
         "da Proteção Veicular seja negada, e/ou todos os custos inerentes à recuperação do veículo junto ao depósito, em caso "
         "de reboque.")
    item("5.12.", "O LOCATÁRIO deve manter as características originais do veículo; portanto, a instalação de adesivos, pinturas "
         "especiais, equipamentos ou acessórios no veículo está sujeita à autorização prévia, por escrito, do LOCADOR. Neste "
         "caso, a retirada dos mesmos e a recuperação do veículo ao seu estado original, em caso de devolução, são de "
         "responsabilidade do LOCATÁRIO.")
    item("5.13.", f"É de responsabilidade do LOCATÁRIO o pagamento e a troca do óleo do motor a cada {_milhar(t['troca_oleo_km'])} km "
         "rodados, de acordo com as especificações do fabricante do veículo, sendo exigida foto do painel do veículo e nota "
         "fiscal da compra do óleo.")
    subitem("5.13.1.", f"O descumprimento do item 5.13, seja pela troca do óleo fora do prazo de {_milhar(t['troca_oleo_km'])} km, pelo uso "
            "de óleo em desacordo com a especificação do fabricante ou pela falta de envio da foto do painel e da nota fiscal, "
            f"sujeitará o LOCATÁRIO à multa de {_r(t['multa_troca_oleo'])} por ocorrência, sem prejuízo da responsabilidade por "
            "eventuais danos ao motor, nos termos do item 5.1.2.")
    item("5.14.", "O LOCATÁRIO aceita que o LOCADOR promova, pelos meios processuais de que venha a dispor, o seu chamamento aos "
         "feitos judiciais promovidos por terceiros decorrentes de eventos com o veículo, cabendo-lhe assumir o polo passivo nas "
         "demandas, inclusive quanto aos valores reclamados por terceiros e/ou para assegurar os direitos regressivos do "
         "LOCADOR. O LOCATÁRIO será responsável pelo pagamento de lucros cessantes que terceiros possam pleitear judicialmente "
         "em razão de sua conduta irregular.")

    clausula(6, "DA HABILITAÇÃO DO LOCATÁRIO")
    item("6.1.", "O LOCATÁRIO declara possuir Carteira Nacional de Habilitação (CNH) válida na categoria \"A\", cujo número consta "
         "do preâmbulo, e obriga-se a mantê-la válida durante toda a vigência deste contrato.")
    item("6.2.", "Em caso de suspensão, cassação, vencimento ou recolhimento da CNH, o LOCATÁRIO deverá comunicar o fato ao "
         "LOCADOR em até 24 (vinte e quatro) horas e ficará proibido de conduzir o veículo até a regularização, sob pena de "
         "rescisão contratual.")
    item("6.3.", "Se a Proteção Veicular negar cobertura por irregularidade na habilitação do LOCATÁRIO, este responderá "
         "integralmente pelos danos ao veículo, limitados ao valor da tabela FIPE do veículo na data do evento, e pelos danos "
         "causados a terceiros.")

    clausula(7, "DA APREENSÃO DO VEÍCULO E DA RETOMADA PELO LOCADOR")
    dias = t["apreensao_prazo_dias"]
    item("7.1.", "Caso o veículo seja apreendido, removido ou retido por autoridade de trânsito ou policial por qualquer motivo "
         "atribuível ao LOCATÁRIO, inclusive pela condução sem habilitação, o LOCATÁRIO deverá comunicar o fato ao LOCADOR "
         "imediatamente e arcar, sozinho, com todas as multas, taxas, guincho, diárias de pátio e demais despesas necessárias "
         "à liberação.")
    item("7.2.", f"O LOCATÁRIO terá o prazo de **{_n(dias)} dias corridos**, contados da data da apreensão, para quitar todos os "
         "valores e liberar o veículo, entregando ao LOCADOR os comprovantes de pagamento e de liberação.")
    item("7.3.", "Durante o período em que o veículo estiver apreendido, as parcelas previstas na Cláusula 8ª continuam vencendo "
         "normalmente, sem qualquer desconto ou suspensão.")
    item("7.4.", "Decorrido o prazo do item 7.2 sem que o LOCATÁRIO tenha liberado o veículo, o presente contrato estará "
         "**rescindido de pleno direito**, independentemente de notificação, ficando o LOCADOR autorizado a quitar os valores "
         "pendentes, retirar o veículo do pátio e retomá-lo em definitivo, voltando o veículo à sua livre disposição, sem que o "
         "LOCATÁRIO tenha direito " + ("à aquisição do bem, a " if promessa else "a ") + "qualquer indenização ou à restituição dos valores já pagos, que "
         "permanecerão com o LOCADOR como remuneração pelo uso do veículo (item 2.2).")
    item("7.5.", "Na hipótese do item 7.4, o LOCATÁRIO continuará devedor do LOCADOR de todos os valores por este desembolsados "
         "para a liberação do veículo, das parcelas vencidas até a data da rescisão, das multas contratuais e dos eventuais "
         "danos ao veículo, podendo o LOCADOR cobrá-los inclusive judicialmente.")

    clausula(8, "DO PREÇO E DA FORMA DE PAGAMENTO")
    b.append(_quadro_preco(contrato, inicio, primeira, ultima, restantes) if promessa else _quadro_preco_locacao(contrato, inicio))
    item("8.1.", "O LOCATÁRIO pagará ao LOCADOR os valores indicados no quadro acima, até o dia do vencimento de cada parcela.")
    item("8.2.", "Caso o pagamento seja feito após a data acordada, o valor sofrerá um acréscimo de "
         f"{_r(t['atraso_multa'])} a título de multa, bem como um acréscimo de {_r(t['atraso_juros_por_dia'])} por dia de atraso "
         "a título de juros.")
    item("8.3.", "Fica o LOCATÁRIO obrigado a encaminhar o comprovante de pagamento ao LOCADOR no dia do pagamento, valendo o "
         "mesmo como recibo.")
    item("8.4.", f"O atraso de qualquer parcela por mais de **{_n(t['atraso_dias_rescisao'])} dias** autoriza o LOCADOR a "
         "considerar o contrato rescindido, nos termos da Cláusula 10ª, e a retomar o veículo.")
    item("8.5.", "Eventual tolerância do LOCADOR quanto a atrasos é mera liberalidade e não altera as condições deste contrato.")

    clausula(9, "DAS DESPESAS NA DEVOLUÇÃO DO VEÍCULO")
    item("9.1.", "Os gastos com o combustível do veículo deverão ser arcados integralmente pelo LOCATÁRIO. Em caso de devolução, "
         "o veículo deverá ser entregue com a mesma quantidade de combustível contida quando da entrega pelo LOCADOR, sob "
         "pena de cobrança do valor necessário para atingir tal quantidade.")
    item("9.2.", "Qualquer valor inerente a cobrança por passagem, estacionamento ou pedágio do veículo durante a posse do "
         "LOCATÁRIO deverá por este ser arcado. Caso o LOCADOR seja cobrado por qualquer valor desta natureza, o LOCATÁRIO "
         "deverá reembolsá-lo imediatamente.")
    item("9.3.", "Caso o veículo seja devolvido sujo, será cobrada a lavagem simples "
         f"({_moeda(t['lavagem_simples'])}) ou especial ({_moeda(t['lavagem_especial'])}), dependendo do seu estado.")
    item("9.4.", "Quando o documento do veículo não for devolvido, será cobrado o reembolso das despesas para obtenção da 2ª via.")

    clausula(10, "DA VIGÊNCIA E DA RESCISÃO")
    if promessa:
        item("10.1.", "O presente contrato se inicia na data de sua assinatura e vigora até a quitação integral do preço previsto "
             "na Cláusula 8ª.")
    elif contrato.get("data_fim_prevista"):
        item("10.1.", f"O presente contrato se inicia na data de sua assinatura e vigora até {_data(contrato['data_fim_prevista'])}, "
             "salvo rescisão nos termos desta cláusula.")
    else:
        item("10.1.", "O presente contrato se inicia na data de sua assinatura e vigora por prazo indeterminado, podendo ser "
             "encerrado nos termos desta cláusula.")
    item("10.2.", "O contrato poderá ser considerado rescindido de pleno direito pelo LOCADOR, independentemente de qualquer "
         "notificação, e este, sem mais formalidades, providenciará a retomada do veículo, sem que isso enseje ao LOCATÁRIO "
         "qualquer direito de retenção, indenização ou devolução dos valores pagos, quando:")
    subitem("10.2.1.", f"O LOCATÁRIO atrasar qualquer parcela por mais de {_n(t['atraso_dias_rescisao'])} dias;")
    subitem("10.2.2.", "Ocorrer o uso inadequado do veículo ou a condução por terceiro não autorizado;")
    subitem("10.2.3.", "O veículo apreendido não for liberado pelo LOCATÁRIO no prazo do item 7.2;")
    subitem("10.2.4.", "O LOCATÁRIO tentar vender, ceder, esconder ou dar em garantia o veículo;")
    subitem("10.2.5.", f"O LOCATÁRIO acumular dívida superior a {_r(t['divida_limite_retomada'])} com o LOCADOR (multas, despesas ou "
            "reembolsos) e não a quitar imediatamente, caso em que o veículo deverá ser entregue em local determinado pelo "
            f"LOCADOR, imediatamente, sob pena de multa de {_r(t['multa_retomada_por_dia'])} por dia, salvo acordo contrário entre as partes.")
    item("10.3.", f"Em qualquer hipótese de rescisão, o LOCATÁRIO deverá devolver o veículo em até {_n(t['devolucao_horas'])} horas, no "
         "local indicado pelo LOCADOR. Os valores pagos " + ("(entrada e parcelas) " if promessa else "") + "permanecerão com o LOCADOR como remuneração pelo uso "
         "do veículo, nos termos do item 2.2, e continuarão devidos as parcelas vencidas até a devolução, as multas, as despesas "
         "e os danos.")
    item("10.4.", ("O LOCATÁRIO poderá desistir da compra" if promessa else "O LOCATÁRIO poderá encerrar a locação")
         + " a qualquer momento, devolvendo o veículo ao LOCADOR, aplicando-se o disposto no item 10.3.")
    item("10.5.", "Fica desde já pactuada a total inexistência de vínculo trabalhista entre as partes do presente contrato, sendo "
         "indevida toda e qualquer incidência das obrigações previdenciárias e dos encargos sociais, não havendo entre as partes "
         "qualquer tipo de subordinação e controle típicos de relações de emprego.")
    item("10.6.", "Nos termos do artigo 265 do Código Civil Brasileiro, inexiste solidariedade, seja contratual ou legal, entre o "
         "LOCADOR e o LOCATÁRIO, razão pela qual, com a efetiva retirada do veículo, o LOCATÁRIO assume sua posse autônoma para "
         "todos os fins de direito, responsabilizando-se por eventuais indenizações decorrentes do uso e circulação do veículo, "
         "responsabilidade que perdurará até a efetiva devolução ou transferência do veículo.")

    clausula(11, "DA DEVOLUÇÃO DO VEÍCULO")
    item("11.1.", "Rescindido o contrato, o veículo deve ser devolvido em local, dia e hora indicados pelo LOCADOR, sob pena de "
         f"multa de {_r(t['multa_devolucao_por_dia'])} por dia.")
    item("11.2.", "A não devolução do veículo pelo LOCATÁRIO, após notificação realizada pelo LOCADOR, configura crime de "
         "**APROPRIAÇÃO INDÉBITA**, conforme artigo 168 do Código Penal Brasileiro, com pena de reclusão de 1 (um) a 4 (quatro) "
         "anos e multa.")

    if promessa:
        clausula(12, "DA QUITAÇÃO E DA TRANSFERÊNCIA DO VEÍCULO")
        item("12.1.", "Quitados a entrada, todas as parcelas e todos os demais débitos deste contrato, a promessa de compra e venda "
             "tornar-se-á efetiva e o LOCADOR assinará a Autorização para Transferência de Propriedade do Veículo (ATPV-e) em favor "
             f"do LOCATÁRIO, em até {_n(t['transferencia_prazo_dias_uteis'])} dias úteis, mediante termo de quitação.")
        item("12.2.", "Todas as despesas da transferência, como taxas do DETRAN, vistoria, reconhecimento de firma, emplacamento e "
             "quaisquer outros custos, são de **responsabilidade exclusiva do LOCATÁRIO**.")
        item("12.3.", f"O LOCATÁRIO deverá efetuar a transferência do veículo para o seu nome no prazo de {_n(t['transferencia_prazo_dias'])} "
             "dias da assinatura da ATPV-e (artigo 123 do Código de Trânsito Brasileiro), respondendo por qualquer multa ou "
             "penalidade decorrente do atraso.")

    gerais = 13 if promessa else 12
    clausula(gerais, "DAS DISPOSIÇÕES GERAIS")
    item(f"{gerais}.1.", "Quaisquer notificações e comunicações enviadas sob este contrato podem ser realizadas de forma eletrônica "
         "(e-mail ou WhatsApp), escrita ou por correspondência com aviso de recebimento aos endereços constantes do preâmbulo. "
         "Havendo alteração de endereço, ficam as partes obrigadas a fornecer tal informação.")
    item(f"{gerais}.2.", "Todos os valores, despesas e encargos deste contrato constituem dívidas líquidas e certas, passíveis de cobrança "
         "executiva. Assinado pelas partes e por duas testemunhas, este contrato é título executivo extrajudicial (artigo 784, "
         "III, do Código de Processo Civil).")
    item(f"{gerais}.3.", "Eventuais tolerâncias do LOCADOR para com o LOCATÁRIO no cumprimento das obrigações ajustadas neste contrato "
         "constituem mera liberalidade, não importando, em hipótese alguma, em novação ou renúncia, permanecendo íntegras as "
         "cláusulas e condições aqui contratadas.")
    item(f"{gerais}.4.", "O LOCATÁRIO autoriza o LOCADOR a coletar, usar e divulgar a sua imagem para fins de cadastro, defesa e/ou "
         "promoção.")
    item(f"{gerais}.5.", "O LOCATÁRIO concorda que a sua assinatura no contrato implica ciência e adesão, por si, seus herdeiros e "
         "sucessores, a estas cláusulas, e declara ter lido e compreendido todo o seu conteúdo, especialmente as Cláusulas 6ª e 7ª.")
    item(f"{gerais}.6.", f"Fica eleito o foro da Comarca de {foro} como competente para dirimir quaisquer questões que possam advir da "
         "aplicação do presente contrato, com renúncia a qualquer outro, por mais privilegiado que seja ou venha a ser.")
    item(f"{gerais}.7.", "E, por estarem assim justas e contratadas, as partes firmam o presente instrumento em 02 (duas) vias de igual "
         "teor e forma, para que produza seus efeitos legais, após terem lido o seu conteúdo, o qual foi claramente entendido e aceito.")

    b.append(Bloco("legenda", "", "RESUMO DAS MULTAS E VALORES DESTE CONTRATO"))
    b.append(Bloco("legenda", "", "Quadro apenas de consulta rápida. Em caso de dúvida, vale o texto da cláusula indicada."))
    b.append(_resumo_de_multas())
    b.append(Bloco("fecho", "", f"{cidade}, {data_por_extenso(inicio)}."))

    nome_locador = _limpa(locador.get("representante_nome")) or _limpa(locador.get("nome"))
    b.append(Bloco("assinatura", f"{'LOCADOR / PROMITENTE VENDEDOR' if promessa else 'LOCADOR'} - CPF {_cpf(locador.get('representante_cpf'))}", _v(nome_locador, "LOCADOR").upper()))
    b.append(Bloco("assinatura", f"{'LOCATÁRIO / PROMITENTE COMPRADOR' if promessa else 'LOCATÁRIO'} - CPF {_cpf(cliente.get('cpf'))}", _v(cliente.get("nome"), "LOCATÁRIO").upper()))
    return b
