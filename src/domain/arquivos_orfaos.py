"""Arquivos órfãos do portal (pendência da Fase 7). Funções puras.

O locatário envia as fotos da troca de óleo e o comprovante de documento ao Storage antes de registrar a operação. Se o registro falha,
o arquivo fica no Storage sem nenhuma linha que o referencie. A RPC `rpc_listar_arquivos_orfaos` os encontra (só os do portal, só os com
mais de `HORAS_MINIMAS` horas); aqui ficam o agrupamento por bucket, o resumo da tela e o tamanho em texto."""

from collections import OrderedDict

HORAS_MINIMAS = 24
TAMANHO_DO_LOTE = 100  # arquivos por chamada de remoção ao Storage
ROTULO_BUCKET = {
    "trocas_oleo": "Fotos de troca de óleo",
    "documentos": "Comprovantes de documentos enviados pelo locatário",
}


def rotulo_do_bucket(bucket: str) -> str:
    return ROTULO_BUCKET.get(bucket, bucket)


def formatar_tamanho(bytes_: int | None) -> str:
    """1536 -> '1,5 KB'; 3145728 -> '3,0 MB'. Sem decimais abaixo de 1 KB."""
    total = int(bytes_ or 0)
    if total < 1024:
        return f"{total} B"
    valor = float(total)
    for unidade in ("KB", "MB", "GB"):
        valor /= 1024
        if valor < 1024:
            break
    return f"{valor:.1f}".replace(".", ",") + f" {unidade}"


def agrupar_por_bucket(arquivos: list[dict]) -> "OrderedDict[str, list[str]]":
    """{bucket: [caminhos]} na ordem em que os buckets aparecem; cada caminho uma vez só."""
    grupos: "OrderedDict[str, list[str]]" = OrderedDict()
    for a in arquivos:
        caminhos = grupos.setdefault(a["bucket"], [])
        if a["caminho"] not in caminhos:
            caminhos.append(a["caminho"])
    return grupos


def em_lotes(caminhos: list[str], tamanho: int = TAMANHO_DO_LOTE) -> list[list[str]]:
    return [caminhos[i:i + tamanho] for i in range(0, len(caminhos), tamanho)]


def resumir(arquivos: list[dict]) -> dict:
    """Totais para a tela: quantidade, tamanho (texto) e quantidade por bucket, mais os arquivos já com rótulo e tamanho."""
    por_bucket: "OrderedDict[str, int]" = OrderedDict()
    for a in arquivos:
        por_bucket[a["bucket"]] = por_bucket.get(a["bucket"], 0) + 1
    total_bytes = sum(int(a.get("tamanho") or 0) for a in arquivos)
    return {
        "quantidade": len(arquivos),
        "tamanho": formatar_tamanho(total_bytes),
        "por_bucket": [(rotulo_do_bucket(b), n) for b, n in por_bucket.items()],
        "itens": [{**a, "rotulo": rotulo_do_bucket(a["bucket"]), "tamanho_texto": formatar_tamanho(a.get("tamanho"))} for a in arquivos],
    }
