import pandas as pd
import pytest

from autonomia_marcas import backoffice as bo
from tests.test_metricas import config, classificador  # noqa: F401


def test_diferenca_horas_ignora_ordem_invertida():
    assert bo._diferenca_horas("2026-08-02T12:00:00Z", "2026-08-02T18:00:00Z") == 6.0
    assert bo._diferenca_horas("2026-08-02T18:00:00Z", "2026-08-02T12:00:00Z") is None
    assert bo._diferenca_horas(None, "2026-08-02T12:00:00Z") is None


def test_extrai_apenas_pedidos_com_nf_enviada(config):  # noqa: F811
    registros = [
        {"Name": "PO-1", "Brand__c": "Alpha"},
        {
            "Name": "PO-2", "Brand__c": "Alpha",
            "NFSentDate__c": "2026-08-01T09:00:00Z",
            "EvaluationDate__c": "2026-08-01T15:00:00Z",
            "InvoiceapprovalDate__c": "2026-08-02T09:00:00Z",
            "InvoiceStatus__c": "Aprovado",
        },
    ]
    notas = bo.extrair_notas(registros, config)
    assert len(notas) == 1
    linha = notas.iloc[0]
    assert linha["envio_para_avaliacao"] == 6.0
    assert linha["avaliacao_para_aprovacao"] == 18.0
    assert linha["total"] == 24.0
    assert bool(linha["concluida"]) is True


def test_fila_conta_pendentes_por_status(config):  # noqa: F811
    registros = [
        {"Name": f"PO-{i}", "Brand__c": "Alpha",
         "NFSentDate__c": "2026-08-01T09:00:00Z", "InvoiceStatus__c": "Pendente"}
        for i in range(3)
    ]
    fila = bo.fila_atual(bo.extrair_notas(registros, config))
    assert fila[0]["status"] == "Pendente"
    assert fila[0]["quantidade"] == 3


def test_resumo_vazio_nao_quebra(config):  # noqa: F811
    resumo = bo.resumo(pd.DataFrame())
    assert resumo["total_notas"] == 0
    assert resumo["por_perna"] == []
