"""Métricas do backoffice: quanto tempo leva cada perna da aprovação da NF.

Pernas medidas (em horas úteis corridas — usamos horas corridas mesmo, por
simplicidade e por serem auditáveis; se precisar de horário comercial, o
ponto de troca é `_diferenca_horas`):

    envio_para_avaliacao : NFSentDate__c        -> EvaluationDate__c
    avaliacao_para_aprovacao : EvaluationDate__c -> InvoiceapprovalDate__c
    total : NFSentDate__c -> InvoiceapprovalDate__c
"""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from .config import Config

PERNAS = [
    ("envio_para_avaliacao", "Envio da NF → início da avaliação"),
    ("avaliacao_para_aprovacao", "Avaliação → aprovação da NF"),
    ("total", "Total: envio → aprovação"),
]


def _para_datahora(valor: Any) -> pd.Timestamp | None:
    if not valor:
        return None
    marca = pd.to_datetime(valor, utc=True, errors="coerce")
    return None if pd.isna(marca) else marca


def _diferenca_horas(inicio: Any, fim: Any) -> float | None:
    a, b = _para_datahora(inicio), _para_datahora(fim)
    if a is None or b is None or b < a:
        return None
    return round((b - a).total_seconds() / 3600, 2)


def extrair_notas(
    registros: Iterable[dict[str, Any]], config: Config
) -> pd.DataFrame:
    """Uma linha por pedido que já teve a NF enviada."""
    linhas: list[dict[str, Any]] = []
    agora = pd.Timestamp.now(tz="UTC")

    for registro in registros:
        enviada = registro.get(config.campo_nf_enviada)
        if not enviada:
            continue

        avaliada = registro.get(config.campo_avaliacao)
        aprovada = registro.get(config.campo_aprovacao)
        marca_dt = _para_datahora(enviada)

        linhas.append(
            {
                "marca": (registro.get(config.campo_marca) or "Sem marca").strip(),
                "id_pedido": str(
                    registro.get(config.campo_id_pedido) or registro.get("Id", "")
                ),
                "status": (registro.get(config.campo_status_nf) or "Sem status").strip(),
                "nf_enviada_em": str(enviada),
                "avaliada_em": str(avaliada) if avaliada else None,
                "aprovada_em": str(aprovada) if aprovada else None,
                "envio_para_avaliacao": _diferenca_horas(enviada, avaliada),
                "avaliacao_para_aprovacao": _diferenca_horas(avaliada, aprovada),
                "total": _diferenca_horas(enviada, aprovada),
                "concluida": bool(aprovada),
                "horas_em_fila": (
                    None
                    if aprovada or marca_dt is None
                    else round((agora - marca_dt).total_seconds() / 3600, 2)
                ),
                "mes": marca_dt.strftime("%Y-%m") if marca_dt is not None else None,
                "semana": (
                    marca_dt.strftime("%G-S%V") if marca_dt is not None else None
                ),
            }
        )

    return pd.DataFrame(linhas)


def tempos_por_perna(notas: pd.DataFrame) -> list[dict[str, Any]]:
    """Média, mediana e p90 de cada perna do processo."""
    if notas.empty:
        return []

    resultado: list[dict[str, Any]] = []
    for chave, rotulo in PERNAS:
        serie = notas[chave].dropna()
        resultado.append(
            {
                "perna": chave,
                "rotulo": rotulo,
                "amostras": int(serie.size),
                "media_horas": round(float(serie.mean()), 2) if serie.size else None,
                "mediana_horas": round(float(serie.median()), 2) if serie.size else None,
                "p90_horas": (
                    round(float(serie.quantile(0.9)), 2) if serie.size else None
                ),
            }
        )
    return resultado


def ranking_marcas(notas: pd.DataFrame, minimo_amostras: int = 3) -> list[dict[str, Any]]:
    """Marcas ordenadas pelo tempo total até a aprovação (maior primeiro)."""
    if notas.empty:
        return []

    concluidas = notas.dropna(subset=["total"])
    if concluidas.empty:
        return []

    agrupado = (
        concluidas.groupby("marca", as_index=False)
        .agg(
            notas_aprovadas=("total", "size"),
            media_total_horas=("total", "mean"),
            mediana_total_horas=("total", "median"),
            media_envio_avaliacao=("envio_para_avaliacao", "mean"),
            media_avaliacao_aprovacao=("avaliacao_para_aprovacao", "mean"),
        )
    )
    agrupado = agrupado[agrupado["notas_aprovadas"] >= minimo_amostras]
    for coluna in agrupado.columns:
        if coluna.startswith(("media", "mediana")):
            agrupado[coluna] = agrupado[coluna].round(2)

    return (
        agrupado.sort_values("media_total_horas", ascending=False)
        .to_dict(orient="records")
    )


def fila_atual(notas: pd.DataFrame) -> list[dict[str, Any]]:
    """Quantas NFs estão paradas em cada status e há quanto tempo."""
    if notas.empty:
        return []

    pendentes = notas[~notas["concluida"]]
    if pendentes.empty:
        return []

    agrupado = (
        pendentes.groupby("status", as_index=False)
        .agg(
            quantidade=("id_pedido", "size"),
            media_horas_parada=("horas_em_fila", "mean"),
            maior_espera_horas=("horas_em_fila", "max"),
        )
    )
    agrupado["media_horas_parada"] = agrupado["media_horas_parada"].round(2)
    agrupado["maior_espera_horas"] = agrupado["maior_espera_horas"].round(2)
    return agrupado.sort_values("quantidade", ascending=False).to_dict(orient="records")


def evolucao_mensal(notas: pd.DataFrame) -> list[dict[str, Any]]:
    """Tempo médio de aprovação por mês de envio da NF."""
    if notas.empty:
        return []

    concluidas = notas.dropna(subset=["total", "mes"])
    if concluidas.empty:
        return []

    agrupado = (
        concluidas.groupby("mes", as_index=False)
        .agg(
            notas=("total", "size"),
            media_total_horas=("total", "mean"),
            media_envio_avaliacao=("envio_para_avaliacao", "mean"),
            media_avaliacao_aprovacao=("avaliacao_para_aprovacao", "mean"),
        )
        .sort_values("mes")
    )
    for coluna in ("media_total_horas", "media_envio_avaliacao", "media_avaliacao_aprovacao"):
        agrupado[coluna] = agrupado[coluna].round(2)
    return agrupado.to_dict(orient="records")


def resumo(notas: pd.DataFrame) -> dict[str, Any]:
    if notas.empty:
        return {
            "total_notas": 0,
            "aprovadas": 0,
            "pendentes": 0,
            "media_total_horas": None,
            "por_perna": [],
            "ranking_marcas": [],
            "fila": [],
            "evolucao": [],
        }

    concluidas = notas.dropna(subset=["total"])
    return {
        "total_notas": int(len(notas)),
        "aprovadas": int(len(concluidas)),
        "pendentes": int((~notas["concluida"]).sum()),
        "media_total_horas": (
            round(float(concluidas["total"].mean()), 2) if not concluidas.empty else None
        ),
        "por_perna": tempos_por_perna(notas),
        "ranking_marcas": ranking_marcas(notas),
        "fila": fila_atual(notas),
        "evolucao": evolucao_mensal(notas),
    }
