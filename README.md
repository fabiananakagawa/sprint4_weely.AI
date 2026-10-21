A Weely é a inteligência artificial conversacional da plataforma ChargeGrid Intelligence, desenvolvida para auxiliar gestores de estabelecimentos comerciais na operação de infraestrutura de carregamento veicular.

A proposta da solução é transformar dados operacionais, energéticos e financeiros em informações acessíveis por meio de linguagem natural, permitindo que o gestor converse diretamente com os dados da operação.

A IA atua como suporte analítico e consultivo, auxiliando em temas como:

tarifação dinâmica;

consumo energético;

ocupação dos carregadores;

faturamento;

utilização de energia solar;

indicadores operacionais;

alertas e falhas técnicas;

análise de desempenho da operação.

A Weely utiliza os dados consolidados pela ChargeGrid Intelligence para gerar insights estratégicos, responder perguntas em tempo real e apoiar a tomada de decisão do estabelecimento.

A solução foi concebida como uma interface inteligente de analytics conversacional aplicada ao contexto de mobilidade elétrica e gestão energética.

---

# Sprint 03 — Arquitetura com framework de agentes

O núcleo conversacional foi refatorado do notebook da Sprint 2 (chamadas manuais
ao `chat.completions`) para uma aplicação local construída sobre o
**OpenAI Agents SDK**.

## Estrutura

```
weely/
  agente.py      # Agente principal Weely (Agent + ModelSettings)
  guardrails.py  # Guardrail de entrada (prompt injection / fora de escopo)
  contexto.py    # Base de conhecimento ChargeGrid Intelligence
  config.py      # Credenciais (.env) e modelo padrão
main.py          # Chat interativo com memória por sessão (SQLiteSession)
tests/
  casos_teste.md / casos_teste.json   # Casos funcionais, de memória e de segurança
  run_tests.py                        # Executor + LLM-as-judge + métricas
relatorio_modelos.md                  # Comparação entre modelos/parâmetros
relatorios/relatorio_evolucao.md      # Fonte do PDF de evolução
```

## Como executar

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # e preencha sua OPENAI_API_KEY

python main.py                 # chat interativo
python tests/run_tests.py      # suíte completa de testes (3 configurações de modelo)
```

As credenciais ficam apenas no `.env` (ignorado pelo Git).

## Componentes do framework utilizados

- `Agent` / `Runner` — orquestração da conversa;
- `SQLiteSession` — memória por sessão gerenciada pelo framework;
- `@input_guardrail` + `InputGuardrailTripwireTriggered` — bloqueio de prompt
  injection e mensagens fora de escopo antes do modelo principal;
- `ModelSettings` — experimentação com modelos e parâmetros (temperature);
- `output_type` (Pydantic) — saídas estruturadas do classificador e dos juízes.

---

# Sprint 04 — Pipeline de avaliação sistemática

A checagem manual da Sprint 3 foi substituída por um pipeline reprodutível:
um golden dataset de 46 casos é executado contra 3 versões do agente, e cada
resposta é julgada por um LLM juiz (rubrica de 1 a 5, saída estruturada) e por
checagens determinísticas.

```
eval/
  golden_dataset.json   # 46 casos com gabarito (14 das Sprints 1–3 + 32 novos)
  versoes.py            # V1 = Sprint 2 (notebook) · V2 = Sprint 3 final · V3 = Sprint 3 gpt-5-nano
  juiz.py               # LLM as a judge (gpt-5-nano; 2º juiz gpt-4o-mini para concordância)
  metricas.py           # correção, escopo, fidelidade, recusa correta, falsa recusa, nota final
  run_eval.py           # orquestra geração → julgamento → tabela comparativa
  simulacao.py          # agente/juiz falsos para testar o pipeline sem API
tests/test_metricas.py  # testes unitários das métricas e do dataset
relatorios/relatorio_sprint4.md / .pdf   # relatório final da Sprint 04
```

## Como executar

```bash
pip install -r requirements.txt
python -m unittest tests.test_metricas -v   # sem API
python eval/run_eval.py --simular           # testa o pipeline sem API (notas fictícias)
python eval/run_eval.py --offline-sprint3   # checagens determinísticas nas respostas da Sprint 3

python eval/run_eval.py --casos F1 S1       # teste rápido com API
python eval/run_eval.py                     # avaliação completa (V1, V2, V3)
python eval/run_eval.py --rejulgar          # rejulga as respostas já gravadas
```

Saídas em `eval/resultados/`: `respostas_<V>.json`, `avaliacao_<V>.json`,
`resumo.json` e `resumo.md` (tabela por versão e por métrica + comparação com a
Sprint 3).
