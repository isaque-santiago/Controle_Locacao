"""Transforma o histórico exportado do claude.ai em texto datado, só das conversas escolhidas, para a sessão de sincronização ler.

    python scripts/extrair_chat_exportado.py EXPORTACAO.zip PASTA_DE_SAIDA --titulo "Acompanhamento Financeiro" --titulo "Contratos Locadora"

EXPORTACAO é o `.zip` (ou o `conversations.json`) que o claude.ai manda por e-mail em «Configurações > Privacidade > Exportar dados».
A PASTA_DE_SAIDA precisa ficar **fora do repositório**: as conversas têm CPF, telefone e valores reais. O script se recusa a escrever dentro dele.
Escreve um `.md` por conversa e um `indice.txt` com o período e a quantidade de mensagens por mês (para conferir a cobertura)."""

import argparse
import json
import sys
from pathlib import Path
from zipfile import ZipFile

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.domain.chat_exportado import conversas_do_titulo, markdown_da_conversa, nome_do_arquivo, resumo_da_conversa  # noqa: E402


def ler_conversas(caminho: Path):
    if caminho.suffix.lower() == ".zip":
        with ZipFile(caminho) as zip_:
            nomes = [n for n in zip_.namelist() if n.lower().endswith("conversations.json")]
            if not nomes:
                raise SystemExit("O zip não tem conversations.json.")
            return json.loads(zip_.read(nomes[0]).decode("utf-8"))
    return json.loads(caminho.read_text(encoding="utf-8"))


def dentro_do_repositorio(pasta: Path) -> bool:
    return RAIZ == pasta.resolve() or RAIZ in pasta.resolve().parents


def principal(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("exportacao", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--titulo", action="append", required=True, help="parte do nome da conversa (pode repetir)")
    args = ap.parse_args(argv)
    if dentro_do_repositorio(args.saida):
        print("Recuso: a pasta de saída está dentro do repositório. Use uma pasta fora dele (as conversas têm dados pessoais).", file=sys.stderr)
        return 2
    if not args.exportacao.exists():
        print(f"Não achei {args.exportacao}.", file=sys.stderr)
        return 2
    conversas = conversas_do_titulo(ler_conversas(args.exportacao), args.titulo)
    if not conversas:
        print("Nenhuma conversa tem esse título.", file=sys.stderr)
        return 1
    args.saida.mkdir(parents=True, exist_ok=True)
    indice = []
    for i, conversa in enumerate(conversas, start=1):
        arquivo = args.saida / nome_do_arquivo(conversa.get("name") or conversa.get("title") or "", i)
        arquivo.write_text(markdown_da_conversa(conversa), encoding="utf-8")
        r = resumo_da_conversa(conversa)
        periodo = f"{r['primeira']:%d/%m/%Y} a {r['ultima']:%d/%m/%Y}" if r["primeira"] else "sem datas"
        indice.append(f"{arquivo.name}: {r['nome']} | {r['mensagens']} mensagens | {periodo}\n  por mês: " + ", ".join(f"{m}={n}" for m, n in r["por_mes"].items()))
    (args.saida / "indice.txt").write_text("\n".join(indice) + "\n", encoding="utf-8")
    print("\n".join(indice))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
