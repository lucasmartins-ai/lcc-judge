# Resumo do projeto (LCC + LCC-judge) — 2026-10-11

Documento para o dono. Todo número abaixo vem de um recibo commitado; o caminho está ao lado
de cada tabela ou frase. `R/` = `research/goal-engine-2026-10-04/`. Nenhum texto de sessão
privada aparece aqui, só contagens. Quase tudo é **INFERIDO** (exploratório, uma passada,
juízes LLM ou um único revisor), não MEDIDO.

## Atualização 2026-10-18: teste final do especialista v3

Protocolo pré-registrado: `R/specialist-v1/V3_FINAL_TEST_PROTOCOL.md`. Resultado em
`R/specialist-v1/V3_FINAL_TEST_RESULTS.md` (INFERIDO: os rótulos são regras de "o que o agente usou em seguida").
Conjunto novo, de sessões iniciadas depois de 12/10: 208 itens, 193 primários em 36 sessões.

- **Contra recency, BM25 e mecânico:** passou nas duas métricas (limite inferior do IC acima de 0; recall AUC
  0,899 contra 0,818 / 0,803 / 0,829).
- **Contra os generalistas** (36 itens, um por sessão):
  - Opus: empate técnico. Recall −0,009 [−0,055; +0,031] e all-kept +0,069 [−0,028; +0,167]. A regra rotula
    como "inferior", mas o IC é largo e não há diferença significativa em nenhum sentido.
  - Gemini Flash: "não inferior" em recall e superior em all-kept.
  - A frase "superior a um generalista" **não** se sustenta.
- **Custo:** passou (mediana 178 ms, p90 567 ms, pico de 97,5 MB).
- **Casos sintéticos difíceis** (suíte de borda): os LLMs continuam muito à frente.
- Gasto zero em API. Opus usou 1.480 chamadas e Gemini 1.465, as duas pela assinatura e abaixo do teto de 2.500.

## Resumo executivo (1 página)

