"""Carrega credenciais do arquivo .env (nunca hardcoded no código)."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def validar_credenciais() -> None:
    """Encerra com mensagem clara se a chave da API não estiver configurada."""
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit(
            "Erro: OPENAI_API_KEY não encontrada.\n"
            "Copie .env.example para .env e preencha sua chave:\n"
            "  cp .env.example .env"
        )


# Modelo padrão da versão final (escolhido após os experimentos do relatorio_modelos.md)
MODELO_PADRAO = os.getenv("WEELY_MODEL", "gpt-4o-mini")
# Modelos de raciocínio (família gpt-5) não aceitam temperature — use None nesse caso.
_temp = os.getenv("WEELY_TEMPERATURE", "0.2")
TEMPERATURE_PADRAO = None if _temp.lower() == "none" else float(_temp)

# Modelo barato usado nos agentes auxiliares (guardrail e juiz de avaliação)
MODELO_AUXILIAR = "gpt-4o-mini"
