"""Chat interativo da Weely — Sprint 03.

Uso:
    python main.py                # sessão padrão
    python main.py minha_sessao   # nomeia a sessão (memória separada por sessão)

A memória da conversa é gerenciada pelo framework (SQLiteSession): cada turno é
persistido em weely_sessions.db e reenviado automaticamente ao modelo, sem
manipulação manual de listas de mensagens.
"""

import asyncio
import sys

from agents import InputGuardrailTripwireTriggered, Runner, SQLiteSession

from weely.agente import criar_agente
from weely.config import validar_credenciais
from weely.guardrails import MENSAGEM_BLOQUEIO


async def chat() -> None:
    validar_credenciais()

    session_id = sys.argv[1] if len(sys.argv) > 1 else "sessao_padrao"
    session = SQLiteSession(session_id, "weely_sessions.db")
    agente = criar_agente()

    print("Bem-vindo à Central de Atendimento do seu eletroposto! 🙂")
    print(f"(sessão: {session_id} — modelo: {agente.model})")
    print("A Weely está à disposição. Escreva 'sair' para encerrar.\n")

    while True:
        pergunta = input("Você: ").strip()
        if not pergunta:
            continue
        if pergunta.lower() == "sair":
            print("\nWeely: Até logo! Conte com a gente na gestão do seu eletroposto. ⚡")
            break

        try:
            resultado = await Runner.run(agente, pergunta, session=session)
            print(f"\nWeely: {resultado.final_output}\n")
        except InputGuardrailTripwireTriggered:
            print(f"\nWeely: {MENSAGEM_BLOQUEIO}\n")
        except Exception as erro:  # ex.: modelo indisponível, sem conexão
            print(f"\n[erro] Não foi possível obter resposta: {erro}\n")


if __name__ == "__main__":
    asyncio.run(chat())
