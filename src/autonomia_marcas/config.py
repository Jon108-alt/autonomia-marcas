"""Configuração da aplicação, lida do arquivo .env.

Usamos dataclasses (e não dicionários soltos) porque os campos ficam explícitos,
com type hints e validação em um único lugar: se faltar uma variável no .env o
erro aparece na largada, com o nome exato da variável, em vez de estourar um
KeyError no meio da consulta ao Salesforce.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


class ErroDeConfiguracao(RuntimeError):
    """Configuração ausente ou inválida no .env."""


# --------------------------------------------------------------------------- #
# Etapas do fluxo
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Etapa:
    """Uma das quatro etapas do fluxo do pedido.

    campo_data      : campo de data/hora que marca a conclusão da etapa.
    campo_executor  : campo que aponta o usuário que executou (lookup de User).
    campo_condicao  : opcional; campo booleano que precisa ser True para a etapa
                      contar como concluída (ex.: Download__c).
    """

    chave: str
    rotulo: str
    campo_data: str
    campo_executor: str
    campo_condicao: str | None = None

    @property
    def campos_soql(self) -> list[str]:
        campos = [self.campo_data, self.campo_executor]
        if self.campo_condicao:
            campos.append(self.campo_condicao)
        return campos


ETAPAS_PADRAO: dict[str, dict[str, str]] = {
    "recebimento_po": {
        "rotulo": "Recebimento/confirmação do PO",
        "campo_data": "PODownloadDate__c",
        "campo_executor": "PODownloadBy__c",
        "campo_condicao": "Download__c",
    },
    "atualizacao_status": {
        "rotulo": "Atualização do status",
        "campo_data": "EvaluationDate__c",
        "campo_executor": "EvaluationBy__c",
    },
    "upload_nf": {
        "rotulo": "Upload da nota fiscal",
        "campo_data": "NFSentDate__c",
        "campo_executor": "NFSentBy__c",
    },
    "agendamento_coleta": {
        "rotulo": "Agendamento da coleta",
        "campo_data": "PickupScheduledDate__c",
        "campo_executor": "CreatedById",
    },
}


# --------------------------------------------------------------------------- #
# Configuração principal
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class Config:
    # --- Salesforce ---
    sf_dominio: str
    sf_versao_api: str
    sf_modo_auth: str
    sf_client_id: str
    sf_client_secret: str
    sf_usuario: str
    sf_senha: str
    sf_token: str

    # --- Objeto e campos ---
    sf_objeto: str
    campo_marca: str
    campo_id_pedido: str
    campo_status_nf: str

    # --- Backoffice (aprovação da NF) ---
    campo_nf_enviada: str
    campo_avaliacao: str
    campo_aprovacao: str

    etapas: list[Etapa]

    # --- Regra de autonomia ---
    modo_autonomia: str
    dominios_internos: list[str]
    perfis_internos: list[str]
    arquivo_usuarios_internos: Path

    # --- Janela de dados e saída ---
    data_inicio_padrao: date
    output_dir: Path
    docs_dir: Path

    limiar_autonomo: float = 90.0
    limiar_parcial: float = 50.0

    # ----------------------------------------------------------------- #
    @classmethod
    def carregar(cls, caminho_env: str | os.PathLike[str] | None = None) -> "Config":
        load_dotenv(caminho_env or ".env", override=False)

        def obrigatorio(nome: str) -> str:
            valor = os.getenv(nome, "").strip()
            if not valor:
                raise ErroDeConfiguracao(
                    f"Variável {nome} não está preenchida no .env."
                )
            return valor

        def opcional(nome: str, padrao: str = "") -> str:
            return os.getenv(nome, padrao).strip()

        def lista(nome: str, padrao: str = "") -> list[str]:
            bruto = opcional(nome, padrao)
            return [item.strip().lower() for item in bruto.split(",") if item.strip()]

        modo_auth = opcional("SF_AUTH_MODE", "client_credentials").lower()
        if modo_auth not in {"client_credentials", "password"}:
            raise ErroDeConfiguracao(
                "SF_AUTH_MODE deve ser 'client_credentials' ou 'password'."
            )

        etapas_bruto = opcional("SF_ETAPAS")
        try:
            etapas_dict = json.loads(etapas_bruto) if etapas_bruto else ETAPAS_PADRAO
        except json.JSONDecodeError as exc:
            raise ErroDeConfiguracao(f"SF_ETAPAS não é um JSON válido: {exc}") from exc

        etapas = [
            Etapa(
                chave=chave,
                rotulo=dados.get("rotulo", chave),
                campo_data=dados["campo_data"],
                campo_executor=dados["campo_executor"],
                campo_condicao=dados.get("campo_condicao") or None,
            )
            for chave, dados in etapas_dict.items()
        ]
        if not etapas:
            raise ErroDeConfiguracao("SF_ETAPAS não definiu nenhuma etapa.")

        modo_autonomia = opcional("MODO_AUTONOMIA", "dominio").lower()
        if modo_autonomia not in {"dominio", "perfil", "lista"}:
            raise ErroDeConfiguracao(
                "MODO_AUTONOMIA deve ser 'dominio', 'perfil' ou 'lista'."
            )

        data_inicio = opcional("DATA_INICIO_PADRAO", "2026-08-01")
        try:
            data_inicio_padrao = date.fromisoformat(data_inicio)
        except ValueError as exc:
            raise ErroDeConfiguracao(
                "DATA_INICIO_PADRAO precisa estar no formato AAAA-MM-DD."
            ) from exc

        # Em modo demo não exigimos credenciais: o pipeline nem chega a chamar o SF.
        exigir = obrigatorio if os.getenv("MODO_DEMO", "0") != "1" else opcional

        return cls(
            sf_dominio=exigir("SF_DOMAIN").rstrip("/"),
            sf_versao_api=opcional("SF_API_VERSION", "v61.0"),
            sf_modo_auth=modo_auth,
            sf_client_id=opcional("SF_CLIENT_ID"),
            sf_client_secret=opcional("SF_CLIENT_SECRET"),
            sf_usuario=opcional("SF_USERNAME"),
            sf_senha=opcional("SF_PASSWORD"),
            sf_token=opcional("SF_SECURITY_TOKEN"),
            sf_objeto=opcional("SF_OBJETO", "OrderExportReport__c"),
            campo_marca=opcional("SF_CAMPO_MARCA", "Brand__c"),
            campo_id_pedido=opcional("SF_CAMPO_ID_PEDIDO", "Name"),
            campo_status_nf=opcional("SF_CAMPO_STATUS_NF", "InvoiceStatus__c"),
            campo_nf_enviada=opcional("SF_CAMPO_NF_ENVIADA", "NFSentDate__c"),
            campo_avaliacao=opcional("SF_CAMPO_AVALIACAO", "EvaluationDate__c"),
            campo_aprovacao=opcional("SF_CAMPO_APROVACAO", "InvoiceapprovalDate__c"),
            etapas=etapas,
            modo_autonomia=modo_autonomia,
            dominios_internos=lista("DOMINIOS_INTERNOS", "privalia.com,veepee.com"),
            perfis_internos=lista("PERFIS_INTERNOS"),
            arquivo_usuarios_internos=Path(
                opcional("ARQUIVO_USUARIOS_INTERNOS", "config/usuarios_internos.txt")
            ),
            data_inicio_padrao=data_inicio_padrao,
            output_dir=Path(opcional("OUTPUT_DIR", "output")),
            docs_dir=Path(opcional("DOCS_DIR", "docs")),
            limiar_autonomo=float(opcional("LIMIAR_AUTONOMO", "90")),
            limiar_parcial=float(opcional("LIMIAR_PARCIAL", "50")),
        )

    # ----------------------------------------------------------------- #
    @property
    def url_api(self) -> str:
        return f"{self.sf_dominio}/services/data/{self.sf_versao_api}"

    def campos_consulta(self) -> list[str]:
        """Todos os campos que a SOQL precisa trazer, sem duplicatas."""
        campos: list[str] = [
            "Id",
            self.campo_id_pedido,
            self.campo_marca,
            self.campo_status_nf,
            "CreatedDate",
            "CreatedById",
            self.campo_nf_enviada,
            self.campo_avaliacao,
            self.campo_aprovacao,
        ]
        for etapa in self.etapas:
            campos.extend(etapa.campos_soql)
        # dict.fromkeys preserva a ordem e remove duplicatas (Python 3.7+)
        return list(dict.fromkeys(c for c in campos if c))


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)
