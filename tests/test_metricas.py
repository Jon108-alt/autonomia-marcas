from datetime import datetime, timezone

import pytest

from autonomia_marcas import demo, metricas
from autonomia_marcas.config import Config, Etapa
from autonomia_marcas.executores import ClassificadorDeExecutor


@pytest.fixture()
def config(tmp_path) -> Config:
    return Config(
        sf_dominio="https://exemplo.my.salesforce.com",
        sf_versao_api="v61.0",
        sf_modo_auth="client_credentials",
        sf_client_id="", sf_client_secret="",
        sf_usuario="", sf_senha="", sf_token="",
        sf_objeto="OrderExportReport__c",
        campo_marca="Brand__c",
        campo_id_pedido="Name",
        campo_status_nf="InvoiceStatus__c",
        campo_nf_enviada="NFSentDate__c",
        campo_avaliacao="EvaluationDate__c",
        campo_aprovacao="InvoiceapprovalDate__c",
        etapas=[
            Etapa("recebimento_po", "Recebimento do PO", "PODownloadDate__c",
                  "PODownloadBy__c", "Download__c"),
            Etapa("upload_nf", "Upload da NF", "NFSentDate__c", "NFSentBy__c"),
        ],
        modo_autonomia="dominio",
        dominios_internos=["privalia.com"],
        perfis_internos=[],
        arquivo_usuarios_internos=tmp_path / "internos.txt",
        data_inicio_padrao=datetime(2026, 8, 1).date(),
        output_dir=tmp_path / "output",
        docs_dir=tmp_path / "docs",
    )


@pytest.fixture()
def classificador(config) -> ClassificadorDeExecutor:
    usuarios = {
        "U_MARCA": {"nome": "Ana", "email": "ana@marca.com", "perfil": "Parceiro"},
        "U_INTERNO": {"nome": "Bia", "email": "bia@privalia.com", "perfil": "Ops"},
    }
    return ClassificadorDeExecutor(config, usuarios)


def test_etapa_sem_data_nao_conta(config, classificador):
    registros = [{"Name": "PO-1", "Brand__c": "Alpha", "NFSentBy__c": "U_MARCA"}]
    assert metricas.extrair_eventos(registros, config, classificador).empty


def test_condicao_falsa_descarta_etapa(config, classificador):
    registros = [{
        "Name": "PO-1", "Brand__c": "Alpha",
        "PODownloadDate__c": "2026-08-02T10:00:00Z",
        "PODownloadBy__c": "U_MARCA",
        "Download__c": False,
    }]
    assert metricas.extrair_eventos(registros, config, classificador).empty


def test_score_por_etapa_e_geral(config, classificador):
    def pedido(nome: str, quem_po: str, quem_nf: str) -> dict:
        return {
            "Name": nome, "Brand__c": "Alpha",
            "PODownloadDate__c": "2026-08-02T10:00:00Z",
            "PODownloadBy__c": quem_po, "Download__c": True,
            "NFSentDate__c": "2026-08-03T10:00:00Z", "NFSentBy__c": quem_nf,
        }

    registros = [
        pedido("PO-1", "U_MARCA", "U_MARCA"),
        pedido("PO-2", "U_MARCA", "U_INTERNO"),
    ]
    eventos = metricas.extrair_eventos(registros, config, classificador)
    detalhes = metricas.calcular_detalhes(eventos, config)

    scores = dict(zip(detalhes["etapa"], detalhes["score"]))
    assert scores["recebimento_po"] == 100.0
    assert scores["upload_nf"] == 50.0

    status = metricas.calcular_status_atual(detalhes, config)
    assert status.loc[0, "score_geral"] == 75.0
    assert status.loc[0, "classificacao"] == "Parcialmente autônomo"


def test_executor_desconhecido_nao_penaliza(config, classificador):
    registros = [{
        "Name": "PO-1", "Brand__c": "Alpha",
        "NFSentDate__c": "2026-08-03T10:00:00Z", "NFSentBy__c": "U_INEXISTENTE",
    }]
    eventos = metricas.extrair_eventos(registros, config, classificador)
    detalhes = metricas.calcular_detalhes(eventos, config)
    assert detalhes.empty  # ignorado, não contado como 0%


@pytest.mark.parametrize(
    "score, esperado",
    [(100.0, "Autônomo"), (90.0, "Autônomo"), (89.9, "Parcialmente autônomo"),
     (50.0, "Parcialmente autônomo"), (49.9, "Em treinamento/suporte")],
)
def test_faixas_de_classificacao(config, score, esperado):
    assert metricas.classificar_score(score, config) == esperado


def test_demo_gera_dados_processaveis(config):
    registros = demo.gerar_registros(config, quantidade=120)
    classificador = ClassificadorDeExecutor(config, demo.usuarios_demo())
    eventos = metricas.extrair_eventos(registros, config, classificador)
    detalhes = metricas.calcular_detalhes(eventos, config)
    assert not detalhes.empty
    assert detalhes["score"].between(0, 100).all()
