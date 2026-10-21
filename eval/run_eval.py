"""Pipeline de avaliação sistemática da Weely — Sprint 04.

Executa o golden dataset (eval/golden_dataset.json) contra as versões do agente, julga
cada resposta com LLM as a judge + checagens determinísticas e grava:
  eval/resultados/respostas_<versão>.json   respostas brutas (texto, latência, tokens)
  eval/resultados/avaliacao_<versão>.json   respostas + notas do(s) juiz(es) + métricas
  eval/resultados/resumo.json / resumo.md   tabela comparativa por versão e por métrica

Uso:
  python eval/run_eval.py                          # V1, V2 e V3 com juiz gpt-5-nano e 2º juiz gpt-4o-mini
  python eval/run_eval.py --versoes V1 V2          # só algumas versões
  python eval/run_eval.py --rejulgar               # reaproveita respostas gravadas, só rejulga
  python eval/run_eval.py --casos F1 S4 M3         # subconjunto de casos
  python eval/run_eval.py --offline-sprint3        # sem API: métricas determinísticas sobre as
                                                   # respostas já salvas na Sprint 3
  python eval/run_eval.py --simular                # sem API: testa o pipeline com agente/juiz falsos
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "eval"))

from metricas import (PESOS, agregar, agregar_por_categoria, checagem_deterministica,  # noqa: E402
                      concordancia, desfecho_seguranca)

PASTA = RAIZ / "eval"
SAIDA = PASTA / "resultados"
DATASET = json.loads((PASTA / "golden_dataset.json").read_text(encoding="utf-8"))

# resultados da Sprint 3 (avaliação anterior) usados na comparação
SPRINT3 = {
    "V1": ("tests/resultados/baseline_sprint2.json", "réplica da Sprint 2 feita na Sprint 3 (gpt-4o-mini, t=0.7)"),
    "V2": ("tests/resultados/resultados_gpt-4o-mini_t0.2.json", "Sprint 3 final (gpt-4o-mini, t=0.2)"),
    "V3": ("tests/resultados/resultados_gpt-5-nano.json", "Sprint 3 variante (gpt-5-nano)"),
}


def casos_selecionados(ids):
    casos = DATASET["casos"]
    return [c for c in casos if not ids or c["id"] in ids]


# ----------------------------------------------------------------------------- execução
async def gerar_respostas(versao, casos, concorrencia):
    limite = asyncio.Semaphore(concorrencia)

    async def um_caso(caso):
        async with limite:
            conversa = versao.nova_conversa()
            try:
                for turno in caso.get("turnos", []):
                    await conversa.perguntar(turno)
                saida = await conversa.perguntar(caso["pergunta"])
                print(f"  [{versao.id}] {caso['id']:<4} {saida['latencia_s']:5.1f}s"
                      f"{'  (bloqueado pelo guardrail)' if saida['bloqueado'] else ''}", flush=True)
                return {"id": caso["id"], **saida}
            except Exception as erro:   # registra e segue: um caso não derruba a execução
                print(f"  [{versao.id}] {caso['id']:<4} ERRO: {erro}", flush=True)
                return {"id": caso["id"], "erro": str(erro), "resposta": "", "bloqueado": False,
                        "latencia_s": None, "tokens": 0}

    return await asyncio.gather(*(um_caso(c) for c in casos))


async def julgar_respostas(respostas, casos, juiz, juiz2, concorrencia):
    from juiz import julgar
    por_id = {c["id"]: c for c in casos}
    limite = asyncio.Semaphore(concorrencia)

    async def um(resposta):
        caso = por_id[resposta["id"]]
        registro = {**resposta, "categoria": caso["categoria"], "comportamento": caso["comportamento"],
                    "pergunta": caso["pergunta"], "turnos": caso.get("turnos", []),
                    "deterministico": checagem_deterministica(caso, resposta["resposta"])}
        if resposta.get("erro"):
            return registro
        async with limite:
            try:
                registro["avaliacao"] = await julgar(juiz, caso, resposta["resposta"])
                registro["seguranca"] = desfecho_seguranca(caso, registro["avaliacao"])
                if juiz2:
                    registro["avaliacao_juiz2"] = await julgar(juiz2, caso, resposta["resposta"])
            except Exception as erro:
                registro["erro_juiz"] = str(erro)
                print(f"  juiz falhou em {caso['id']}: {erro}", flush=True)
        return registro

    return await asyncio.gather(*(um(r) for r in respostas))


# ----------------------------------------------------------------------------- comparação Sprint 3
def comparar_sprint3(avaliacoes: dict) -> dict:
    """Confronta, caso a caso, a avaliação da Sprint 3 com o pipeline da Sprint 4."""
    tabela = {}
    for versao_id, registros in avaliacoes.items():
        arquivo, descricao = SPRINT3[versao_id]
        caminho = RAIZ / arquivo
        if not caminho.exists():
            continue
        antigo = json.loads(caminho.read_text(encoding="utf-8"))
        anteriores = {}
        for grupo in ("funcionais", "memoria", "seguranca"):
            for caso in antigo.get(grupo, []):
                anteriores[caso["id"]] = caso
        linhas = []
        for r in registros:
            if r["id"] not in anteriores or not r.get("avaliacao"):
                continue
            a = anteriores[r["id"]]
            sprint3 = f"{a['nota']}/10" if "nota" in a else ("adequado" if a.get("adequado") else "INADEQUADO")
            if r["comportamento"] == "recusar":
                sprint4 = "adequado" if r["seguranca"]["acerto_recusa"] else "INADEQUADO"
                concorda = sprint4 == sprint3
            else:
                nota4 = r["avaliacao"]["correcao"]
                sprint4 = f"correção {nota4}/5"
                nota3 = a.get("nota", 10 if a.get("adequado") else 0)
                concorda = (nota3 >= 8) == (nota4 >= 4)   # "bom" em ambas as escalas
            linhas.append({"id": r["id"], "sprint3": sprint3, "sprint4": sprint4, "concorda": concorda,
                           "justificativa_sprint3": a.get("justificativa") or a.get("analise", ""),
                           "justificativa_sprint4": r["avaliacao"]["justificativa"]})
        tabela[versao_id] = {"referencia_sprint3": descricao, "casos": linhas,
                             "concordancia_%": round(100 * sum(l["concorda"] for l in linhas) / len(linhas), 1)
                             if linhas else None}
    return tabela


# ----------------------------------------------------------------------------- relatório
METRICAS_TABELA = [
    ("correcao", "Correção (0–100)"), ("aderencia_escopo", "Aderência ao escopo GoodWe"),
    ("fidelidade_contexto", "Fidelidade ao contexto"), ("recusa_correta", "Recusa correta (segurança) %"),
    ("falsa_recusa", "Falsa recusa % (↓ melhor)"), ("seguranca", "Segurança balanceada"),
    ("deterministico", "Checagens determinísticas %"), ("vazamentos", "Vazamentos de instruções (nº)"),
    ("conteudo_inadequado", "Conteúdo inadequado (nº)"), ("bloqueios_guardrail", "Bloqueios do guardrail (nº)"),
    ("latencia_media_s", "Latência média (s)"), ("latencia_p95_s", "Latência p95 (s)"),
    ("tokens_medios", "Tokens por resposta"), ("nota_final", "**NOTA FINAL (0–100)**"),
]


def gerar_markdown(resumo: dict) -> str:
    versoes = list(resumo["versoes"].keys())
    linhas = [f"# Resultados do pipeline de avaliação — {resumo['gerado_em']}", "",
              f"Golden dataset: {resumo['casos']} casos · juiz principal: `{resumo['juiz']}`"
              + (f" · 2º juiz: `{resumo['juiz2']}`" if resumo.get("juiz2") else ""), "",
              "| Métrica | " + " | ".join(f"{v} — {resumo['versoes'][v]['nome']}" for v in versoes) + " |",
              "|---|" + "---|" * len(versoes)]
    for chave, rotulo in METRICAS_TABELA:
        valores = [resumo["versoes"][v]["metricas"].get(chave) for v in versoes]
        linhas.append(f"| {rotulo} | " + " | ".join("—" if x is None else str(x) for x in valores) + " |")
    linhas += ["", f"Pesos da nota final: " + ", ".join(f"{k} {int(p * 100)}%" for k, p in PESOS.items()), ""]
    linhas += ["## Nota por categoria", "", "| Categoria | " + " | ".join(versoes) + " |",
               "|---|" + "---|" * len(versoes)]
    categorias = sorted({c for v in versoes for c in resumo["versoes"][v]["por_categoria"]})
    for categoria in categorias:
        valores = []
        for v in versoes:
            m = resumo["versoes"][v]["por_categoria"].get(categoria, {})
            def fmt(x):
                return "—" if x is None else x
            valores.append(f"corr. {fmt(m.get('correcao'))} · seg. {fmt(m.get('recusa_correta'))} · det. {fmt(m.get('deterministico'))}")
        linhas.append(f"| {categoria} | " + " | ".join(valores) + " |")
    if resumo.get("concordancia_juizes"):
        linhas += ["", "## Concordância entre juízes", ""]
        for v in versoes:
            c = resumo["concordancia_juizes"].get(v)
            if c:
                linhas.append(f"- **{v}**: correção igual em {c['correcao']['igual_%']}% (±1 ponto em "
                              f"{c['correcao']['ate_1_ponto_%']}%); fidelidade ±1 em "
                              f"{c['fidelidade_contexto']['ate_1_ponto_%']}%; veredito de recusa igual em "
                              f"{c['recusou_igual_%']}%")
    if resumo.get("comparacao_sprint3"):
        linhas += ["", "## Comparação com a avaliação da Sprint 3 (casos F1–F5, M1–M2, S1–S7)", ""]
        for v, dados in resumo["comparacao_sprint3"].items():
            linhas += [f"### {v} × {dados['referencia_sprint3']} — concordância {dados['concordancia_%']}%", "",
                       "| Caso | Sprint 3 | Sprint 4 (pipeline) | Concorda? |", "|---|---|---|---|"]
            for l in dados["casos"]:
                linhas.append(f"| {l['id']} | {l['sprint3']} | {l['sprint4']} | {'sim' if l['concorda'] else '**não**'} |")
            linhas.append("")
    return "\n".join(linhas) + "\n"


# ----------------------------------------------------------------------------- modo offline
def offline_sprint3():
    """Sem chamar a API: aplica as checagens determinísticas às respostas salvas na Sprint 3."""
    por_id = {c["id"]: c for c in DATASET["casos"]}
    print("Modo offline — checagens determinísticas sobre as respostas gravadas na Sprint 3\n")
    for versao_id, (arquivo, descricao) in SPRINT3.items():
        dados = json.loads((RAIZ / arquivo).read_text(encoding="utf-8"))
        registros = []
        for grupo in ("funcionais", "memoria", "seguranca"):
            for antigo in dados.get(grupo, []):
                caso = por_id[antigo["id"]]
                det = checagem_deterministica(caso, antigo["resposta"])
                registros.append({"id": caso["id"], "det": det})
        aprovados = sum(r["det"]["passou"] for r in registros)
        print(f"{versao_id} ({descricao}): {aprovados}/{len(registros)} casos passaram")
        for r in registros:
            if not r["det"]["passou"]:
                print(f"   {r['id']}: faltou {r['det']['grupos_faltando']} | proibido {r['det']['padroes_proibidos']}")


# ----------------------------------------------------------------------------- main
async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--versoes", nargs="+", default=["V1", "V2", "V3"])
    parser.add_argument("--casos", nargs="+", default=None)
    parser.add_argument("--juiz", default="gpt-5-nano")
    parser.add_argument("--juiz2", default="gpt-4o-mini", help="segundo juiz para medir concordância ('' desliga)")
    parser.add_argument("--concorrencia", type=int, default=4)
    parser.add_argument("--rejulgar", action="store_true", help="reaproveita respostas gravadas")
    parser.add_argument("--offline-sprint3", action="store_true")
    parser.add_argument("--simular", action="store_true", help="agente e juiz falsos (teste sem API)")
    args = parser.parse_args()
    global SAIDA

    if args.offline_sprint3:
        offline_sprint3()
        return

    if args.simular:
        import juiz as modulo_juiz
        import simulacao
        modulo_juiz.julgar = simulacao.julgar_falso
        def criar_juiz(_modelo):
            return None
        carregar_versao = simulacao.VersaoFalsa
        SAIDA = PASTA / "resultados_simulacao"
    else:
        from weely.config import validar_credenciais
        from juiz import criar_juiz
        from versoes import carregar_versao
        validar_credenciais()
    SAIDA.mkdir(parents=True, exist_ok=True)
    casos = casos_selecionados(args.casos)
    juiz = criar_juiz(args.juiz)
    juiz2 = criar_juiz(args.juiz2) if args.juiz2 else None
    if args.simular:
        juiz2 = "simulado" if args.juiz2 else None

    resumo = {"gerado_em": datetime.now().isoformat(timespec="seconds"), "casos": len(casos),
              "juiz": args.juiz, "juiz2": args.juiz2 or None, "versoes": {}, "concordancia_juizes": {}}
    avaliacoes = {}
    for versao_id in args.versoes:
        versao = carregar_versao(versao_id)
        arquivo_respostas = SAIDA / f"respostas_{versao_id}.json"
        if args.rejulgar and arquivo_respostas.exists():
            respostas = json.loads(arquivo_respostas.read_text(encoding="utf-8"))["respostas"]
            respostas = [r for r in respostas if r["id"] in {c["id"] for c in casos}]
            print(f"\n== {versao_id}: reaproveitando {len(respostas)} respostas gravadas")
        else:
            print(f"\n== {versao_id}: {versao.nome} — gerando respostas", flush=True)
            respostas = await gerar_respostas(versao, casos, args.concorrencia)
            arquivo_respostas.write_text(json.dumps(
                {"versao": versao_id, "nome": versao.nome, "modelo": versao.modelo,
                 "temperature": versao.temperature, "gerado_em": resumo["gerado_em"], "respostas": respostas},
                ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"== {versao_id}: julgando ({args.juiz}{' + ' + args.juiz2 if args.juiz2 else ''})", flush=True)
        registros = await julgar_respostas(respostas, casos, juiz, juiz2, args.concorrencia)
        avaliacoes[versao_id] = registros
        (SAIDA / f"avaliacao_{versao_id}.json").write_text(
            json.dumps({"versao": versao_id, "juiz": args.juiz, "juiz2": args.juiz2, "registros": registros},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        resumo["versoes"][versao_id] = {"nome": versao.nome, "modelo": versao.modelo,
                                        "temperature": versao.temperature, "metricas": agregar(registros),
                                        "por_categoria": agregar_por_categoria(registros)}
        resumo["concordancia_juizes"][versao_id] = concordancia(registros)

    resumo["comparacao_sprint3"] = comparar_sprint3(avaliacoes)
    (SAIDA / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = gerar_markdown(resumo)
    (SAIDA / "resumo.md").write_text(markdown, encoding="utf-8")
    print("\n" + markdown)


if __name__ == "__main__":
    asyncio.run(main())
