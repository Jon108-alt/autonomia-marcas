"""Orquestra o fluxo completo: buscar -> classificar -> agregar -> gravar."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from . import backoffice as bo
from . import demo, metricas, saida
from .config import Config, agora_utc
from .executores import ClassificadorDeExecutor
from .salesforce import ClienteSalesforce

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Resultado:
    momento: datetime
    registros: int
    status_atual: pd.DataFrame
    detalhes: pd.DataFrame
    historico: pd.DataFrame
    backoffice: dict[str, Any]
    arquivos: list[str]


def executar(
    config: Config,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    modo_demo: bool = False,
) -> Resultado:
    momento = agora_utc()

    if modo_demo:
        logger.warning("MODO DEMO — dados fictícios, nada é lido do Salesforce.")
        registros = demo.gerar_registros(config)
        usuarios = demo.usuarios_demo()
    else:
        inicio = inicio or datetime.combine(
            config.data_inicio_padrao, datetime.min.time()
        )
        cliente = ClienteSalesforce(config)
        registros = cliente.buscar_pedidos(inicio, fim)
        logger.info("%d pedidos retornados pelo Salesforce.", len(registros))

        ids_usuarios = {
            registro.get(etapa.campo_executor)
            for registro in registros
            for etapa in config.etapas
        }
        ids_usuarios.update(registro.get("CreatedById") for registro in registros)
        usuarios = cliente.buscar_usuarios({i for i in ids_usuarios if i})

    classificador = ClassificadorDeExecutor(config, usuarios)
    eventos = metricas.extrair_eventos(registros, config, classificador)
    detalhes = metricas.calcular_detalhes(eventos, config)
    status = metricas.calcular_status_atual(detalhes, config)

    notas = bo.extrair_notas(registros, config)
    resumo_backoffice = bo.resumo(notas)

    linha_historico = metricas.montar_historico(detalhes, momento)
    historico = saida.acumular_historico(config.output_dir, linha_historico)

    arquivos = [str(saida.gravar_excel(config.output_dir, status, detalhes, notas))]
    arquivos += [
        str(caminho)
        for caminho in saida.gravar_dashboard(
            [config.output_dir, config.docs_dir],
            momento,
            status,
            detalhes,
            historico,
            resumo_backoffice,
        )
    ]

    return Resultado(
        momento=momento,
        registros=len(registros),
        status_atual=status,
        detalhes=detalhes,
        historico=historico,
        backoffice=resumo_backoffice,
        arquivos=arquivos,
    )
