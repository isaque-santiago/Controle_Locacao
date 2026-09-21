"""Testes de src/domain/documentos.py (Fase 4)."""

from src.domain.documentos import sugerir_proximo_documento


class TestSugerirProximoDocumento:
    def test_ipva_sugere_ano_seguinte_sem_vencimento(self):
        sugestao = sugerir_proximo_documento("ipva", 2026)
        assert sugestao == {
            "tipo": "ipva",
            "ano_referencia": 2027,
            "vencimento": None,
            "regularizado": False,
        }

    def test_licenciamento_sugere_ano_seguinte(self):
        sugestao = sugerir_proximo_documento("licenciamento", 2026)
        assert sugestao["ano_referencia"] == 2027

    def test_seguro_sugere_ano_seguinte(self):
        sugestao = sugerir_proximo_documento("seguro", 2026)
        assert sugestao["ano_referencia"] == 2027

    def test_tipo_sem_renovacao_anual_nao_sugere(self):
        assert sugerir_proximo_documento("vistoria_detran", 2026) is None
        assert sugerir_proximo_documento("outro", 2026) is None

    def test_sem_ano_referencia_nao_sugere(self):
        assert sugerir_proximo_documento("ipva", None) is None
