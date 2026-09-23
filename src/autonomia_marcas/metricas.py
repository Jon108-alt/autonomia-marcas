"""Cálculo da autonomia por marca e etapa.

Regra: uma etapa só entra na conta quando foi concluída (tem data e, se houver
campo de condição, ele é verdadeiro) E o executor foi identificado. Executor
desconhecido não vira "não autônomo" — vira registro ignorado, senão a métrica
pune a marca por uma falha de cadastro no Salesforce.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable

import pandas as pd

from .config import Config
from .executores import ClassificadorDeExecutor


@dataclass(frozen=True, slots=True)
class LinhaEtapa:
    marca: str
    etapa: str
    rotulo_etapa: str
    id_pedido: str
    executor_nome: str
    executor_email: str
    origem: str
    autonomo: bool
    data_execucao: str | None


def _verdadeiro(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return False
    return str(valor).strip().lower() in {"true", "1", "sim", "yes"}


def extrair_eventos(
    registros: Iterable[dict[str, Any]],
    config: Config,
    classificador: ClassificadorDeExecutor,
) -> pd.DataFrame:
    """Transforma cada pedido em até 4 linhas (uma por etapa concluída)."""
    linhas: list[LinhaEtapa] = []

    for registro in registros:
        marca = (registro.get(config.campo_marca) or "Sem marca").strip()
        id_pedido = str(registro.get(config.campo_id_pedido) or registro.get("Id", ""))

        for etapa in config.etapas:
            data = registro.get(etapa.campo_data)
            if not data:
                continue
            if etapa.campo_condicao and not _verdadeiro(registro.get(etapa.campo_condicao)):
                continue

            executor = classificador.classificar(registro.get(etapa.campo_executor))
            linhas.append(
                LinhaEtapa(
                    marca=marca,
                    etapa=etapa.chave,
                    rotulo_etapa=etapa.rotulo,
                    id_pedido=id_pedido,
                    executor_nome=executor.nome,
                    executor_email=executor.email,
                    origem=executor.origem,
                    autonomo=executor.autonomo,
                    data_execucao=str(data),
                )
            )

    if not linhas:
        return pd.DataFrame(columns=list(LinhaEtapa.__annotations__))
    return pd.DataFrame([asdict(linha) for linha in linhas])


def classificar_score(score: float, config: Config) -> str:
    if score >= config.limiar_autonomo:
        return "Autônomo"
    if score >= config.limiar_parcial:
        return "Parcialmente autônomo"
    return "Em treinamento/suporte"


def calcular_detalhes(eventos: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Taxa de autonomia por marca x etapa."""
    colunas = [
        "marca", "etapa", "rotulo_etapa", "total", "autonomos",
        "internos", "desconhecidos", "score",
    ]
    if eventos.empty:
        return pd.DataFrame(columns=colunas)

    considerados = eventos[eventos["origem"] != "desconhecido"]
    agrupado = (
        considerados.groupby(["marca", "etapa", "rotulo_etapa"], as_index=False)
        .agg(total=("autonomo", "size"), autonomos=("autonomo", "sum"))
    )
    agrupado["internos"] = agrupado["total"] - agrupado["autonomos"]

    ignorados = (
        eventos[eventos["origem"] == "desconhecido"]
        .groupby(["marca", "etapa"], as_index=False)
        .size()
        .rename(columns={"size": "desconhecidos"})
    )
    agrupado = agrupado.merge(ignorados, on=["marca", "etapa"], how="left")
    agrupado["desconhecidos"] = agrupado["desconhecidos"].fillna(0).astype(int)
    agrupado["score"] = (agrupado["autonomos"] / agrupado["total"] * 100).round(1)
    return agrupado[colunas]


def calcular_status_atual(detalhes: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Score geral por marca = média simples das etapas presentes (peso igual)."""
    colunas = [
        "marca", "score_geral", "classificacao", "etapas_medidas", "total_eventos",
    ]
    if detalhes.empty:
        return pd.DataFrame(columns=colunas)

    resumo = (
        detalhes.groupby("marca", as_index=False)
        .agg(
            score_geral=("score", "mean"),
            etapas_medidas=("etapa", "nunique"),
            total_eventos=("total", "sum"),
        )
    )
    resumo["score_geral"] = resumo["score_geral"].round(1)
    resumo["classificacao"] = resumo["score_geral"].apply(
        lambda valor: classificar_score(valor, config)
    )
    return resumo.sort_values("score_geral", ascending=False)[colunas].reset_index(drop=True)


def montar_historico(detalhes: pd.DataFrame, momento: datetime) -> pd.DataFrame:
    if detalhes.empty:
        return pd.DataFrame(
            columns=["execucao_em", "marca", "etapa", "rotulo_etapa", "total", "autonomos", "score"]
        )
    registro = detalhes.copy()
    registro.insert(0, "execucao_em", momento.isoformat())
    return registro[
        ["execucao_em", "marca", "etapa", "rotulo_etapa", "total", "autonomos", "score"]
    ]
