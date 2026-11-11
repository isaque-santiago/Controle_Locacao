"""Testes estáticos do fluxo do n8n (n8n/enviar-mensagens-whatsapp.json): o fluxo não passa pelo pytest como código, então o que
dá para garantir sem rodá-lo é conferido aqui: nomes, ligações, RPCs que existem no banco, tempos que cabem na reserva e
ausência de segredos."""

import json
import re
from pathlib import Path

import pytest

from src.services import whatsapp

RAIZ = Path(__file__).resolve().parents[1]
FLUXO = json.loads((RAIZ / "n8n" / "enviar-mensagens-whatsapp.json").read_text(encoding="utf-8"))
TEXTO = json.dumps(FLUXO, ensure_ascii=False)
NOS = {n["name"]: n for n in FLUXO["nodes"]}


def _migrations() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((RAIZ / "supabase" / "migrations").glob("*.sql")))


def test_nomes_unicos_e_ligacoes_apontam_para_nos_que_existem():
    assert len(NOS) == len(FLUXO["nodes"])
    for origem, saidas in FLUXO["connections"].items():
        assert origem in NOS, origem
        for grupo in saidas["main"]:
            for destino in grupo:
                assert destino["node"] in NOS, f"{origem} -> {destino['node']}"


def test_todo_no_e_alcancavel_a_partir_do_agendamento():
    visitados, fila = set(), ["Agendamento"]
    while fila:
        atual = fila.pop()
        if atual in visitados:
            continue
        visitados.add(atual)
        for grupo in FLUXO["connections"].get(atual, {}).get("main", []):
            fila.extend(d["node"] for d in grupo)
    assert visitados == set(NOS)


def test_as_rpcs_chamadas_existem_nas_migrations():
    chamadas = set(re.findall(r"rest/v1/rpc/(rpc_\w+)", TEXTO))
    assert chamadas == {"rpc_whatsapp_reservar", "rpc_whatsapp_registrar_resultado", "rpc_whatsapp_registrar_rodada"}
    sql = _migrations()
    for nome in chamadas:
        assert re.search(rf"create or replace function {nome}\(", sql), nome


def test_os_endpoints_da_evolution_sao_os_do_cliente_python():
    codigo = (RAIZ / "src" / "services" / "evolution.py").read_text(encoding="utf-8")
    for caminho in ("/instance/connectionState/", "/chat/whatsappNumbers/", "/message/sendText/"):
        assert caminho in codigo and caminho in TEXTO


def test_configuracao_do_fluxo_bate_com_o_servico_python():
    valores = {a["name"]: a["value"] for a in NOS["Configuração"]["parameters"]["assignments"]["assignments"]}
    assert valores["lote"] == whatsapp.LOTE
    assert (valores["pausa_minima_s"], valores["pausa_maxima_s"]) == (whatsapp.PAUSA_MINIMA, whatsapp.PAUSA_MAXIMA)


def test_o_fluxo_cabe_na_reserva_do_banco():
    """O tempo limite do fluxo e o de cada chamada seguem a mesma conta do servidor Python (reserva de 10 minutos no banco)."""
    assert FLUXO["settings"]["executionTimeout"] <= whatsapp.RESERVA_SEGUNDOS - whatsapp.MARGEM_SEGUNDOS
    tempos = [n["parameters"]["options"]["timeout"] for n in FLUXO["nodes"] if n["type"] == "n8n-nodes-base.httpRequest"]
    assert tempos and all(t == whatsapp.TIMEOUT_CHAMADA_SEGUNDOS * 1000 for t in tempos)
    valores = {a["name"]: a["value"] for a in NOS["Configuração"]["parameters"]["assignments"]["assignments"]}
    pior = (valores["lote"] - 1) * valores["pausa_maxima_s"] + valores["lote"] * 2 * whatsapp.TIMEOUT_CHAMADA_SEGUNDOS
    assert pior <= FLUXO["settings"]["executionTimeout"]


def test_fuso_de_brasilia_e_agendamento_a_cada_5_minutos_e_fluxo_inativo_por_padrao():
    assert FLUXO["settings"]["timezone"] == "America/Sao_Paulo"
    assert NOS["Agendamento"]["parameters"]["rule"]["interval"] == [{"field": "minutes", "minutesInterval": 5}]
    assert FLUXO["active"] is False


def test_dados_pessoais_nao_ficam_guardados_nas_execucoes_com_sucesso():
    assert FLUXO["settings"]["saveDataSuccessExecution"] == "none" and FLUXO["settings"]["saveManualExecutions"] is False


@pytest.mark.parametrize("proibido", ["service_role", "sb_secret", "eyJ", "supabase.co/rest/v1/clientes", "password\":", "\"apikey\":"])
def test_sem_segredos_nem_service_role_no_arquivo(proibido):
    assert proibido not in TEXTO


def test_credenciais_so_por_referencia_e_os_enderecos_sao_modelos():
    credenciais = [c for n in FLUXO["nodes"] for tipo in n.get("credentials", {}).values() for c in [tipo]]
    assert credenciais and all(set(c) == {"id", "name"} for c in credenciais)
    valores = {a["name"]: a["value"] for a in NOS["Configuração"]["parameters"]["assignments"]["assignments"]}
    assert "SEU-PROJETO" in valores["supabase_url"] and "SEU-DOMINIO" in valores["evolution_url"]


def test_classificacao_de_erros_igual_a_do_cliente_python():
    codigo = NOS["Avaliar envio"]["parameters"]["jsCode"]
    for esperado in ("408", "429", "401, 403, 404", "r.statusCode >= 500", "r.statusCode >= 400"):
        assert esperado in codigo


def test_so_para_sem_registrar_quando_a_evolution_recusa_a_chave():
    """Chave ou instância inválida não registra falha na mensagem: a reserva vence sozinha (igual ao script Python)."""
    codigo = NOS["Avaliar número"]["parameters"]["jsCode"]
    assert "parar_sem_registro" in codigo
    assert "Parar: configuração da Evolution" in NOS and NOS["Parar: configuração da Evolution"]["type"] == "n8n-nodes-base.noOp"
