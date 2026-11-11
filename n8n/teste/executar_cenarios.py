"""Executa o fluxo n8n/enviar-mensagens-whatsapp.json NUM N8N DE VERDADE, contra um servidor falso do Supabase e da Evolution, em
cada cenário importante, e confere as chamadas que o fluxo fez. Use depois de editar o fluxo no n8n (e exporte o JSON de volta).

Pré-requisito (uma vez, fora do repositório; baixa ~3 GB): numa pasta qualquer, `npm init -y && npm i n8n`. Depois, na raiz do projeto:

    python n8n/teste/executar_cenarios.py --n8n-dir /caminho/da/pasta/onde/instalou
    python n8n/teste/executar_cenarios.py --n8n-dir ... sucesso limite_429     # só alguns cenários

Nada é gravado no repositório nem em ~/.n8n: o n8n usa uma pasta temporária (apagada ao fim) e credenciais fictícias.
A pausa entre mensagens vai para 0 s (menos no cenário de pausa) para o teste ser rápido."""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FLUXO = RAIZ / "n8n" / "enviar-mensagens-whatsapp.json"
SERVIDOR = Path(__file__).with_name("servidor_falso.cjs")
ID_DO_FLUXO = "wfTesteWhatsapp1"


class Ambiente:
    def __init__(self, n8n_dir: Path, porta: int):
        self.n8n_dir, self.porta = n8n_dir, porta
        self.tmp = Path(tempfile.mkdtemp(prefix="n8n-teste-"))
        self.log = self.tmp / "chamadas.jsonl"
        self.env = dict(os.environ, N8N_USER_FOLDER=str(self.tmp / "dados"), N8N_ENCRYPTION_KEY="chave-de-teste-nao-usar",
                        N8N_DIAGNOSTICS_ENABLED="false", N8N_VERSION_NOTIFICATIONS_ENABLED="false",
                        N8N_PERSONALIZATION_ENABLED="false", N8N_RUNNERS_ENABLED="true")
        self.n8n = str(n8n_dir / "node_modules" / ".bin" / "n8n")
        self.servidor = None

    def iniciar(self):
        if not Path(self.n8n).exists():
            sys.exit(f"n8n não encontrado em {self.n8n}. Rode `npm i n8n` nessa pasta (veja o topo deste arquivo).")
        self.servidor = subprocess.Popen(["node", str(SERVIDOR), str(self.porta), str(self.log)], stdout=subprocess.DEVNULL)
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", self.porta), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        credenciais = [
            {"id": "SUPABASE_ANON", "name": "Supabase — chave anônima (apikey)", "type": "httpHeaderAuth",
             "data": {"name": "apikey", "value": "anon-teste"}},
            {"id": "EVOLUTION_APIKEY", "name": "Evolution — apikey", "type": "httpHeaderAuth",
             "data": {"name": "apikey", "value": "evo-teste"}},
            {"id": "SUPABASE_LOGIN", "name": "Supabase — usuário de serviço (login)", "type": "httpCustomAuth",
             "data": {"json": json.dumps({"headers": {"apikey": "anon-teste"}, "body": {"email": "robo@exemplo.com", "password": "senha-robo"}})}},
        ]
        arquivo = self.tmp / "credenciais.json"
        arquivo.write_text(json.dumps(credenciais), encoding="utf-8")
        self._n8n("import:credentials", f"--input={arquivo}")

    def encerrar(self):
        if self.servidor:
            self.servidor.terminate()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _n8n(self, *args, timeout=170):
        return subprocess.run([self.n8n, *args], env=self.env, cwd=self.n8n_dir, capture_output=True, text=True, timeout=timeout)

    def preparar_fluxo(self, config=None):
        """Importa uma cópia do fluxo apontando para o servidor falso (o arquivo do repositório não é alterado)."""
        fluxo = json.loads(FLUXO.read_text(encoding="utf-8"))
        url = f"http://127.0.0.1:{self.porta}"
        for n in fluxo["nodes"]:
            if n["name"] == "Configuração":
                for a in n["parameters"]["assignments"]["assignments"]:
                    if a["name"] in ("supabase_url", "evolution_url"):
                        a["value"] = url
                    if a["name"] == "evolution_instancia":
                        a["value"] = "locacao"
                    if a["name"] in ("pausa_minima_s", "pausa_maxima_s"):
                        a["value"] = 0
                    if config and a["name"] in config:
                        a["value"] = config[a["name"]]
            if n["name"] == "Agendamento":  # o CLI do n8n só executa fluxos com este gatilho
                n["type"], n["typeVersion"], n["parameters"] = "n8n-nodes-base.executeWorkflowTrigger", 1.1, {"inputSource": "passthrough"}
        fluxo["id"] = ID_DO_FLUXO
        arquivo = self.tmp / "fluxo-teste.json"
        arquivo.write_text(json.dumps([fluxo], ensure_ascii=False), encoding="utf-8")
        self._n8n("import:workflow", f"--input={arquivo}")

    def cenario(self, **kw):
        base = {"estado": "open", "reservar": [], "numeros": {}, "envio": {}, "reservarStatus": 200, "loginStatus": 200}
        base.update(kw)
        pedido = urllib.request.Request(f"http://127.0.0.1:{self.porta}/_cenario", data=json.dumps(base).encode(), method="POST")
        urllib.request.urlopen(pedido).read()

    def executar(self, config=None):
        if config is not None:
            self.preparar_fluxo(config)
        self.log.unlink(missing_ok=True)
        inicio = time.time()
        r = self._n8n("execute", f"--id={ID_DO_FLUXO}", timeout=150)
        saida = r.stdout + r.stderr
        status = "success" if '"status": "success"' in saida else ("error" if "Error executing workflow" in saida else "?")
        chamadas = [json.loads(linha) for linha in self.log.read_text().splitlines()] if self.log.exists() else []
        return status, chamadas, time.time() - inicio


