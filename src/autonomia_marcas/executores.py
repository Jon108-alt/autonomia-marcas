"""Decide se quem executou uma etapa foi a MARCA (autônomo) ou o time interno.

Três modos, escolhidos em MODO_AUTONOMIA no .env — a ideia é você trocar de
modo sem mexer em código depois que o time do Salesforce mostrar como os
usuários estão cadastrados:

- "dominio" : e-mail em DOMINIOS_INTERNOS  -> interno; qualquer outro -> marca.
- "perfil"  : Profile.Name em PERFIS_INTERNOS -> interno.
- "lista"   : Id/e-mail listado em ARQUIVO_USUARIOS_INTERNOS -> interno.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config

logger = logging.getLogger(__name__)

INTERNO = "interno"
MARCA = "marca"
DESCONHECIDO = "desconhecido"


@dataclass(frozen=True, slots=True)
class Executor:
    id_usuario: str
    nome: str
    email: str
    perfil: str
    origem: str  # INTERNO | MARCA | DESCONHECIDO

    @property
    def autonomo(self) -> bool:
        return self.origem == MARCA


def _carregar_lista(caminho: Path) -> set[str]:
    if not caminho.exists():
        logger.warning(
            "Arquivo de usuários internos não encontrado: %s "
            "(nenhum usuário será tratado como interno).",
            caminho,
        )
        return set()
    itens: set[str] = set()
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip().lower()
        if linha:
            itens.add(linha)
    return itens


class ClassificadorDeExecutor:
    def __init__(self, config: Config, usuarios: dict[str, dict[str, Any]]) -> None:
        self.config = config
        self.usuarios = usuarios
        self._lista_interna = (
            _carregar_lista(config.arquivo_usuarios_internos)
            if config.modo_autonomia == "lista"
            else set()
        )

    def classificar(self, id_usuario: str | None) -> Executor:
        if not id_usuario:
            return Executor("", "", "", "", DESCONHECIDO)

        dados = self.usuarios.get(id_usuario, {})
        nome = dados.get("nome", "")
        email = (dados.get("email") or "").lower()
        perfil = dados.get("perfil", "")

        origem = self._origem(id_usuario, email, perfil)
        return Executor(id_usuario, nome, email, perfil, origem)

    # ------------------------------------------------------------------ #
    def _origem(self, id_usuario: str, email: str, perfil: str) -> str:
        modo = self.config.modo_autonomia

        if modo == "dominio":
            if not email:
                return DESCONHECIDO
            dominio = email.rsplit("@", 1)[-1]
            return INTERNO if dominio in self.config.dominios_internos else MARCA

        if modo == "perfil":
            if not perfil:
                return DESCONHECIDO
            return INTERNO if perfil.lower() in self.config.perfis_internos else MARCA

        # modo == "lista"
        if not self._lista_interna:
            return DESCONHECIDO
        chaves = {id_usuario.lower(), email}
        return INTERNO if chaves & self._lista_interna else MARCA
