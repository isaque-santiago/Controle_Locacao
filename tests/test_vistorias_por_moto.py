"""Vistoria por moto em contrato com várias motos: validação, motos pendentes e exigência da tela."""

import pytest

from src.domain.vistorias_por_moto import exigir_todas_as_motos, motos_sem_vistoria, validar_vistorias_vinculadas

KM = {"m2": 1000, "m3": 500}


class TestValidarVistoriasVinculadas:
    def test_sem_vistorias_devolve_lista_vazia(self):
        assert validar_vistorias_vinculadas("m1", ["m2"], None, KM) == []

    def test_normaliza_moto_e_km(self):
        r = validar_vistorias_vinculadas("m1", ["m2"], [{"moto_id": " m2 ", "km": "1200", "checklist": {}}], KM)
        assert r == [{"moto_id": "m2", "km": 1200, "checklist": {}}]

    def test_aceita_km_igual_ao_atual(self):
        assert validar_vistorias_vinculadas("m1", ["m2"], [{"moto_id": "m2", "km": 1000}], KM)[0]["km"] == 1000

    def test_recusa_km_menor_que_o_atual(self):
        with pytest.raises(ValueError, match="menor que a atual"):
            validar_vistorias_vinculadas("m1", ["m2"], [{"moto_id": "m2", "km": 999}], KM)

    def test_recusa_km_invalido_ou_negativo(self):
        with pytest.raises(ValueError, match="quilometragem"):
            validar_vistorias_vinculadas("m1", ["m2"], [{"moto_id": "m2", "km": "abc"}], KM)
        with pytest.raises(ValueError, match="negativa"):
            validar_vistorias_vinculadas("m1", ["m2"], [{"moto_id": "m2", "km": -1}], KM)

    def test_recusa_moto_de_fora_do_contrato(self):
        with pytest.raises(ValueError, match="não pertence"):
            validar_vistorias_vinculadas("m1", ["m2"], [{"moto_id": "m9", "km": 10}], KM)

    def test_recusa_a_principal_na_lista(self):
        with pytest.raises(ValueError, match="principal"):
            validar_vistorias_vinculadas("m1", ["m2"], [{"moto_id": "m1", "km": 10}], KM)

    def test_recusa_moto_repetida(self):
        with pytest.raises(ValueError, match="mais de uma vez"):
            validar_vistorias_vinculadas("m1", ["m2"], [{"moto_id": "m2", "km": 1100}, {"moto_id": "m2", "km": 1200}], KM)

    def test_recusa_vistoria_sem_moto(self):
        with pytest.raises(ValueError, match="Informe a moto"):
            validar_vistorias_vinculadas("m1", ["m2"], [{"km": 10}], KM)


class TestMotosSemVistoria:
    FEITAS = [
        {"moto_id": "m1", "tipo": "entrega"},
        {"moto_id": "m1", "tipo": "devolucao"},
        {"moto_id": "m2", "tipo": "entrega"},
    ]

    def test_a_principal_vem_primeiro(self):
        assert motos_sem_vistoria("m1", ["m2", "m3"], [], "entrega") == ["m1", "m2", "m3"]

    def test_so_as_que_faltam_no_tipo(self):
        assert motos_sem_vistoria("m1", ["m2", "m3"], self.FEITAS, "entrega") == ["m3"]
        assert motos_sem_vistoria("m1", ["m2", "m3"], self.FEITAS, "devolucao") == ["m2", "m3"]

    def test_contrato_de_uma_moto_so(self):
        assert motos_sem_vistoria("m1", None, self.FEITAS, "entrega") == []

    def test_recusa_tipo_invalido(self):
        with pytest.raises(ValueError, match="tipo"):
            motos_sem_vistoria("m1", ["m2"], [], "outro")


class TestExigirTodasAsMotos:
    def test_sem_vinculadas_nao_exige_nada(self):
        exigir_todas_as_motos("m1", None, None)

    def test_com_todas_passa(self):
        exigir_todas_as_motos("m1", ["m2", "m3"], [{"moto_id": "m3"}, {"moto_id": "m2"}])

    def test_falta_uma_recusa(self):
        with pytest.raises(ValueError, match="todas as motos"):
            exigir_todas_as_motos("m1", ["m2", "m3"], [{"moto_id": "m2"}])

    def test_com_vinculadas_e_nenhuma_vistoria_recusa(self):
        with pytest.raises(ValueError, match="todas as motos"):
            exigir_todas_as_motos("m1", ["m2"], [])
