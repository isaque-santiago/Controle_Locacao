"""Leitura do histórico exportado do claude.ai («Configurações > Privacidade > Exportar dados», arquivo `conversations.json`).

O Claude dentro de um chat só enxerga a parte recente (o resto vira resumo), então o histórico antigo vem da exportação oficial, que traz
cada mensagem com data e hora. Estas funções puras escolhem as conversas pelo título e as transformam em texto datado, para uma sessão de
sincronização ler. O formato do arquivo não é documentado em detalhe: a leitura aceita o texto direto da mensagem ou os blocos de
conteúdo, e ignora o que não conhecer."""

import re
import unicodedata
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

_FUSO = ZoneInfo("America/Sao_Paulo")
_AUTOR = {"human": "Você", "user": "Você", "assistant": "Claude"}


def _simplificar(texto) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def _data(texto) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")).astimezone(_FUSO)
    except (TypeError, ValueError):
        return None


def texto_da_mensagem(mensagem: dict) -> str:
    """O texto da mensagem: o campo `text`, ou os blocos de conteúdo do tipo texto; anexos aparecem como «[anexo: nome]»."""
    partes = []
    bruto = mensagem.get("text")
    if isinstance(bruto, str) and bruto.strip():
        partes.append(bruto.strip())
    else:
        for bloco in mensagem.get("content") or []:
            if isinstance(bloco, dict) and isinstance(bloco.get("text"), str) and bloco["text"].strip():
                partes.append(bloco["text"].strip())
    for chave in ("attachments", "files"):
        for anexo in mensagem.get(chave) or []:
            nome = anexo.get("file_name") or anexo.get("name") if isinstance(anexo, dict) else None
            if nome:
                partes.append(f"[anexo: {nome}]")
    return "\n".join(partes)


def mensagens_da_conversa(conversa: dict) -> list[dict]:
    """[{"data": datetime, "autor": "Você"|"Claude", "texto": str}] em ordem cronológica, sem as mensagens vazias."""
    saida = []
    for m in conversa.get("chat_messages") or conversa.get("messages") or []:
        if not isinstance(m, dict):
            continue
        texto = texto_da_mensagem(m)
        if texto:
            saida.append({"data": _data(m.get("created_at")), "autor": _AUTOR.get(str(m.get("sender") or m.get("role")), "Outro"), "texto": texto})
    return sorted(saida, key=lambda x: (x["data"] is None, x["data"] or datetime.min.replace(tzinfo=_FUSO)))


def conversas_do_titulo(dados, titulos: list[str]) -> list[dict]:
    """Conversas cujo nome contém algum dos títulos (sem diferenciar maiúsculas nem acentos)."""
    lista = dados if isinstance(dados, list) else (dados.get("conversations") if isinstance(dados, dict) else None) or []
    buscas = [_simplificar(t) for t in titulos if _simplificar(t)]
    return [c for c in lista if isinstance(c, dict) and any(b in _simplificar(c.get("name") or c.get("title")) for b in buscas)]


def resumo_da_conversa(conversa: dict) -> dict:
    """{"nome", "mensagens", "primeira", "ultima", "por_mes": {"2026-10": n}} para conferir a cobertura antes de usar."""
    mensagens = mensagens_da_conversa(conversa)
    datas = [m["data"] for m in mensagens if m["data"]]
    return {"nome": conversa.get("name") or conversa.get("title") or "(sem nome)", "mensagens": len(mensagens),
            "primeira": min(datas) if datas else None, "ultima": max(datas) if datas else None,
            "por_mes": dict(sorted(Counter(d.strftime("%Y-%m") for d in datas).items()))}


def markdown_da_conversa(conversa: dict) -> str:
    resumo = resumo_da_conversa(conversa)
    linhas = [f"# {resumo['nome']}", "", f"Mensagens: {resumo['mensagens']}"]
    if resumo["primeira"]:
        linhas.append(f"Período: {resumo['primeira']:%d/%m/%Y %H:%M} a {resumo['ultima']:%d/%m/%Y %H:%M} (horário de Brasília)")
    linhas.append("")
    for m in mensagens_da_conversa(conversa):
        quando = f"{m['data']:%d/%m/%Y %H:%M}" if m["data"] else "sem data"
        linhas += [f"## [{quando}] {m['autor']}", "", m["texto"], ""]
    return "\n".join(linhas)


def nome_do_arquivo(nome: str, indice: int = 1) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", _simplificar(nome)).strip("-")[:60] or "conversa"
    return f"{indice:02d}-{base}.md"
