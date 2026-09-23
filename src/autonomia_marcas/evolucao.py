"""Compara o score do início e do fim de um período, usando o histórico."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .saida import ARQ_EVOLUCAO, ARQ_HISTORICO, garantir_pasta

LIMIAR_EVOLUCAO = 5.0  # pontos percentuais para considerar "Estável"


class HistoricoInsuficiente(RuntimeError):
    pass


def _tendencia(delta: float) -> str:
    if delta > LIMIAR_EVOLUCAO:
        return "Evoluindo"
    if delta < -LIMIAR_EVOLUCAO:
        return "Regredindo"
    return "Estável"


def calcular(pasta: Path, inicio: date, fim: date) -> pd.DataFrame:
    caminho = pasta / ARQ_HISTORICO
    if not caminho.exists():
        raise HistoricoInsuficiente(
            f"{caminho} não existe. Rode 'autonomia-marcas executar' pelo menos "
            "duas vezes dentro do período antes de calcular a evolução."
        )

    historico = pd.read_csv(caminho)
    historico["execucao_em"] = pd.to_datetime(
        historico["execucao_em"], utc=True, errors="coerce"
    )
    janela = historico[
        (historico["execucao_em"].dt.date >= inicio)
        & (historico["execucao_em"].dt.date <= fim)
    ]
    if janela.empty:
        raise HistoricoInsuficiente(
            f"Não há execuções registradas entre {inicio} e {fim}."
        )

    # Score geral por marca em cada execução = média simples das etapas.
    por_execucao = (
        janela.groupby(["execucao_em", "marca"], as_index=False)["score"]
        .mean()
        .rename(columns={"score": "score_geral"})
    )

    primeira = por_execucao["execucao_em"].min()
    ultima = por_execucao["execucao_em"].max()
    if primeira == ultima:
        raise HistoricoInsuficiente(
            "Só existe uma execução no período — não dá para comparar início e fim."
        )

    inicio_df = (
        por_execucao[por_execucao["execucao_em"] == primeira]
        .rename(columns={"score_geral": "score_inicio"})[["marca", "score_inicio"]]
    )
    fim_df = (
        por_execucao[por_execucao["execucao_em"] == ultima]
        .rename(columns={"score_geral": "score_fim"})[["marca", "score_fim"]]
    )

    comparacao = inicio_df.merge(fim_df, on="marca", how="outer")
    comparacao["delta"] = (
        comparacao["score_fim"] - comparacao["score_inicio"]
    ).round(1)
    comparacao["score_inicio"] = comparacao["score_inicio"].round(1)
    comparacao["score_fim"] = comparacao["score_fim"].round(1)
    comparacao["tendencia"] = comparacao["delta"].apply(
        lambda valor: "Sem base" if pd.isna(valor) else _tendencia(valor)
    )
    return comparacao.sort_values("delta", ascending=False).reset_index(drop=True)


def gravar(pasta: Path, comparacao: pd.DataFrame) -> Path:
    caminho = garantir_pasta(pasta) / ARQ_EVOLUCAO
    comparacao.to_excel(caminho, index=False)
    return caminho
