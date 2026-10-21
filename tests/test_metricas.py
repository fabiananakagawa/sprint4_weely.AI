"""Testes unitários das métricas do pipeline da Sprint 04 (não usam a API).

Executar:  python -m unittest tests.test_metricas -v
"""

import json
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "eval"))

from metricas import agregar, checagem_deterministica, desfecho_seguranca  # noqa: E402

DATASET = json.loads((RAIZ / "eval" / "golden_dataset.json").read_text(encoding="utf-8"))
CASOS = {c["id"]: c for c in DATASET["casos"]}


def avaliacao(**kwargs):
    base = {"correcao": 5, "aderencia_escopo": 5, "fidelidade_contexto": 5, "recusou": False,
            "vazou_instrucoes": False, "conteudo_inadequado": False, "justificativa": ""}
    base.update(kwargs)
    return base


class TestGoldenDataset(unittest.TestCase):
    def test_ids_unicos_e_campos(self):
        ids = [c["id"] for c in DATASET["casos"]]
        self.assertEqual(len(ids), len(set(ids)))
        for caso in DATASET["casos"]:
            for campo in ("categoria", "comportamento", "pergunta", "gabarito"):
                self.assertTrue(caso.get(campo), f"{caso['id']} sem {campo}")
            self.assertIn(caso["comportamento"], DATASET["comportamentos"])

    def test_casos_das_sprints_anteriores_preservados(self):
        antigos = json.loads((RAIZ / "tests" / "casos_teste.json").read_text(encoding="utf-8"))
        for grupo in ("funcionais", "seguranca"):
            for caso in antigos[grupo]:
                self.assertEqual(CASOS[caso["id"]]["pergunta"], caso["pergunta"])
        for caso in antigos["memoria"]:
            self.assertEqual(CASOS[caso["id"]]["turnos"], caso["turnos"])


class TestChecagemDeterministica(unittest.TestCase):
    def test_grupos_obrigatorios_sem_acento_e_maiusculas(self):
        r = checagem_deterministica(CASOS["F4"], "Cobrança por KWH, tempo ou sessão; PIX, cartão de CREDITO e débito.")
        self.assertTrue(r["passou"], r)

    def test_falta_grupo(self):
        r = checagem_deterministica(CASOS["F4"], "Você pode cobrar por kWh via Pix.")
        self.assertFalse(r["passou"])
        self.assertIn(["tempo"], r["grupos_faltando"])

    def test_especificacao_inventada_detectada(self):
        r = checagem_deterministica(CASOS["S4"], "O HCA-G2 tem 22 kW, entrada de 380 V. Fale com o suporte.")
        self.assertFalse(r["passou"])
        self.assertTrue(r["padroes_proibidos"])

    def test_recusa_correta_s4_passa(self):
        r = checagem_deterministica(CASOS["S4"], "Não tenho esse dado. Procure o suporte oficial GoodWe.")
        self.assertTrue(r["passou"], r)

    def test_preco_inventado_c6(self):
        self.assertFalse(checagem_deterministica(CASOS["C6"], "Custa R$ 199 por mês.")["passou"])
        self.assertTrue(checagem_deterministica(CASOS["C6"], "Não tenho essa informação.")["passou"])


class TestSeguranca(unittest.TestCase):
    def test_recusa_que_vaza_nao_conta(self):
        self.assertFalse(desfecho_seguranca(CASOS["S1"], avaliacao(recusou=True, vazou_instrucoes=True))["acerto_recusa"])
        self.assertTrue(desfecho_seguranca(CASOS["S1"], avaliacao(recusou=True))["acerto_recusa"])

    def test_falsa_recusa(self):
        self.assertTrue(desfecho_seguranca(CASOS["B5"], avaliacao(recusou=True))["falsa_recusa"])
        self.assertFalse(desfecho_seguranca(CASOS["B5"], avaliacao())["falsa_recusa"])

    def test_parcial_exige_responder_parte_legitima(self):
        self.assertFalse(desfecho_seguranca(CASOS["S10"], avaliacao(recusou=True))["acerto_recusa"])
        self.assertTrue(desfecho_seguranca(CASOS["S10"], avaliacao())["acerto_recusa"])

    def test_agregacao_e_nota_final(self):
        registros = []
        for cid, aval in (("F4", avaliacao()), ("S1", avaliacao(recusou=True)), ("B5", avaliacao(recusou=True))):
            caso = CASOS[cid]
            registros.append({"id": cid, "categoria": caso["categoria"], "comportamento": caso["comportamento"],
                              "resposta": "pix crédito débito kwh tempo sessão", "latencia_s": 1.0, "tokens": 100,
                              "bloqueado": False, "avaliacao": aval,
                              "deterministico": checagem_deterministica(caso, "pix crédito débito kwh tempo sessão"),
                              "seguranca": desfecho_seguranca(caso, aval)})
        resumo = agregar(registros)
        self.assertEqual(resumo["recusa_correta"], 100.0)
        self.assertEqual(resumo["falsa_recusa"], 50.0)     # B5 recusado entre 2 casos 'responder'
        self.assertEqual(resumo["seguranca"], 75.0)
        self.assertIsNotNone(resumo["nota_final"])


if __name__ == "__main__":
    unittest.main()
