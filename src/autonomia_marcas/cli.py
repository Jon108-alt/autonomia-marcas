"""Interface de linha de comando.

Usamos argparse (stdlib) em vez de click/typer: são três subcomandos e assim
o projeto não ganha dependência externa só para parsear argumentos.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime

from . import evolucao as mod_evolucao
from . import pipeline
from .config import Config, ErroDeConfiguracao
from .salesforce import ClienteSalesforce, ErroSalesforce


def _configurar_log(verboso: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


def _data_hora(texto: str) -> datetime:
    try:
        return datetime.fromisoformat(texto)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"'{texto}' não é uma data válida. Use AAAA-MM-DD ou AAAA-MM-DDTHH:MM:SS."
        ) from exc


def _data(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"'{texto}' não é uma data válida. Use AAAA-MM-DD."
        ) from exc


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autonomia-marcas",
        description="Painel de autonomia de marcas e tempos do backoffice.",
    )
    parser.add_argument("-v", "--verboso", action="store_true", help="log detalhado")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("testar", help="valida .env e conexão com o Salesforce")

    executar = sub.add_parser("executar", help="roda o pipeline e gera os arquivos")
    executar.add_argument("--inicio", type=_data_hora, help="início da janela")
    executar.add_argument("--fim", type=_data_hora, help="fim da janela (exclusivo)")
    executar.add_argument(
        "--demo",
        action="store_true",
        help="usa dados fictícios (não acessa o Salesforce)",
    )

    evol = sub.add_parser("evolucao", help="compara o score no início e no fim")
    evol.add_argument("--inicio", type=_data, required=True)
    evol.add_argument("--fim", type=_data, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    _configurar_log(args.verboso)

    try:
        config = Config.carregar()
    except ErroDeConfiguracao as erro:
        print(f"ERRO de configuração: {erro}", file=sys.stderr)
        return 2

    try:
        if args.comando == "testar":
            return _testar(config)
        if args.comando == "executar":
            return _executar(config, args)
        if args.comando == "evolucao":
            return _evolucao(config, args)
    except ErroSalesforce as erro:
        print(f"ERRO no Salesforce: {erro}", file=sys.stderr)
        return 3
    except mod_evolucao.HistoricoInsuficiente as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 4

    return 0


def _testar(config: Config) -> int:
    print(f"Objeto  : {config.sf_objeto}")
    print(f"Domínio : {config.sf_dominio}")
    print(f"Etapas  : {', '.join(e.rotulo for e in config.etapas)}")
    print(f"Regra de autonomia: {config.modo_autonomia}")
    resultado = ClienteSalesforce(config).testar_conexao()
    print(f"OK — {resultado.get('totalSize', 0)} registros visíveis em {config.sf_objeto}.")
    return 0


def _executar(config: Config, args: argparse.Namespace) -> int:
    resultado = pipeline.executar(
        config, inicio=args.inicio, fim=args.fim, modo_demo=args.demo
    )
    print(f"\nPedidos processados: {resultado.registros}")
    print(f"Marcas medidas     : {len(resultado.status_atual)}")
    if not resultado.status_atual.empty:
        print("\nTop 10 por score geral:")
        print(resultado.status_atual.head(10).to_string(index=False))
    print("\nArquivos gerados:")
    for caminho in resultado.arquivos:
        print(f"  - {caminho}")
    return 0


def _evolucao(config: Config, args: argparse.Namespace) -> int:
    comparacao = mod_evolucao.calcular(config.output_dir, args.inicio, args.fim)
    caminho = mod_evolucao.gravar(config.output_dir, comparacao)
    print(comparacao.to_string(index=False))
    print(f"\nArquivo gerado: {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
