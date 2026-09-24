"""Modelo do contrato de locação de motocicleta (funções puras).

Reproduz o modelo de contrato usado pela empresa (10 cláusulas). O que muda de um
contrato para outro (partes, veículo, valor, caução, datas) vem dos dados; as
penalidades e prazos fixos do modelo ficam em TERMOS, num só lugar, para facilitar
a revisão com o advogado. Tudo em Latin-1 (fonte padrão do PDF): sem travessão
longo, aspas curvas ou marcadores tipográficos.
"""

from datetime import date
from decimal import Decimal
from typing import NamedTuple

from src.domain.extenso import data_por_extenso, moeda_por_extenso

TERMOS = {
    "multa_terceiro_conduzir": Decimal("500.00"),
    "multa_vistoria_por_dia": Decimal("20.00"),
    "protecao_terceiros_limite": Decimal("10000.00"),
    "multa_pontos_cnh": Decimal("200.00"),
    "multa_deposito_por_dia": Decimal("30.00"),
    "multa_acionar_protecao": Decimal("200.00"),
    "multa_fora_perimetro": Decimal("150.00"),
    "perimetro_permitido": "Grande Fortaleza",
    "orgao_transito": "DETRAN-CE",
    "troca_oleo_km": 1000,
    "cota_participacao_protecao": Decimal("700.00"),
    "atraso_multa": Decimal("15.00"),
    "atraso_juros_por_dia": Decimal("7.00"),
    "caucao_devolucao_dias_uteis": 20,
    "lavagem_simples": Decimal("15.00"),
    "lavagem_especial": Decimal("45.00"),
    "lavagem_especial_max_diarias": 10,
    "prazo_minimo_dias": 30,
    "devolucao_antecipada_percentual": 50,
    "divida_limite_retomada": Decimal("100.00"),
    "multa_retomada_por_dia": Decimal("150.00"),
    "multa_devolucao_por_dia": Decimal("50.00"),
    "foro_padrao": "Fortaleza-CE",
}

_PERIODO = {
    "diario": "por dia",
    "semanal": "por semana",
    "quinzenal": "por quinzena",
    "mensal": "por mês",
}
_EM_BRANCO = "..............................."
_LOCADOR = "**LOCADOR**"
_LOCATARIO = "**LOCATÁRIO**"


class Bloco(NamedTuple):
    """tipo: preambulo | clausula | item | subitem | fecho | assinatura."""

    tipo: str
    numero: str
    texto: str


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


def _ano(moto) -> str:
    ano_fab, ano_mod = moto.get("ano_fabricacao"), moto.get("ano_modelo")
    if ano_fab and ano_mod and ano_fab != ano_mod:
        return f"{ano_fab}/{ano_mod}"
    return _v(ano_fab or ano_mod)


def _telefones(cliente) -> str:
    numeros = []
    for chave in ("telefone", "whatsapp"):
        numero = _limpa(cliente.get(chave))
        if numero and numero not in numeros:
            numeros.append(numero)
    return " / ".join(numeros) if numeros else _EM_BRANCO


def _preambulo(locador, cliente) -> str:
    empresa = (
        f"**{_v(locador.get('nome'))}**, inscrita no CNPJ sob o número "
        f"{_v(locador.get('cnpj'))} e inscrição estadual {_v(locador.get('inscricao_estadual'))}, "
        f"e-mail: {_v(locador.get('email'))}, telefone {_v(locador.get('telefones'))}, "
        f"sediada em: {_v(locador.get('endereco'))}, representada por: "
        f"{_v(locador.get('representante_nome'))}, {_v(locador.get('representante_qualificacao'))}, "
        f"portador da cédula de identidade {_v(locador.get('representante_rg'))}, "
        f"inscrito com o CPF de número: {_cpf(locador.get('representante_cpf'))}, "
        f"doravante denominada {_LOCADOR}, e de outro lado;"
    )
    locatario = (
        f"**{_v(cliente.get('nome')).upper()}**, nacionalidade: {_EM_BRANCO}, "
        f"estado civil: {_EM_BRANCO}, profissão: {_EM_BRANCO}, portador da cédula de "
        f"identidade nº {_EM_BRANCO}, inscrito no CPF {_cpf(cliente.get('cpf'))}, "
        f"e-mail: {_v(cliente.get('email'))}, telefone {_telefones(cliente)}, "
        f"residente em: {_v(cliente.get('endereco'))}, doravante denominado {_LOCATARIO}, "
        "têm entre si como justo e contratado o que segue:"
    )
    return f"Pelo presente instrumento particular, de um lado: {empresa} {locatario}"


