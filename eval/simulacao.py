"""Agente e juiz falsos para testar o pipeline de ponta a ponta sem chamar a API.

Usado por `python eval/run_eval.py --simular`. As notas geradas aqui NÃO são resultados:
servem só para verificar que geração, julgamento, agregação e relatório funcionam.
"""

import random

from metricas import checagem_deterministica


class ConversaFalsa:
    def __init__(self, versao_id):
        self.versao_id = versao_id

    async def perguntar(self, texto):
        bloqueado = self.versao_id != "V1" and "ignore" in texto.lower()
        return {"resposta": "Resposta simulada sobre a plataforma ChargeGrid: Pix, crédito, débito, kWh, tempo, sessão.",
                "bloqueado": bloqueado, "latencia_s": round(random.uniform(0.5, 3.0), 2), "tokens": 1500}


class VersaoFalsa:
    def __init__(self, versao_id):
        self.id = versao_id
        self.nome = f"{versao_id} (simulada)"
        self.modelo = "simulado"
        self.temperature = None

    def nova_conversa(self):
        return ConversaFalsa(self.id)


async def julgar_falso(_juiz, caso, resposta):
    det = checagem_deterministica(caso, resposta)
    nota = 5 if det["passou"] else 3
    return {"correcao": nota, "aderencia_escopo": random.choice([4, 5]), "fidelidade_contexto": random.choice([4, 5]),
            "recusou": caso["comportamento"] == "recusar" and random.random() < 0.8,
            "vazou_instrucoes": False, "conteudo_inadequado": False, "justificativa": "simulação"}
