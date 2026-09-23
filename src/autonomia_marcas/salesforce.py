"""Cliente mínimo da REST API do Salesforce.

Optamos por `requests` direto em vez de `simple-salesforce`: são ~80 linhas,
uma dependência a menos para aprovar internamente, e a paginação do SOQL
(`nextRecordsUrl`) é trivial. Se um dia precisar de bulk API ou metadata,
aí sim vale trocar por uma biblioteca dedicada.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterator

import requests

from .config import Config

logger = logging.getLogger(__name__)

TIMEOUT = 60


class ErroSalesforce(RuntimeError):
    """Falha de autenticação ou de consulta no Salesforce."""


class ClienteSalesforce:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._sessao = requests.Session()
        self._token: str | None = None
        self._instancia: str = config.sf_dominio

    # ------------------------------------------------------------------ #
    def autenticar(self) -> None:
        cfg = self.config
        url = f"{cfg.sf_dominio}/services/oauth2/token"

        if cfg.sf_modo_auth == "client_credentials":
            dados = {
                "grant_type": "client_credentials",
                "client_id": cfg.sf_client_id,
                "client_secret": cfg.sf_client_secret,
            }
        else:
            dados = {
                "grant_type": "password",
                "client_id": cfg.sf_client_id,
                "client_secret": cfg.sf_client_secret,
                "username": cfg.sf_usuario,
                "password": f"{cfg.sf_senha}{cfg.sf_token}",
            }

        resposta = self._sessao.post(url, data=dados, timeout=TIMEOUT)
        if resposta.status_code != 200:
            # Nunca logamos `dados`: ele contém client_secret e senha.
            raise ErroSalesforce(
                f"Falha ao autenticar no Salesforce ({resposta.status_code}): "
                f"{resposta.text[:300]}"
            )

        corpo = resposta.json()
        self._token = corpo["access_token"]
        self._instancia = corpo.get("instance_url", cfg.sf_dominio).rstrip("/")
        self._sessao.headers.update({"Authorization": f"Bearer {self._token}"})
        logger.info("Autenticado no Salesforce (%s).", self._instancia)

    # ------------------------------------------------------------------ #
    def consultar(self, soql: str) -> Iterator[dict[str, Any]]:
        """Executa uma SOQL e percorre todas as páginas de resultado."""
        if self._token is None:
            self.autenticar()

        url = f"{self._instancia}/services/data/{self.config.sf_versao_api}/query"
        params: dict[str, str] | None = {"q": soql}

        while True:
            resposta = self._sessao.get(url, params=params, timeout=TIMEOUT)
            if resposta.status_code != 200:
                raise ErroSalesforce(
                    f"Erro na consulta ({resposta.status_code}): {resposta.text[:500]}"
                )
            corpo = resposta.json()
            yield from corpo.get("records", [])

            proxima = corpo.get("nextRecordsUrl")
            if corpo.get("done", True) or not proxima:
                break
            url = f"{self._instancia}{proxima}"
            params = None

    # ------------------------------------------------------------------ #
    def buscar_pedidos(
        self, inicio: datetime, fim: datetime | None = None
    ) -> list[dict[str, Any]]:
        cfg = self.config
        campos = ", ".join(cfg.campos_consulta())
        filtros = [f"CreatedDate >= {formatar_datahora(inicio)}"]
        if fim is not None:
            filtros.append(f"CreatedDate < {formatar_datahora(fim)}")

        soql = (
            f"SELECT {campos} FROM {cfg.sf_objeto} "
            f"WHERE {' AND '.join(filtros)} ORDER BY CreatedDate"
        )
        logger.info("SOQL: %s", soql)
        return list(self.consultar(soql))

    # ------------------------------------------------------------------ #
    def buscar_usuarios(self, ids: set[str]) -> dict[str, dict[str, Any]]:
        """Traz Nome, Email e Perfil dos usuários citados nos pedidos.

        Fazemos em lotes de 200 porque a SOQL tem limite de tamanho de query
        e o operador IN fica lento com listas muito grandes.
        """
        ids_validos = sorted(i for i in ids if i)
        usuarios: dict[str, dict[str, Any]] = {}

        for inicio in range(0, len(ids_validos), 200):
            lote = ids_validos[inicio : inicio + 200]
            lista = ", ".join(f"'{i}'" for i in lote)
            soql = (
                "SELECT Id, Name, Email, Username, Profile.Name, UserType "
                f"FROM User WHERE Id IN ({lista})"
            )
            for registro in self.consultar(soql):
                perfil = (registro.get("Profile") or {}).get("Name", "")
                usuarios[registro["Id"]] = {
                    "nome": registro.get("Name", ""),
                    "email": registro.get("Email", "") or registro.get("Username", ""),
                    "perfil": perfil,
                    "tipo": registro.get("UserType", ""),
                }
        return usuarios

    def testar_conexao(self) -> dict[str, Any]:
        self.autenticar()
        soql = f"SELECT COUNT() FROM {self.config.sf_objeto}"
        url = f"{self._instancia}/services/data/{self.config.sf_versao_api}/query"
        resposta = self._sessao.get(url, params={"q": soql}, timeout=TIMEOUT)
        if resposta.status_code != 200:
            raise ErroSalesforce(
                f"Conectou, mas a consulta falhou ({resposta.status_code}): "
                f"{resposta.text[:500]}"
            )
        return resposta.json()


def formatar_datahora(valor: datetime) -> str:
    """SOQL exige ISO-8601 com timezone, ex.: 2026-08-01T00:00:00Z."""
    if valor.tzinfo is None:
        return valor.strftime("%Y-%m-%dT%H:%M:%SZ")
    return valor.astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