def msg(i, **extra):
    n = f"55119000000{i:02d}"
    return {"id": f"m{i}", "cliente_id": "c", "numero": n, "texto": f"Texto {i}", "tentativas": 0, "modo_teste": False,
            "numero_envio": n, "texto_envio": f"Texto {i}", **extra}


def so(chamadas, trecho):
    return [c for c in chamadas if trecho in c["caminho"]]


def resultados(chamadas):
    return [(c["corpo"]["p_id"], c["corpo"]["p_resultado"], c["corpo"]["p_erro"], c["corpo"]["p_evolution_id"]) for c in so(chamadas, "registrar_resultado")]


def rodadas(chamadas):
    return [c["corpo"] for c in so(chamadas, "registrar_rodada")]


def envios(chamadas):
    return [c["corpo"] for c in so(chamadas, "sendText")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n8n-dir", required=True, type=Path)
    ap.add_argument("--porta", type=int, default=8099)
    ap.add_argument("cenarios", nargs="*")
    args = ap.parse_args()
    amb = Ambiente(args.n8n_dir, args.porta)
    falhas = []

    def conferir(nome, condicao, detalhe=""):
        print(("PASSOU " if condicao else "FALHOU ") + nome + ("" if condicao else f"  -> {detalhe}"))
        if not condicao:
            falhas.append(nome)

    def rodar(nome):
        return not args.cenarios or nome in args.cenarios

    try:
        amb.iniciar()
        amb.preparar_fluxo({})

        if rodar("sucesso"):
            amb.cenario(reservar=[msg(1), msg(2)])
            st, c, _ = amb.executar()
            conferir("sucesso: duas mensagens enviadas e registradas",
                     st == "success" and resultados(c) == [("m1", "enviada", None, "EVO-0001"), ("m2", "enviada", None, "EVO-0002")], (st, resultados(c)))
            conferir("sucesso: heartbeat da rodada com estado open e 2 reservadas",
                     rodadas(c) == [{"p_estado": "open", "p_resumo": {"executor": "n8n", "reservadas": 2}}], rodadas(c))
            conferir("sucesso: envia o que o banco resolveu (v2: number, text, delay)",
                     envios(c)[0] == {"number": "5511900000001", "text": "Texto 1", "delay": 1200}, envios(c))
            conferir("sucesso: o token e a apikey vão em toda RPC",
                     all(x.get("auth") == "Bearer tok-servico" and x.get("apikey") == "anon-teste" for x in so(c, "/rest/v1/rpc/")))

        if rodar("numero_sem_whatsapp"):
            amb.cenario(reservar=[msg(1), msg(2)], numeros={"5511900000001": {"status": 200, "exists": False}})
            st, c, _ = amb.executar()
            conferir("sem WhatsApp: m1 ignorada e m2 enviada",
                     resultados(c) == [("m1", "ignorada", "O número não tem WhatsApp.", None), ("m2", "enviada", None, "EVO-0002")], resultados(c))
            conferir("sem WhatsApp: não tenta enviar para o número que não tem", [e["number"] for e in envios(c)] == ["5511900000002"], envios(c))

        if rodar("recusa_da_mensagem"):
            amb.cenario(reservar=[msg(1), msg(2)], envio={"5511900000001": {"status": 400}})
            st, c, _ = amb.executar()
            conferir("400 no envio: falha só da mensagem e segue",
                     resultados(c) == [("m1", "falhou", "A Evolution recusou o pedido (400).", None), ("m2", "enviada", None, "EVO-0002")], resultados(c))

        if rodar("limite_429"):
            amb.cenario(reservar=[msg(1), msg(2), msg(3)], envio={"5511900000002": {"status": 429}})
            st, c, _ = amb.executar()
            conferir("429: m1 enviada, m2 volta para a fila e o fluxo PARA",
                     resultados(c) == [("m1", "enviada", None, "EVO-0001"), ("m2", "falhou", "A Evolution pediu para tentar depois (429).", None)], resultados(c))
            conferir("429: m3 nem é tentada", "5511900000003" not in json.dumps([x["corpo"] for x in c]), [x["caminho"] for x in c])

        if rodar("erro_500_na_consulta"):
            amb.cenario(reservar=[msg(1), msg(2)], numeros={"5511900000001": {"status": 500}})
            st, c, _ = amb.executar()
            conferir("500 ao conferir o número: falha registrada e PARA", resultados(c) == [("m1", "falhou", "A Evolution respondeu 500.", None)], resultados(c))

        if rodar("chave_recusada"):
            amb.cenario(reservar=[msg(1), msg(2)], numeros={"5511900000001": {"status": 401}})
            st, c, _ = amb.executar()
            conferir("401 da Evolution: NÃO registra nada (a reserva vence sozinha) e PARA", resultados(c) == [] and not envios(c), (resultados(c), envios(c)))

        if rodar("instancia_fechada"):
            amb.cenario(estado="close", reservar=[msg(1)])
            st, c, _ = amb.executar()
            conferir("instância close: só o heartbeat, sem reservar nem enviar",
                     rodadas(c) == [{"p_estado": "close", "p_resumo": {"executor": "n8n", "parou_por": "instancia_nao_aberta"}}]
                     and not so(c, "reservar") and not envios(c), (rodadas(c), [x["caminho"] for x in c]))

        if rodar("estado_500"):
            amb.cenario(estado="http500", reservar=[msg(1)])
            st, c, _ = amb.executar()
            conferir("estado 500: registra indisponivel e não reserva", [r["p_estado"] for r in rodadas(c)] == ["indisponivel"] and not so(c, "reservar"), rodadas(c))

        if rodar("estado_401"):
            amb.cenario(estado="http401", reservar=[msg(1)])
            st, c, _ = amb.executar()
            conferir("estado 401: registra config_invalida e não reserva", [r["p_estado"] for r in rodadas(c)] == ["config_invalida"] and not so(c, "reservar"), rodadas(c))

        if rodar("fila_vazia"):
            amb.cenario(reservar=[])
            st, c, _ = amb.executar()
            conferir("fila vazia (portão fechado ou nada devido): heartbeat e nada mais",
                     st == "success" and rodadas(c) == [{"p_estado": "open", "p_resumo": {"executor": "n8n", "reservadas": 0}}] and not envios(c), (st, rodadas(c)))

        if rodar("reservar_recusada"):
            amb.cenario(reservarStatus=401, reservar={"message": "JWT inválido"})
            st, c, _ = amb.executar()
            conferir("reservar recusada (401): a execução FALHA (aparece no n8n) e nada é enviado nem registrado",
                     st == "error" and not envios(c) and not so(c, "registrar"), (st, [x["caminho"] for x in c]))

        if rodar("login_recusado"):
            amb.cenario(loginStatus=400)
            st, c, _ = amb.executar()
            conferir("login recusado: a execução FALHA e nada além do login é chamado",
                     st == "error" and [x["caminho"] for x in c] == ["/auth/v1/token"], (st, [x["caminho"] for x in c]))

        if rodar("modo_teste"):
            m = msg(1, modo_teste=True, numero_envio="5511977776666", texto_envio="[TESTE] Esta mensagem iria para 55119****0001.\n\nTexto 1")
            amb.cenario(reservar=[m])
            st, c, _ = amb.executar()
            conferir("modo teste: envia o número e o texto resolvidos pelo banco",
                     envios(c) == [{"number": "5511977776666", "text": m["texto_envio"], "delay": 1200}], envios(c))

        if rodar("evolution_v1"):
            amb.cenario(reservar=[msg(1)])
            st, c, _ = amb.executar(config={"evolution_versao": 1})
            conferir("Evolution v1: corpo com textMessage",
                     envios(c) == [{"number": "5511900000001", "options": {"delay": 1200, "presence": "composing"}, "textMessage": {"text": "Texto 1"}}], envios(c))
            amb.preparar_fluxo({})

        if rodar("pausa"):
            amb.cenario(reservar=[msg(1), msg(2), msg(3)])
            st, c, duracao = amb.executar(config={"pausa_minima_s": 3, "pausa_maxima_s": 3})
            conferir("pausa: 3 mensagens enviadas com 2 pausas de 3 s (nenhuma antes da primeira)", st == "success" and len(envios(c)) == 3, (st, len(envios(c))))
            conferir("pausa: a duração total inclui as 2 pausas", duracao >= 6, duracao)
            amb.preparar_fluxo({})
    finally:
        amb.encerrar()

    print("\nRESULTADO:", "tudo certo" if not falhas else f"{len(falhas)} verificação(ões) falharam: {falhas}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
