"""Gravação dos arquivos: histórico CSV, Excel e dashboard.json."""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

ARQ_HISTORICO = "historico_autonomia.csv"
ARQ_EXCEL = "status_atual.xlsx"
ARQ_DASHBOARD = "dashboard.json"
ARQ_EVOLUCAO = "evolucao_periodo.xlsx"


def garantir_pasta(pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def acumular_historico(pasta: Path, novo: pd.DataFrame) -> pd.DataFrame:
    """Anexa a execução atual ao histórico e devolve o histórico completo."""
    caminho = garantir_pasta(pasta) / ARQ_HISTORICO
    if caminho.exists():
        anterior = pd.read_csv(caminho)
        completo = pd.concat([anterior, novo], ignore_index=True)
    else:
        completo = novo
    completo.to_csv(caminho, index=False, encoding="utf-8")
    logger.info("Histórico atualizado: %s (%d linhas).", caminho, len(completo))
    return completo


def gravar_excel(pasta: Path, status: pd.DataFrame, detalhes: pd.DataFrame,
                 notas: pd.DataFrame) -> Path:
    caminho = garantir_pasta(pasta) / ARQ_EXCEL
    with pd.ExcelWriter(caminho, engine="openpyxl") as escritor:
        status.to_excel(escritor, sheet_name="Resumo por marca", index=False)
        detalhes.to_excel(escritor, sheet_name="Detalhe por etapa", index=False)
        if not notas.empty:
            notas.to_excel(escritor, sheet_name="Backoffice NF", index=False)
    logger.info("Excel gravado: %s", caminho)
    return caminho


def _limpar(valor: Any) -> Any:
    """JSON não aceita NaN/NaT; troca por None."""
    if isinstance(valor, float) and math.isnan(valor):
        return None
    if valor is pd.NaT or valor is None:
        return None
    if isinstance(valor, (pd.Timestamp, datetime)):
        return valor.isoformat()
    return valor


def _registros(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return [
        {chave: _limpar(valor) for chave, valor in linha.items()}
        for linha in df.to_dict(orient="records")
    ]


def gravar_dashboard(
    pastas: list[Path],
    momento: datetime,
    status: pd.DataFrame,
    detalhes: pd.DataFrame,
    historico: pd.DataFrame,
    backoffice: dict[str, Any],
) -> list[Path]:
    """Grava o mesmo dashboard.json em todas as pastas (output/ e docs/).

    docs/ é o que o GitHub Pages publica; output/ fica para consulta local.
    """
    dados = {
        "atualizado_em": momento.isoformat(),
        "status_atual": _registros(status),
        "detalhes": _registros(detalhes),
        "historico": _registros(historico),
        "backoffice": backoffice,
    }
    conteudo = json.dumps(dados, ensure_ascii=False, indent=2, default=str)

    escritos: list[Path] = []
    for pasta in pastas:
        caminho = garantir_pasta(pasta) / ARQ_DASHBOARD
        caminho.write_text(conteudo, encoding="utf-8")
        escritos.append(caminho)
        logger.info("Dashboard gravado: %s", caminho)
    return escritos
