# Replay piloto

A suíte `tasks.py` contém 20 fixtures curadas. Os caminhos dos blocos são
metadados fictícios; não representam checkouts executáveis. `is_decisive` e
`required_keywords` são gabaritos do smoke test.

O resultado antigo 90%/10% veio de um simulador que consultava esse gabarito.
Foi preservado em `research/continuation-2026-10-03/inherited/data/d6_pilot/`.
Os arquivos canônicos em `data/d6_pilot/` agora têm origem **SYNTHETIC**, zero
registros admitidos em treino e custo real de API zero. O limiar .95 é uma
proposta; não foi estimado nem validado pelo piloto.

Smoke test explícito:

```sh
/Users/Master/LCC/.venv/bin/python -m replay.harness --simulate --out-dir data/d6_pilot
```

Para execução real, informar comandos independentes de executor e verificador:

```sh
/Users/Master/LCC/.venv/bin/python -m replay.harness \
  --executor-command '/caminho/absoluto/executor-json' \
  --verifier-command '/caminho/absoluto/verificador-json' \
  --out-dir data/d6_adapter_pilot --repeats 3
```

Cada comando lê um objeto JSON em stdin e retorna um objeto JSON em stdout.
O executor recebe apenas `objective`, `context` e `seed`; não recebe gabarito,
bloco candidato ou rótulo esperado. Retorna `status` (`SUCCESS`, `FAILURE`,
`ERROR`, `TIMEOUT`), `output` e, quando disponíveis, `tokens_used` e
`cost_usd` **medidos**. Falhas de processo e timeout geram UNKNOWN.

O verificador recebe a resposta, o objetivo e as referências da fixture;
retorna `passed` booleano e evidência verificável. O verificador interno apenas
confere palavras e serve para diagnóstico. Codificação exige fixtures executáveis
e testes; investigação exige uma checagem de resultado independente. Os registros
permanecem fora de treino até validar o verificador e a confiabilidade dos rótulos.

As repetições usam os mesmos seeds nas duas condições, salvam respostas completas,
hashes dos inputs, argv/scripts, harness e suíte. O wrapper não restaura por conta
própria arquivos, memória, rede ou estado de sessão do agente: o executor deve criar
um ambiente limpo por chamada e registrar modelo/política, versão, seed e reset no
recibo. Configurações ou serviços externos não são congelados pelo hash do script.
Sem esse contrato, igualdade de seed não garante uma ablação causal.

## Execução real concluída

Em2026-10-03, `real_pilot.py` executou120 chamadas Hermes reais com processo/sessão
novos:20 tarefas×baseline/ablação×3, safe-mode e sem ferramentas. As respostas,
prompts, hashes e recibos estão em `data/d6_real_pilot/episodes/`; versão executada
`real-replay/0.1`, fontes originais preservadas em
`research/replay-real-2026-10-03/executed-source/`.

Seis casos executam Python gerado contra contratos comportamentais;14 verificam
diagnósticos/decisões tipados. O resultado auditado dá5 NECESSARY,11 UNNECESSARY,
4 UNKNOWN:80% concordância/20% UNKNOWN, abaixo das metas propostas. Todos os registros
continuam fora de treino. Um bug PDB foi corrigido por reapuração das saídas salvas,
com recibos de episódio intactos; não houve retry seletivo.

Jev1.13.0 usa o cliente canônico e o ledger compartilhado com feature
`lcc_judge_replay_real`. Suas119 chamadas são diagnóstico semântico, não outcome
oracle. Custos efetivamente debitados não são retornados; tokens e estimativa
tarifária estão no resumo. A CLI Hermes não aplica seed de geração, e seu modelo
é um alias sem snapshot imutável. A versão executada incluía seed como metadado no
input; a receita futura v0.2 remove isso e corrige a canonicalização do hash.
Ela ainda não foi executada.

```sh
python3 research/replay-real-2026-10-03/verify_run.py
# Nova receita; sempre diretório novo, sem sobrescrever recibos v0.1:
/Users/Master/LCC/.venv/bin/python -m replay.real_pilot --out-dir data/d6_real_pilot_v02
```

Ver [relatório e próximos critérios](../research/replay-real-2026-10-03/REPORT.md).

## Calibração de verificadores concluída — 2026-10-04

`outcome_verifier.py` é um candidato experimental com contratos executáveis
ampliados e checagens de tipos/percentuais. Foi avaliado em80 controles de calibração
e108 reservados; programas sem AST idêntica entre splits ou com outputs do piloto
anterior. Controles são curados por um único autor nos mesmos arquétipos, sem
anotação externa independente ou restauração dos serviços.

Cutoff Jev .50 escolhido somente em calibração e congelado antes de eval. Código:
0FP/0FN; tipado com consistência Jev:0FP/2FN. Critérios provisórios por tipo passam,
mas os2 FN são PDB válidos (2/3 positivos da família). A próxima receita deve separar
cálculo numérico e checagem textual. O cutoff .50 não substitui a meta de concordância
95% dos replays. O executor do piloto anterior continua na receita histórica.

```sh
python3 research/verifier-calibration-2026-10-03/verify.py
```

Ver [relatório de calibração](../research/verifier-calibration-2026-10-03/REPORT.md).
Nenhum label admitido em treino; qualidade Sprint2, M8 e confiabilidade R19 continuam
sem aprovação global.

## PDB: cálculo separado do texto — 2026-10-04

`pdb_verifier.py` é a próxima receita experimental. Valida orçamento em código
e envia somente fatos verificados + explicação completa ao Jev1.13.0. Referência
Go oficial v0.36.0:4240 conversões e290752 comparações de política sem divergências;
regressões cobrem zeros à esquerda, int32, equivalência de budget e UNKNOWN.

56 controles de desenvolvimento/112 eval, escalas disjuntas, alvo zero erros e
cutoff .50 congelados antes de chamadas. Eval separada:48TP/64TN/0FP/0FN/0UNKNOWN;
acoplada, mesmo guard:21TP/64TN/0FP/27FN/0UNKNOWN.240 chamadas reais Jev com recibos
e ledger. Observação pontual em controles curados; gateClaim DOWNGRADE.
Textos de um autor e templates compartilhados não certificam erro populacional.

```sh
python3 research/pdb-routing-2026-10-04/verify.py
```

Ver [protocolo, limites e evidências](../research/pdb-routing-2026-10-04/REPORT.md).
O piloto real continua com seus outputs/verdicts históricos. Referências de20
contratos e novo replay repetido ainda faltam; nenhum label P2 admitido.
