"""Versões do agente Weely avaliadas pelo pipeline da Sprint 04.

V1 — Sprint 2: réplica fiel do notebook Sprint2_ChatBot_IA.ipynb. O system prompt é lido
     da própria célula do notebook (sem cópia manual), chamada direta a chat.completions,
     histórico em lista, entrada convertida para minúsculas (como no notebook) e sem
     temperature explícita (padrão da API, 1.0).
V2 — Sprint 3 (versão final): OpenAI Agents SDK, guardrail de entrada, SQLiteSession,
     gpt-4o-mini com temperature 0.2.
V3 — Sprint 3 (variante): mesma arquitetura com gpt-5-nano (modelo de raciocínio, sem
     temperature), testada no relatorio_modelos.md da Sprint 3.

Todas expõem a mesma interface: nova_conversa() -> objeto com `await perguntar(texto)`,
que devolve um dicionário com resposta, bloqueio pelo guardrail, latência e tokens.
"""

import json
import time
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- V1
def prompt_sprint2() -> str:
    """Executa a célula de contexto do notebook da Sprint 2 e devolve o system prompt."""
    notebook = json.loads((RAIZ / "Sprint2_ChatBot_IA.ipynb").read_text(encoding="utf-8"))
    for celula in notebook["cells"]:
        fonte = "".join(celula["source"])
        if celula["cell_type"] == "code" and "msgs = [" in fonte and "ContextoDesafio" in fonte:
            escopo: dict = {}
            exec(fonte, escopo)          # célula só define ContextoDesafio e msgs
            return escopo["msgs"][0]["content"]
    raise RuntimeError("Célula do system prompt não encontrada no notebook da Sprint 2")


class ConversaSprint2:
    def __init__(self, cliente, modelo: str, system_prompt: str):
        self.cliente = cliente
        self.modelo = modelo
        self.msgs = [{"role": "system", "content": system_prompt}]

    async def perguntar(self, texto: str) -> dict:
        self.msgs.append({"role": "user", "content": texto.lower()})   # como no notebook
        inicio = time.perf_counter()
        resposta = await self.cliente.chat.completions.create(model=self.modelo, messages=self.msgs)
        latencia = time.perf_counter() - inicio
        conteudo = resposta.choices[0].message.content
        self.msgs.append({"role": "assistant", "content": conteudo})
        return {"resposta": conteudo, "bloqueado": False, "latencia_s": round(latencia, 2),
                "tokens": resposta.usage.total_tokens if resposta.usage else 0}


class VersaoSprint2:
    id = "V1"
    nome = "Sprint 2 — notebook (chat.completions manual)"
    modelo = "gpt-4o-mini"
    temperature = "padrão da API (1.0)"

    def __init__(self):
        from openai import AsyncOpenAI
        self.cliente = AsyncOpenAI()
        self.system_prompt = prompt_sprint2()

    def nova_conversa(self):
        return ConversaSprint2(self.cliente, self.modelo, self.system_prompt)


# --------------------------------------------------------------------------- V2 / V3
class ConversaSprint3:
    def __init__(self, agente, versao_id: str):
        from agents import SQLiteSession
        self.agente = agente
        # sessão em memória, isolada por caso: a memória é do framework, como na Sprint 3
        self.sessao = SQLiteSession(f"{versao_id}_{uuid.uuid4().hex}")

    async def perguntar(self, texto: str) -> dict:
        from agents import InputGuardrailTripwireTriggered, Runner
        from weely.guardrails import MENSAGEM_BLOQUEIO
        inicio = time.perf_counter()
        try:
            resultado = await Runner.run(self.agente, texto, session=self.sessao)
            uso = resultado.context_wrapper.usage
            return {"resposta": resultado.final_output, "bloqueado": False,
                    "latencia_s": round(time.perf_counter() - inicio, 2), "tokens": uso.total_tokens}
        except InputGuardrailTripwireTriggered:
            return {"resposta": MENSAGEM_BLOQUEIO, "bloqueado": True,
                    "latencia_s": round(time.perf_counter() - inicio, 2), "tokens": 0}


class VersaoSprint3:
    def __init__(self, versao_id: str, nome: str, modelo: str, temperature):
        from weely.agente import criar_agente
        self.id = versao_id
        self.nome = nome
        self.modelo = modelo
        self.temperature = temperature if temperature is not None else "não suportada"
        self.agente = criar_agente(model=modelo, temperature=temperature)

    def nova_conversa(self):
        return ConversaSprint3(self.agente, self.id)


def carregar_versao(versao_id: str):
    if versao_id == "V1":
        return VersaoSprint2()
    if versao_id == "V2":
        return VersaoSprint3("V2", "Sprint 3 — Agents SDK + guardrail (final)", "gpt-4o-mini", 0.2)
    if versao_id == "V3":
        return VersaoSprint3("V3", "Sprint 3 — Agents SDK + guardrail (variante gpt-5-nano)", "gpt-5-nano", None)
    raise ValueError(f"Versão desconhecida: {versao_id}")


VERSOES = ["V1", "V2", "V3"]