def montar(contrato: dict, cliente: dict, moto: dict, locador: dict) -> list[Bloco]:
    """Contrato completo, na ordem do documento, como lista de blocos."""
    t = TERMOS
    inicio = _como_data(contrato["data_inicio"])
    fim = contrato.get("data_fim_prevista")
    periodo = _PERIODO.get(contrato.get("periodicidade"), "por período")
    foro = _limpa(locador.get("foro")) or t["foro_padrao"]
    cidade = _v(locador.get("cidade"), "_______________")

    prazo_final = (
        f", com término previsto para {_data(fim)}" if fim else ""
    )

    b: list[Bloco] = []

    def clausula(numero: int, titulo: str):
        b.append(Bloco("clausula", "", f"CLÁUSULA {numero}ª - {titulo}"))

    def item(numero: str, texto: str):
        b.append(Bloco("item", numero, texto))

    def subitem(numero: str, texto: str):
        b.append(Bloco("subitem", numero, texto))

    b.append(Bloco("preambulo", "", _preambulo(locador, cliente)))

    clausula(1, "DO OBJETO DO CONTRATO")
    item(
        "1.1.",
        "Por meio deste contrato regula-se a locação do veículo: Motocicleta de marca: "
        f"{_v(moto.get('marca')).upper()}, Modelo: {_v(moto.get('modelo')).upper()}, "
        f"Placa: {_v(moto.get('placa')).upper()}, Renavam nº {_v(moto.get('renavam'))}, "
        f"Chassi: {_v(moto.get('chassi')).upper()}, Motor: {_EM_BRANCO}, "
        f"Cor: {_v(moto.get('cor')).upper()}, Ano: {_ano(moto)}, "
        f"Quilometragem: {_milhar(contrato.get('km_inicial'))}.",
    )
    item(
        "1.2.",
        f"O veículo descrito acima será utilizado exclusivamente pelo {_LOCATARIO}, não sendo "
        "permitido sub-rogar para terceiros os direitos por ele obtidos através do presente "
        f"contrato, nem permitir que outra pessoa conduza o referido veículo sem a inequívoca "
        f"e expressa autorização do {_LOCADOR}, sob pena de rescisão contratual, multa de "
        f"{_r(t['multa_terceiro_conduzir'])} bem como responsabilização total por qualquer ato "
        "ou dano em relação ao veículo, inclusive os provenientes de caso fortuito ou força maior.",
    )

    clausula(2, "DO HORÁRIO DO ALUGUEL E LOCAL DE COLETA E DEVOLUÇÃO DO VEÍCULO")
    item(
        "2.1.",
        f"O veículo em questão permanecerá na posse do {_LOCATARIO} por período integral, de "
        "segunda a domingo.",
    )
    item(
        "2.2.",
        f"O {_LOCATARIO} deverá apresentar o veículo ao {_LOCADOR} 01 (uma) vez por mês para a "
        "realização de vistoria, em data e endereço por este designado.",
    )
    item(
        "2.3.",
        "A não apresentação do veículo no prazo e local supracitados acarretará ao "
        f"{_LOCATARIO} multa de {_r(t['multa_vistoria_por_dia'])} por dia de atraso, além de "
        "possível rescisão contratual.",
    )

    clausula(3, "DAS OBRIGAÇÕES DO LOCADOR")
    item(
        "3.1.",
        "O veículo objeto do presente contrato será submetido à manutenção preventiva "
        "periódica, ou em decorrência de problemas mecânicos e/ou elétricos aos quais o "
        f"{_LOCATARIO} não deu causa, em oficina mecânica designada pelo {_LOCADOR}, nos "
        "termos a seguir:",
    )
    subitem(
        "3.1.1.",
        "Troca do Kit de Tração: Sempre que houver barulho anormal e/ou apresentar desgaste "
        "excessivo;",
    )
    subitem(
        "3.1.2.",
        "Troca de Pneus: Quando estiverem no nível do Tread Wear Indicator (TWI).",
    )
    item(
        "3.2.",
        "Caso alguma das manutenções supracitadas seja necessária antes ou durante o período "
        f"estipulado, deverá ser arcada integralmente pelo {_LOCADOR}, salvo nos casos em que o "
        f"{_LOCATARIO} tenha dado causa ao evento, por mau uso.",
    )
    item(
        "3.3.",
        "Os gastos decorrentes da manutenção preventiva periódica supracitada, bem como o "
        "valor pago pela mão de obra do profissional que realizará o serviço, serão "
        f"suportados pelo {_LOCADOR}.",
    )
    item(
        "3.4.",
        "As manutenções que não foram citadas na cláusula 3.1 também terão que ser arcadas "
        f"pelo {_LOCADOR}, quando forem necessárias e atestadas pelo mecânico do mesmo.",
    )
    item(
        "3.5.",
        "No caso de problemas mecânicos e/ou elétricos (quebra, defeito e/ou desgaste) "
        f"percebidos em ocasião diversa da manutenção preventiva periódica, o {_LOCATARIO} "
        f"deverá informar imediatamente ao {_LOCADOR}, bem como apresentar o veículo a este, "
        "no prazo de 24 horas, para reparo a ser realizado em oficina mecânica designada pelo "
        f"{_LOCADOR}.",
    )
    item(
        "3.6.",
        f"O {_LOCADOR} obriga-se a manter Proteção Veicular contratada para o veículo objeto "
        f"do presente contrato, com proteção para terceiros limitada a "
        f"{_r(t['protecao_terceiros_limite'])}. É de responsabilidade do {_LOCADOR} o "
        "pagamento do IPVA, Licenciamento, bem como o pagamento do Seguro Obrigatório do "
        "veículo objeto do presente contrato.",
    )
    item(
        "3.7.",
        f"O {_LOCADOR} não se obriga a disponibilizar veículo reserva e não se responsabiliza "
        f"caso o {_LOCATARIO} não possa dirigir devido à indisponibilidade do veículo.",
    )

    clausula(4, "DAS OBRIGAÇÕES DO LOCATÁRIO")
    item(
        "4.1.",
        f"É de responsabilidade do {_LOCATARIO} a observância básica dos itens do veículo como "
        "calibragem dos pneus, nível de óleo do motor, nível de fluido de freio, observância "
        "da marcação, sistema de iluminação e sinalização, entre outros.",
    )
    subitem(
        "4.1.1.",
        "Quaisquer danos/avarias ao veículo serão apurados ao final do contrato e os custos de "
        f"reparação serão arcados pelo {_LOCATARIO}.",
    )
    subitem(
        "4.1.2.",
        "Os custos de revisões reparatórias causadas pelo mau uso dos veículos correrão por "
        f"conta do {_LOCATARIO}. Caso a bomba de combustível queime ou danifique por falta de "
        f"combustível ou negligência quando o veículo estiver em posse do {_LOCATARIO}, este "
        "deverá arcar com o valor integral da peça, mão de obra, reboque do veículo e demais "
        "valores inerentes ao reparo.",
    )
    item(
        "4.2.",
        f"É de responsabilidade do {_LOCATARIO} o pagamento de quaisquer multas relativas às "
        "infrações de trânsito inerentes à utilização do veículo cometidas na vigência deste "
        "contrato.",
    )
    subitem(
        "4.2.1.",
        f"O pagamento das multas pelo {_LOCATARIO} deve ser feito imediatamente após a "
        f"constatação no sistema do {t['orgao_transito']}, independentemente de qualquer "
        "procedimento, seja transferência de pontos ou recurso.",
    )
    subitem(
        "4.2.2.",
        f"O {_LOCATARIO} concorda que o {_LOCADOR} irá indicá-lo como condutor/infrator "
        "responsável pelas infrações de trânsito apuradas durante a locação, nos termos do "
        "artigo 257, parágrafos 1º, 3º, 7º e 8º do Código de Trânsito. A partir da indicação, "
        f"o {_LOCATARIO} terá legitimidade para se defender perante o órgão autuador.",
    )
    subitem(
        "4.2.3.",
        "Qualquer questionamento sobre eventual improcedência de infração de trânsito deverá "
        f"ser feito exclusivamente pelo {_LOCATARIO} perante o órgão autuador.",
    )
    subitem(
        "4.2.4.",
        f"Caso o {_LOCATARIO} opte por recorrer da autuação e sendo o recurso vitorioso, o "
        f"{_LOCADOR} lhe fornecerá cópia da guia de pagamento para que ele solicite ao órgão "
        "o reembolso.",
    )
    item(
        "4.3.",
        "Em ocorrendo multas acima mencionadas, quando a autuação da infração chegar ao "
        f"{_LOCADOR}, deverá o {_LOCATARIO} comparecer em local e data estipulados pelo "
        f"{_LOCADOR} para a assinatura do auto de infração com o intuito de transferência dos "
        f"pontos para a sua CNH, sob pena de pagar ao {_LOCADOR} a quantia de "
        f"{_r(t['multa_pontos_cnh'])}, em caso de perda do prazo para a transferência dos pontos.",
    )
    item(
        "4.4.",
        "Caso o veículo seja rebocado por estacionamento irregular, ou outra hipótese a qual "
        f"tenha dado causa, o {_LOCATARIO} deverá arcar com todos os custos necessários para a "
        f"recuperação do veículo junto ao respectivo depósito público. O {_LOCATARIO} deverá "
        f"arcar também com multa contratual de {_r(t['multa_deposito_por_dia'])} por dia pelo "
        "período em que a moto estiver no depósito, a título de lucro cessante.",
    )
    item(
        "4.5.",
        f"Caso o {_LOCATARIO} estacione em local diferente do informado ao {_LOCADOR} conforme "
        f"declaração assinada, o {_LOCATARIO} deverá arcar com qualquer dano ou prejuízo "
        "pecuniário ao veículo, inclusive inerentes a caso fortuito ou força maior.",
    )
    item(
        "4.6.",
        f"É proibido o {_LOCATARIO} acionar o serviço de Proteção Veicular do veículo objeto "
        f"deste contrato sem a expressa permissão do {_LOCADOR}, sob pena de multa de "
        f"{_r(t['multa_acionar_protecao'])}, além da obrigação de arcar com eventuais custos de "
        "reboques e/ou transportes necessários, caso o serviço de Proteção Veicular não mais "
        "os disponibilize devido ao limite de utilizações mensais deste serviço.",
    )
    item(
        "4.7.",
        f"O {_LOCATARIO} se responsabiliza por quaisquer acessórios do veículo que estiverem em "
        "sua posse, como por exemplo chave de ignição, documento do veículo, etc. Caso algum "
        f"acessório do veículo seja perdido ou danificado, o {_LOCATARIO} deverá arcar com "
        "todos os custos necessários à reposição.",
    )
    item(
        "4.8.",
        f"É proibido o {_LOCATARIO} sair do perímetro urbano denominado {t['perimetro_permitido']} "
        "com o veículo objeto deste contrato sem a autorização expressa e por escrito do "
        f"{_LOCADOR}, sob pena de multa de {_r(t['multa_fora_perimetro'])}, além do pagamento "
        "dos custos para o retorno do veículo, bem como o pagamento de eventuais danos "
        "ocorridos com o veículo, inclusive caso fortuito e força maior.",
    )
    item(
        "4.9.",
        f"Em caso de roubo ou furto do veículo, o {_LOCATARIO} se compromete a avisar "
        f"imediatamente ao {_LOCADOR}, bem como a comparecer à delegacia de polícia mais "
        f"próxima da residência do {_LOCADOR} para registrar a ocorrência.",
    )
    item(
        "4.10.",
        f"O {_LOCATARIO} se compromete a comparecer à sede da empresa de Proteção Veicular, ou "
        "outro local especificado pela mesma, a fim de cumprir com procedimento de indenização "
        "do veículo.",
    )
    item(
        "4.11.",
        f"Caso o {_LOCATARIO} se envolva em sinistro estando sob efeito de álcool/entorpecentes, "
        "ou se não fizer o teste de embriaguez requerido pela autoridade, este deverá pagar ao "
        f"{_LOCADOR} o valor da tabela FIPE do veículo, caso a indenização da Proteção "
        "Veicular seja negada e/ou com todos os custos inerentes à recuperação do veículo "
        "junto ao depósito, em caso de reboque.",
    )
    item(
        "4.12.",
        f"O {_LOCATARIO} deve manter as características originais do veículo, portanto a "
        "instalação de adesivos, pinturas especiais, equipamentos ou acessórios no veículo "
        f"alugado está sujeita à autorização prévia, por escrito, do {_LOCADOR}. Neste caso, a "
        "retirada dos mesmos e a recuperação do veículo ao seu estado original são de "
        f"responsabilidade do {_LOCATARIO}.",
    )
    item(
        "4.13.",
        f"É de responsabilidade do {_LOCATARIO} o pagamento e a troca do óleo do motor a cada "
        f"{_milhar(t['troca_oleo_km'])} km rodados, de acordo com as especificações do "
        "fabricante do veículo. Será exigido foto do painel do veículo e nota fiscal da "
        "compra do óleo.",
    )
    item(
        "4.14.",
        f"Aceitar que o {_LOCADOR} promova, pelos meios processuais de que venha a dispor, o seu "
        "chamamento aos feitos judiciais promovidos por terceiros decorrentes de eventos com o "
        "veículo alugado, cabendo-lhe assumir o polo passivo nas demandas, inclusive quanto aos "
        f"valores reclamados por terceiros e/ou para assegurar os direitos regressivos do "
        f"{_LOCADOR}. O {_LOCATARIO} será responsável pelo pagamento de lucros cessantes que "
        f"terceiros possam pleitear judicialmente em razão de conduta irregular do {_LOCATARIO}.",
    )

    clausula(5, "DAS OBRIGAÇÕES DECORRENTES DE COLISÕES E AVARIAS DO VEÍCULO")
    item(
        "5.1.",
        f"É de responsabilidade do {_LOCATARIO} o pagamento do reboque, taxas e reparos ao "
        "veículo objeto do presente contrato ou a veículo de outrem na ocorrência de acidentes "
        "e colisões sofridas na vigência do presente contrato quando não contempladas pela "
        "cobertura da Proteção Veicular contratada para este veículo, independente de dolo, "
        f"culpa, negligência, imprudência ou imperícia do {_LOCATARIO}.",
    )
    item(
        "5.2.",
        "Na ocorrência da necessidade do pagamento da cota de participação da Proteção "
        f"Veicular, a quantia será integralmente de responsabilidade do {_LOCATARIO}, no valor "
        f"de {_r(t['cota_participacao_protecao'])}.",
    )
    item(
        "5.3.",
        f"Será de responsabilidade do {_LOCATARIO} o pagamento de taxas e diárias para a "
        "liberação do veículo decorrentes de reboque realizado pelo Poder Público, nos casos "
        "supracitados.",
    )
    item(
        "5.4.",
        "A responsabilidade determinada nos itens supracitados permanece estabelecida, "
        f"inclusive, caso o {_LOCATARIO} não se encontre no interior do veículo objeto do "
        "presente contrato.",
    )

    clausula(6, "DO PAGAMENTO EM RAZÃO DA LOCAÇÃO DO VEÍCULO")
    item(
        "6.1.",
        f"O {_LOCATARIO} pagará ao {_LOCADOR} o valor de {_r(contrato['valor_periodo'])} "
        f"{periodo}, o pagamento sempre de forma antecipada ao período correspondente, com "
        f"primeiro vencimento em {_data(inicio)}.",
    )
    item(
        "6.2.",
        "Caso o pagamento seja feito após a data acordada, o valor sofrerá um acréscimo de "
        f"{_r(t['atraso_multa'])} a título de multa, bem como um acréscimo de "
        f"{_r(t['atraso_juros_por_dia'])} por dia de atraso a título de juros.",
    )
    item(
        "6.3.",
        f"Fica o {_LOCATARIO} obrigado a encaminhar o comprovante de pagamento ao {_LOCADOR} "
        "no dia do pagamento, valendo o mesmo como recibo.",
    )

    clausula(7, "DA QUANTIA CAUÇÃO")
    caucao = Decimal(str(contrato.get("caucao_valor") or 0))
    if caucao > 0:
        item(
            "7.1.",
            "Estabelecem as partes, a QUANTIA CAUÇÃO no valor total de "
            f"{_r(caucao)}, pago na forma acordada entre as partes.",
        )
    else:
        item("7.1.", "As partes ajustam que não haverá QUANTIA CAUÇÃO neste contrato.")
    item(
        "7.2.",
        f"Ao término da vigência do presente contrato caberá ao {_LOCADOR} restituir a "
        f"integralidade da QUANTIA CAUÇÃO ao {_LOCATARIO} no prazo de "
        f"{t['caucao_devolucao_dias_uteis']:02d} dias úteis a contar da devolução do veículo por "
        f"parte do {_LOCATARIO}, conforme as seguintes CONDIÇÕES: (a) a devolução do veículo em "
        "perfeito estado, em condição equivalente à observada no último checklist de vistoria e "
        f"após vistoria feita por vídeo enviada para o WhatsApp do {_LOCADOR}; (b) a inexistência "
        f"de aluguéis, multas de trânsito ou multas por descumprimento contratual pendentes por "
        f"parte do {_LOCATARIO}, após feita a manutenção necessária do veículo, caso haja "
        "necessidade; (c) após descontados quaisquer outros débitos pendentes.",
    )
    item(
        "7.3.",
        f"Na hipótese de não estarem observadas as condições acima dispostas, poderá o "
        f"{_LOCADOR} utilizar-se da QUANTIA CAUÇÃO para adimplir eventuais débitos ou reparar "
        "danos causados ao veículo que não decorram do desgaste natural e utilização adequada "
        f"do bem, hipótese na qual só será de direito do {_LOCATARIO} a quantia remanescente a "
        "tal utilização da QUANTIA CAUÇÃO, se houver.",
    )
    item(
        "7.4.",
        f"Os gastos com o combustível do veículo deverão ser arcados integralmente pelo "
        f"{_LOCATARIO}, devendo sempre devolver o veículo com a mesma quantidade de combustível "
        f"contida no veículo quando da entrega do mesmo pelo {_LOCADOR}, sob pena de desconto na "
        "QUANTIA CAUÇÃO do valor necessário a atingir tal quantidade de combustível.",
    )
    item(
        "7.5.",
        "Qualquer valor inerente a cobrança por passagem, estacionamento ou pedágio do veículo "
        f"durante a posse do {_LOCATARIO} deverá por este ser arcado. Caso o {_LOCADOR} seja "
        f"cobrado por qualquer valor desta natureza, o {_LOCATARIO} deverá reembolsá-lo "
        "imediatamente.",
    )
    item(
        "7.6.",
        "Caso o veículo seja devolvido sujo, será cobrada a lavagem simples "
        f"({_moeda(t['lavagem_simples'])}) ou especial ({_moeda(t['lavagem_especial'])}), "
        "dependendo do seu estado. Na hipótese de lavagem especial será cobrada também 1 "
        "diária de locação ou quantas forem necessárias até a disponibilização do veículo, "
        f"limitadas a {t['lavagem_especial_max_diarias']} diárias.",
    )
    item(
        "7.7.",
        "Quando o documento do veículo não for devolvido, será cobrado o reembolso das despesas "
        "para obtenção de 2ª via e, diante da impossibilidade de o veículo ser alugado, as "
        "diárias correspondentes.",
    )

    clausula(8, "DA VIGÊNCIA E RESCISÃO")
    item(
        "8.1.",
        f"O presente contrato se inicia em {_data(inicio)}{prazo_final}, com prazo mínimo de "
        f"{t['prazo_minimo_dias']} dias de locação, após esse prazo a vigência é "
        "indeterminada, salvo manifestação de qualquer das partes em contrário, motivada por "
        "resilição ou descumprimento contratual ocasionado pela parte contrária.",
    )
    subitem(
        "8.1.1.",
        f"Em caso de devolução antecipada o {_LOCATARIO} pagará uma multa no valor de "
        f"{t['devolucao_antecipada_percentual']}% das diárias canceladas, sem que recaiam "
        f"quaisquer ônus ao {_LOCADOR}.",
    )
    item(
        "8.2.",
        "É assegurado às partes a resilição do presente CONTRATO a qualquer tempo, bastando, "
        f"para tanto, dar ciência a outra parte, cabendo ao {_LOCATARIO} a devolução do veículo "
        f"ao {_LOCADOR} em local designado por este no seguinte prazo: (a) 24 horas a contar da "
        f"comunicação ao {_LOCADOR}, no caso em que o {_LOCATARIO} resilir o presente contrato; "
        "(b) 24 horas a contar do momento em que teve ciência da resilição, quando realizada "
        f"pelo {_LOCADOR}.",
    )
    item(
        "8.3.",
        f"O contrato poderá ser considerado rescindido de pleno direito pelo {_LOCADOR}, "
        "independentemente de qualquer notificação, e este, sem mais formalidades, "
        f"providenciará a retomada do veículo, sem que isso enseje ao {_LOCATARIO} qualquer "
        "direito de retenção, indenização ou devolução da quantia caução, quando:",
    )
    subitem("8.3.1.", "O veículo não for devolvido na data, hora e local previamente ajustados;")
    subitem("8.3.2.", "Ocorrer o uso inadequado do veículo;")
    subitem("8.3.3.", "Ocorrer apreensão do veículo locado por autoridades competentes;")
    subitem("8.3.4.", f"O {_LOCATARIO} não quitar seus débitos nos respectivos vencimentos;")
    subitem(
        "8.3.5.",
        f"O {_LOCATARIO} acumular uma dívida superior a {_r(t['divida_limite_retomada'])} e não "
        "a quite imediatamente, caso no qual o veículo deverá ser entregue em local "
        f"determinado pelo {_LOCADOR}, imediatamente, sob pena de multa de "
        f"{_r(t['multa_retomada_por_dia'])} por dia, salvo acordo contrário entre as partes.",
    )
    item(
        "8.4.",
        "Fica desde já pactuada a total inexistência de vínculo trabalhista entre as partes do "
        "presente contrato, sendo indevida toda e qualquer incidência das obrigações "
        "previdenciárias e os encargos sociais, não havendo entre as partes qualquer tipo de "
        "subordinação e controle típicos de relações de emprego.",
    )
    item(
        "8.5.",
        "Nos termos do artigo 265 do Código Civil Brasileiro, inexiste solidariedade, seja "
        f"contratual ou legal entre o {_LOCADOR} e o {_LOCATARIO}, razão pela qual, com a "
        f"locação e a efetiva retirada do veículo alugado, o {_LOCATARIO} assume sua posse "
        "autônoma para todos os fins de direito, responsabilizando-se por eventuais "
        "indenizações decorrentes do uso e circulação do veículo, cuja responsabilidade "
        "perdurará até a efetiva devolução do veículo alugado.",
    )

    clausula(9, "DA DEVOLUÇÃO DO VEÍCULO")
    item(
        "9.1.",
        "Ao término do contrato, o veículo deve ser devolvido em local, dia e hora indicado "
        f"pelo {_LOCADOR}, sob pena de multa de {_r(t['multa_devolucao_por_dia'])} por dia.",
    )
    item(
        "9.2.",
        f"A não devolução de veículo pelo {_LOCATARIO}, após notificação realizada pelo "
        f"{_LOCADOR}, configura crime de APROPRIAÇÃO INDÉBITA conforme artigo 168 do Código "
        "Penal Brasileiro, com pena de reclusão de um a quatro anos de prisão e multa.",
    )

    clausula(10, "DAS DISPOSIÇÕES GERAIS")
    item(
        "10.1.",
        "Quaisquer notificações e comunicações enviadas sob esse contrato podem ser realizadas "
        "de forma eletrônica (e-mail ou WhatsApp), escritas ou por correspondência com aviso "
        "de recebimento aos endereços constantes do preâmbulo. Em havendo alteração do "
        "endereço ficam as partes obrigadas a fornecerem tal informação.",
    )
    item(
        "10.2.",
        "Todos os valores, despesas e encargos da locação constituem dívidas líquidas e certas "
        "para pagamento à vista, passíveis de cobrança executiva.",
    )
    item(
        "10.3.",
        f"Eventuais tolerâncias do {_LOCADOR} para com o {_LOCATARIO} no cumprimento das "
        "obrigações ajustadas neste contrato constituem mera liberalidade, não importando em "
        "hipótese alguma em novação ou renúncia, permanecendo íntegras as cláusulas e "
        "condições aqui contratadas.",
    )
    item(
        "10.4.",
        f"O {_LOCATARIO} autoriza o {_LOCADOR} a coletar, usar e divulgar a sua imagem para "
        "fins de cadastro, defesa e/ou promoção.",
    )
    item(
        "10.5.",
        f"O {_LOCATARIO} concorda que a sua assinatura no contrato implica ciência e adesão "
        "por si, seus herdeiros/sucessores a estas cláusulas.",
    )
    item(
        "10.6.",
        f"Fica eleito o foro da cidade e Comarca de {foro}, como competente para dirimir "
        "quaisquer questões que possam advir da aplicação do presente CONTRATO, por mais "
        "privilegiado que seja ou venha a ser, qualquer Foro.",
    )
    item(
        "10.7.",
        "E, por estarem assim, justas e contratadas, as partes firmam o presente instrumento "
        "em 02 (duas) vias de igual teor e forma, para que produza seus efeitos legais, após "
        "ter lido o seu conteúdo, ter sido claramente entendido e aceito.",
    )

    b.append(
        Bloco("fecho", "", f"{cidade}, {data_por_extenso(inicio).upper()}.")
    )
    b.append(Bloco("assinatura", "", _v(locador.get("nome"), "LOCADOR")))
    b.append(Bloco("assinatura", "", _v(cliente.get("nome"), "LOCATÁRIO").upper()))
    return b
