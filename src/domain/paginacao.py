"""Paginação e filtros de listas: regras puras, sem Streamlit."""

from dataclasses import dataclass

OPCOES_POR_PAGINA = (10, 25, 50)


@dataclass(frozen=True)
class Pagina:
    """Recorte de uma lista: página atual (já limitada ao intervalo válido) e índices."""

    pagina: int
    total_paginas: int
    por_pagina: int
    total: int
    inicio: int  # índice do primeiro item (base 0)
    fim: int  # índice após o último item (fatiamento `itens[inicio:fim]`)

    @property
    def tem_anterior(self):
        return self.pagina > 1

    @property
    def tem_proxima(self):
        return self.pagina < self.total_paginas

    def resumo(self):
        """Ex.: `Mostrando 11 a 20 de 23 · página 2 de 3`; lista vazia: `Nenhum resultado`."""
        if not self.total:
            return "Nenhum resultado"
        return (
            f"Mostrando {self.inicio + 1} a {self.fim} de {self.total} · "
            f"página {self.pagina} de {self.total_paginas}"
        )


def calcular_pagina(total, pagina, por_pagina):
    """Limita `pagina` a 1..total_paginas (a lista pode ter encolhido depois de um filtro ou de
    uma exclusão) e devolve os índices do recorte. `por_pagina` inválido (< 1) vira 1."""
    por_pagina = max(1, int(por_pagina))
    total = max(0, int(total))
    total_paginas = max(1, -(-total // por_pagina))
    pagina = min(max(1, int(pagina or 1)), total_paginas)
    inicio = (pagina - 1) * por_pagina
    return Pagina(pagina, total_paginas, por_pagina, total, inicio, min(total, inicio + por_pagina))


def filtros_ativos(valor, padrao, busca):
    """Rótulos dos filtros que fogem do estado inicial da lista: `filtro` (o valor difere do
    padrão) e `busca` (texto não vazio). Serve ao resumo e à contagem de filtros ativos."""
    ativos = []
    if valor != padrao:
        ativos.append("filtro")
    if (busca or "").strip():
        ativos.append("busca")
    return ativos
