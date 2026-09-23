"""Testes de src/domain/documentos.py (Fase 4)."""

from datetime import date

from src.domain.documentos import situacao_documento, sugerir_proximo_documento


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


class TestSituacaoDocumento:
    HOJE = date(2026, 9, 21)

    def test_vencido_quando_passou_do_vencimento(self):
        assert situacao_documento(date(2026, 9, 20), False, self.HOJE, 30) == "vencido"

    def test_vence_hoje_ainda_e_a_vencer(self):
        assert situacao_documento(self.HOJE, False, self.HOJE, 30) == "a_vencer"

    def test_a_vencer_no_limite_do_alerta(self):
        assert situacao_documento(date(2026, 10, 21), False, self.HOJE, 30) == "a_vencer"

    def test_em_dia_alem_do_alerta(self):
        assert situacao_documento(date(2026, 10, 22), False, self.HOJE, 30) == "em_dia"

    def test_regularizado_esta_em_dia_mesmo_vencido(self):
        assert situacao_documento(date(2026, 1, 1), True, self.HOJE, 30) == "em_dia"
