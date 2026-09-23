"""Gera dados fictícios no mesmo formato que o Salesforce devolve.

Serve para você ver o painel funcionando antes de receber as credenciais, e
para os testes rodarem sem rede. Nada aqui é usado no modo real.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import Config

MARCAS = [
    ("Alpha Moda", 0.95),
    ("Bravo Casa", 0.82),
    ("Cedro Kids", 0.61),
    ("Delta Sports", 0.44),
    ("Eterna Beleza", 0.28),
    ("Fluxo Denim", 0.73),
]

USUARIOS_MARCA = [
    ("005DEMO001", "Ana Souza", "ana@alphamoda.com.br"),
    ("005DEMO002", "Bruno Lima", "bruno@bravocasa.com.br"),
    ("005DEMO003", "Carla Reis", "carla@cedrokids.com.br"),
]
USUARIOS_INTERNOS = [
    ("005DEMO900", "Backoffice Privalia", "backoffice@privalia.com"),
    ("005DEMO901", "Operações Privalia", "ops@privalia.com"),
]

STATUS_NF = ["Pendente", "Associado", "Em avaliação", "Aprovado", "Recusado"]


def gerar_registros(config: Config, quantidade: int = 600, semente: int = 7) -> list[dict[str, Any]]:
    aleatorio = random.Random(semente)
    inicio = datetime(2026, 8, 1, tzinfo=timezone.utc)
    hoje = datetime.now(timezone.utc)
    dias = max((hoje - inicio).days, 1)

    registros: list[dict[str, Any]] = []
    for indice in range(quantidade):
        marca, propensao = aleatorio.choice(MARCAS)
        criado = inicio + timedelta(
            days=aleatorio.randint(0, dias - 1), hours=aleatorio.randint(8, 18)
        )

        registro: dict[str, Any] = {
            "Id": f"a0X{indice:07d}",
            config.campo_id_pedido: f"PO-{10000 + indice}",
            config.campo_marca: marca,
            "CreatedDate": criado.isoformat(),
            "CreatedById": _sortear_usuario(aleatorio, propensao)[0],
        }

        momento = criado
        for etapa in config.etapas:
            if aleatorio.random() > 0.88:  # etapa ainda não concluída
                break
            momento += timedelta(hours=aleatorio.uniform(2, 60))
            usuario = _sortear_usuario(aleatorio, propensao)
            registro[etapa.campo_data] = momento.isoformat()
            registro[etapa.campo_executor] = usuario[0]
            if etapa.campo_condicao:
                registro[etapa.campo_condicao] = True

        # --- backoffice: envio -> avaliação -> aprovação ---
        enviada = registro.get(config.campo_nf_enviada)
        if enviada:
            base = datetime.fromisoformat(enviada)
            # marcas piores no processo também demoram mais no backoffice
            fator = 1.0 + (1.0 - propensao) * 1.8
            avaliada = base + timedelta(hours=aleatorio.uniform(2, 40) * fator)
            registro[config.campo_avaliacao] = avaliada.isoformat()
            if aleatorio.random() < 0.78:
                aprovada = avaliada + timedelta(hours=aleatorio.uniform(3, 72) * fator)
                if aprovada < hoje:
                    registro[config.campo_aprovacao] = aprovada.isoformat()
                    registro[config.campo_status_nf] = "Aprovado"
            registro.setdefault(
                config.campo_status_nf, aleatorio.choice(STATUS_NF[:3])
            )

        registros.append(registro)

    return registros


def _sortear_usuario(aleatorio: random.Random, propensao: float) -> tuple[str, str, str]:
    if aleatorio.random() < propensao:
        return aleatorio.choice(USUARIOS_MARCA)
    return aleatorio.choice(USUARIOS_INTERNOS)


def usuarios_demo() -> dict[str, dict[str, str]]:
    usuarios: dict[str, dict[str, str]] = {}
    for id_usuario, nome, email in USUARIOS_MARCA:
        usuarios[id_usuario] = {
            "nome": nome, "email": email, "perfil": "Parceiro", "tipo": "PowerPartner"
        }
    for id_usuario, nome, email in USUARIOS_INTERNOS:
        usuarios[id_usuario] = {
            "nome": nome, "email": email, "perfil": "Backoffice", "tipo": "Standard"
        }
    return usuarios