**Qual a relação entre os dois repositórios.** O LCC é o produto: compila o contexto que vai
para o agente e corta o que não serve. O LCC-judge nasceu para treinar um modelo local (o
"especialista" ou "juiz local") que decidisse o que cortar no lugar do Laya ou do Jev. Na
prática, o LCC-judge virou o laboratório de medição do LCC: ele constrói os benchmarks com
sessões reais, pré-registra os protocolos, roda as auditorias cegas e guarda os recibos.
As mudanças que passaram nesses testes foram para o LCC (PR #45).

**O juiz está pronto?** Não. Nenhum modelo aprendido passou fora do treino. Todos os
candidatos foram rejeitados (`docs/08-roadmap.md`, Status 2026-10-08) e o especialista roda
só em modo sombra: dá nota a cada bloco, mas mantém todos. Decisão registrada: modelo local
não adotado; antes de qualquer treino novo, medir o modo recuperável no uso real
(`R/PLAN.md`, seção "Desfecho 2026-10-11").

**O que mudou de rumo.** Em vez de corpus técnico escrito por nós, passamos a usar pedidos
reais do dono: 3.782 prompts importados e redigidos, que ficam só em `~/.lcc`
(`R/genuine-requests-v1/README.md`). A partir deles saiu um catálogo de 13 categorias de
"que contexto o agente precisa", confirmado pelo dono em 26/27 itens novos
(`R/request-taxonomy-v1/README.md`).

**O que os benchmarks com sessões reais mostraram.**

- O Jev dentro do LCC, em modo de blocos, corta só 3,5% dos tokens em sessões reais, contra
  cerca de 50% nos corpora curados (`R/real-context-bench-v0.1/RESULTS.md`).
- As regras offline com perda cortam de 19% a 64%, mas reprovaram duas auditorias cegas em
  sessões disjuntas (`R/real-context-bench-v0.4/RESULTS.md`, `R/real-context-bench-v0.5/RESULTS.md`).
- O modo sem perda tem prova mecânica (0 violações em 707 itens) e corta cerca de 0,9%
  (`R/lossless-dedup-v1/RESULTS.md`, `R/recoverable-v0.8/RESULTS.md`).
- O modo recuperável passou na auditoria, mas sem checagem no disco só cerca de 1,2% é
  seguro (`R/recoverable-v0.8/RESULTS.md`).

**Onde paramos.** A PR #45 foi mergeada no LCC (74f10e1). A configuração recomendada é
`rules_mode=recoverable` com `workspace_root` (checagem no disco) e ponteiros de comando
desligados. O padrão continua `lossless` (`R/PLAN.md`, Desfecho). O ganho real do modo com
disco não dá para medir offline; ele vai sair do coletor de pedidos.

## Glossário

| Termo | O que é |
|---|---|
| **LCC** (Local Context Compiler) | Ferramenta local que limpa, deduplica e corta o contexto antes de mandar ao modelo. Não resume: o que fica é copiado literalmente. |
| **LCC-judge** | Este repositório. Começou como tentativa de treinar um juiz local para o LCC e hoje é sobretudo onde ficam benchmarks, protocolos e recibos. |
| **MSI** (Minimal Sufficient Inference) | A tese do LCC: usar o menor contexto e o modelo mais barato que ainda resolvem a tarefa, e provar isso com recibo. Spec em `docs/msi/05-msi-spec-v0.md` no LCC, status experimental. |
| Contrato da tarefa (task contract) | O que a tarefa pede: objetivo, critérios de sucesso, risco, ferramentas permitidas, orçamento. Risco desconhecido vira "preservar ou escalar". |
| Context IR | A representação intermediária do contexto: cada bloco com origem, relevância, se é protegido, dependências e o que foi mantido, cortado ou restaurado. |
| Plano de inferência | Qual classe de modelo usar (local pequeno até frontier), quanto raciocínio, e o que fazer se falhar: restaurar contexto, tentar de novo, trocar modelo, escalar. |
| Verificação | Checagem independente com três resultados: PASS, REVIEW ou FAIL. Nunca falha em silêncio; tem orçamento limitado de restauração e repetição. |
| Recibo (receipt) | Registro de cada execução: o que entrou, o que saiu e por quê, modelo, verificação, custo, versões. É o que permite auditar depois. |
| Portão de triagem (triage gate) | Regra que decide se a resposta barata basta ou se escala. Veio do cognitive-triage-benchmark (dados sintéticos, só pesquisa). |
| **Jev** | Modelo remoto (TypeSafe, System One) que o LCC pode chamar para julgar blocos. É pago por chamada. |
| **Laya** | Provedor local do LCC, com janela pequena (512/1024 tokens). Mantém tudo quando está em dúvida. |
| Especialista / juiz local | O modelo que tentamos treinar aqui para substituir Laya/Jev. Hoje roda em sombra: dá nota, mas não corta. |
| Catálogo de pedidos (13 categorias) | Classificação dos pedidos reais pelo contexto que exigem, por exemplo `failure_report`, `git_ship`, `handoff_prompt`, `task_status_or_control`, mais `UNKNOWN`. |
| Checagens (probes) | Testes automáticos que conferem se um bloco necessário (último turno do agente, último erro, estado do git) sobreviveu ao corte. São indiretas e várias copiam a lógica das regras. |
| Auditoria cega | Juízes que não sabem qual decisão estão avaliando olham uma amostra de cortes e dizem se o corte apagou algo necessário. Passa se o limite superior de Wilson for ≤ 10%. |
| Pré-registro | Protocolo, amostra e critério de aprovação congelados (com hash e commit enviado) antes de rodar. Impede ajustar a régua depois de ver o resultado. |
| Sessões disjuntas | O conjunto de teste não compartilha nenhuma sessão com o de desenvolvimento. A v0.3 falhou nisso e foi rebaixada. |
| Modo sem perda (lossless) | Só troca saídas repetidas por uma referência exata ("igual ao resultado X", "linhas a–b de X"). Dá para reconstruir byte a byte. É o padrão. |
| Modo recuperável (recoverable) | Também troca a leitura de um arquivo por um ponteiro para ele, desde que o agente consiga ler de novo e obter o mesmo conteúdo. |
| Modo com perda (lossy) | Apaga ou apara saídas antigas por regra. Corta muito, mas o que sai não volta. |
| Checagem no disco | Com `workspace_root`, o LCC relê o arquivo na hora de compactar. Só usa o ponteiro se o conteúdo atual for idêntico ao removido. |
| Coletor de pedidos (request log) | Registro opt-in dos pedidos reais, redigido, guardado em `~/.lcc`. É de onde virá a medição em uso real. |
| INFERIDO vs MEDIDO | MEDIDO exige medição repetida ou fonte independente e passa no `gateClaim`. INFERIDO é observação exploratória. Quase tudo aqui é INFERIDO. |

## Onde estamos

**Benchmark com sessões reais (Claude, 60 contextos reais congelados (itens), 49 com checagem).**
Fontes: `R/real-context-bench-v0/RESULTS.md`, `R/real-context-bench-v0.1/RESULTS.md`,
`R/real-context-bench-v0.2/RESULTS.md`, `R/lossless-dedup-v1/RESULTS.md`.

| Braço | Itens retidos | Redução de tokens (agregada) | Custo | Observação |
|---|---:|---:|---|---|
| full (tudo) | 49/49 | 0 | — | controle |
| mechanical | 48/49 | 0,0001 | $0 | praticamente não corta |
| especialista (sombra) | 49/49 | 0 | $0 | não pode cortar |
| Jev em blocos | 47/49 | 0,035 | $43,52 | 3.226 chamadas |
| Jev em transcrição | 30/49 | 0,252 | $41,42 | inválido: 102 de 379 chamadas falharam |
| regras com perda (v0.2) | 49/49 | 0,386 | $0 | retenção copiada das checagens; 3 bugs achados depois |
| sem perda | 49/49 | 0,0034 | $0 | 0 violações, prova mecânica |

**Laya nas sessões reais: não foi medido.** O único dado comparativo do Laya é em tarefas
curadas. No Pareto com dossiês de 8K/32K, o motor e o Laya removem zero contexto e o Jev
remove cerca de 79% dos caracteres. No piloto de observações (144 execuções), a rota local
acertou 36/36, o Jev 36/36, o full 34/36 e o Laya 33/36, com os mesmos bytes que o full
(`R/PLAN.md`, "Fechamento das medições").

**Auditorias cegas das regras (sessões disjuntas).**

| Rodada | Dados | Corte | Sinalizados / auditados | Limite sup. Wilson | Resultado | Fonte |
|---|---|---:|---:|---:|---|---|
| v0.3 | Claude, sessões compartilhadas | 0,350 | 7/150 | 0,093 | rebaixada (não é teste independente) | `R/real-context-bench-v0.3/RESULTS.md` |
| v0.4 | Codex, com perda | 0,641 | 21/150 | 0,205 | FALHOU | `R/real-context-bench-v0.4/RESULTS.md` |
| v0.5 | Codex, com perda, mais conservador | 0,191 | 36/132 | 0,354 | FALHOU | `R/real-context-bench-v0.5/RESULTS.md` |
| v0.6 | Hermes, recuperável | 0,041 | 0/77 | 0,048 | auditoria passou, verificação falhou (1 fail-safe) | `R/real-context-bench-v0.6/RESULTS.md` |
| v0.7 | Hermes, recuperável | 0,034 | 1/54 | 0,098 | PASSOU, sem margem | `R/real-context-bench-v0.7/RESULTS.md` |

**Recuperável depois da correção (v0.8, 847 itens em 8 conjuntos).** A correção só
transforma substituições em manutenções: 0 violações de subconjunto e verificação 0/0/0.
Mas a redução cai de 0,0576 para 0,0123, contra 0,0093 do modo sem perda. Ou seja, sem
disco o recuperável acrescenta uns 0,3 ponto (`R/recoverable-v0.8/RESULTS.md`).

**Rótulos e pedidos.**

- Revisão do corpus técnico antigo: concordância de 0,417, portão falhou
  (`R/human-review-v2-pt/RESULTS.md`).
- Catálogo de 13 categorias sobre pedidos reais: 41/56 = 0,732 nos casos difíceis e
  26/27 = 0,963 em itens novos de alta confiança (`R/request-taxonomy-v1/README.md`).

## O que funcionou

- Trocar o corpus técnico escrito por nós por pedidos reais do dono. No corpus técnico, a
  concordância do dono foi 0,417 (`R/human-review-v2-pt/RESULTS.md`). A taxonomia nova teve
  26/27 = 0,963 na confirmação de itens novos de alta confiança e 41/56 = 0,732 nos itens
  difíceis (`R/request-taxonomy-v1/README.md`). São populações e medidas diferentes, e
  nenhuma é taxa da população; não se comparam como um antes e depois.
- O método: pré-registro com hash, sessões disjuntas, dois juízes por registro e falhas
  publicadas. Foi isso que pegou o falso sucesso da v0.2 e o vazamento de sessões da v0.3.
- Modo sem perda: corte pequeno, mas com prova mecânica e sem precisar de juiz.
- Medir o Jev em sessões reais mostrou que o gargalo não é o juiz, e sim a política de
  blocos e proteções do LCC, que mantém quase tudo de qualquer jeito
  (`R/real-context-bench-v0.1/RESULTS.md`).

## O que não funcionou

- Todos os modelos locais aprendidos: P1, semântico, relação compacta, suporte, fatorado,
  confirmação variada e intérprete de objetivo (`docs/08-roadmap.md`).
- Regras com perda em Codex: reprovaram duas auditorias seguidas. O ajuste feito no DEV
  (9/100) não se manteve no TEST (36/132). As duas taxas não se comparam direto: no DEV
  havia um juiz por registro, no TEST um registro é marcado se qualquer um de dois juízes
  marcar. Com um juiz, o TEST fica em ~54/264 = 0,20 (`R/real-context-bench-v0.5/RESULTS.md`,
  nota de revisão 3).
- Checagens (probes) como prova de retenção: copiam os predicados das regras e não
  enxergaram três bugs reais (`R/real-context-bench-v0.2/RESULTS.md`).
- Recuperável sem disco: depois da correção sobra quase nada acima do modo sem perda.
- O Jev em modo transcrição monta pedidos maiores do que a API aceita (77 rejeições).

## Próximos passos

1. **Avaliação por resultado primeiro.** A pergunta certa é se o agente termina a tarefa
   igual com o contexto compactado, não se um bloco sobreviveu. O MSI-Bench do LCC já mede
   assim, mas é um piloto com 12 tarefas curadas (`benchmarks/msi-bench/REPORT.md` no LCC).
   O próximo passo é a mesma régua sobre pedidos reais do coletor, com full contra
   recuperável+disco, pré-registrada.
2. Ligar o coletor de pedidos e o modo recuperável com `workspace_root` no uso real, e medir
   quanto o disco libera de fato. Sem isso, os números acima são todos proxy de transcrição.
3. Ponteiros de intervalo e de comando nunca passaram por auditoria. Precisam de um conjunto
   novo, ainda não visto, antes de qualquer mudança de padrão.
4. Só depois disso pensar em treino. Se houver treino, o alvo são as decisões que a política
   deixa em aberto, rotuladas pelo catálogo de 13 categorias, e não o corpus antigo.
5. Revisão do dono: os 7 casos sinalizados da v0.3 e uma amostra dos "não necessários", para
   calibrar os juízes LLM contra o julgamento humano.

## Opinião sobre o caminho

O caminho está mais sólido do que estava há uma semana, porque agora mede o que importa
(pedidos e sessões reais) e aceita resultado negativo. O ponto fraco é que ainda não medimos
o resultado da tarefa, só a sobrevivência de blocos e o julgamento de LLMs sobre cortes.
Enquanto o corte seguro for de cerca de 1% offline (sem perda 0,0093, recuperável 0,0123,
`R/recoverable-v0.8/RESULTS.md`; os ~4% da v0.6/v0.7 vinham de políticas que a v0.8 mostrou inseguras), o valor do LCC está na garantia (sem perda e
verificável) e no MSI (roteamento, verificação e recibo), não na compressão. Falta provar,
com tarefas reais, que roteamento e verificação economizam custo sem piorar o resultado.
