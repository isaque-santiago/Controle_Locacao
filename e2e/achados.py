"""Coletor de achados de UI/UX: registra o que a suíte encontra, sem derrubar o teste.

Na Etapa 0 a suíte mede a linha de base; por isso os problemas viram achados (Markdown
+ JSON em e2e/resultados/) e só reprovam o teste com --e2e-estrito."""

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

PASTA_RESULTADOS = Path(__file__).parent / "resultados"

SEVERIDADES = ("P0", "P1", "P2", "INFO")


@dataclass(frozen=True)
class Achado:
    severidade: str
    tipo: str
    pagina: str
    descricao: str
    elemento: str = ""
    detalhe: str = ""  # medidas observadas (não entram no agrupamento)
    # Contexto de reprodução
    perfil: str = ""
    largura: int = 0
    altura: int = 0
    tema: str = ""
    dados: str = ""
    fluxo: str = ""


@dataclass
class Coletor:
    achados: list[Achado] = field(default_factory=list)

    def registrar(self, achado: Achado) -> None:
        self.achados.append(achado)

    def da_severidade(self, *severidades: str) -> list[Achado]:
        return [a for a in self.achados if a.severidade in severidades]

    def gravar(self) -> None:
        if not self.achados:
            return
        PASTA_RESULTADOS.mkdir(exist_ok=True)
        (PASTA_RESULTADOS / "achados.json").write_text(
            json.dumps([asdict(a) for a in self.achados], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (PASTA_RESULTADOS / "achados.md").write_text(self._markdown(), encoding="utf-8")

    def _markdown(self) -> str:
        # Agrupa ocorrências iguais em vários viewports/temas em uma única linha.
        grupos: dict[tuple, list[Achado]] = defaultdict(list)
        for a in self.achados:
            grupos[(a.severidade, a.pagina, a.tipo, a.descricao, a.elemento)].append(a)

        linhas = [
            "# Achados de UI/UX (gerado pela suíte e2e)",
            "",
            f"Gerado em {datetime.now():%d/%m/%Y %H:%M}. Arquivo gerado: não edite; "
            "copie o que for tratado para `Arquivos/Achados_UI_UX.md`. "
            "O detalhe por ocorrência está em `achados.json`.",
            "",
        ]
        for sev in SEVERIDADES:
            do_nivel = sorted(
                (chave for chave in grupos if chave[0] == sev),
                key=lambda c: (c[1], c[2], c[4]),
            )
            if not do_nivel:
                continue
            linhas += [
                f"## {sev} ({len(do_nivel)})",
                "",
                "| Página | Tipo | Achado | Elemento | Medidas | Onde reproduzir |",
                "|---|---|---|---|---|---|",
            ]
            for chave in do_nivel:
                _, pagina, tipo, descricao, elemento = chave
                ocorrencias = grupos[chave]
                medidas = sorted({a.detalhe for a in ocorrencias if a.detalhe})
                resumo = "; ".join(medidas[:4]) + (" …" if len(medidas) > 4 else "")
                linhas.append(
                    f"| {pagina} | {tipo} | {_celula(descricao)} | {_celula(elemento)} "
                    f"| {_celula(resumo)} | {_celula(_onde(ocorrencias))} |"
                )
            linhas.append("")
        return "\n".join(linhas)


def _onde(ocorrencias: list[Achado]) -> str:
    """Resume perfil, largura, tema, dados e fluxo das ocorrências de um achado."""
    por_perfil: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for a in ocorrencias:
        por_perfil[a.perfil][a.largura].add(a.tema)
    partes = []
    for perfil in sorted(por_perfil):
        larguras = ", ".join(
            f"{largura} ({'+'.join(sorted(temas))})" for largura, temas in sorted(por_perfil[perfil].items())
        )
        partes.append(f"{perfil}: {larguras}")
    dados = "/".join(sorted({a.dados for a in ocorrencias}))
    fluxos = "/".join(sorted({a.fluxo for a in ocorrencias if a.fluxo}))
    return " · ".join(partes) + f" · dados {dados}" + (f" · fluxo {fluxos}" if fluxos else "")


def _celula(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")
