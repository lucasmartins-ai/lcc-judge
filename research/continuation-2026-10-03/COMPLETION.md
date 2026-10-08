# Continuação da auditoria — 2026-10-03

**Snapshot histórico anterior à autorização/execução do replay real.** O estado
atual está em `research/audit-2026-10-03/AUDIT_RESOLUTION.md` e
`research/replay-real-2026-10-03/REPORT.md`:120 chamadas reais concluídas,
80% concordância/20% UNKNOWN, nenhum label admitido. O texto abaixo é preservado
como registro daquela etapa, não como status vigente.

**Estado: gate de qualidade FALHO; M8 por bloco FALHO; replay real PENDENTE.**
O outro agente concluiu os dois treinos limpos, o bake-off e o treino joint-detect.
Seu relatório declarava encerramento com gates certificados, mas o replay era um
simulador com acesso ao gabarito, o benchmark M8 já registrava reprovação e a
comparação detect não tinha um controle independente. Esta continuação corrigiu
esses pontos e reproduziu as métricas dos checkpoints salvos, sem repetir treino.

Artefatos recebidos preservados em [inherited/](/Users/Master/Downloads/LCC-judge/research/continuation-2026-10-03/inherited).
A auditoria original permanece em [AUDIT.md](/Users/Master/Downloads/LCC-judge/research/audit-2026-10-03/AUDIT.md).

## Onde parou e o que foi concluído

| Etapa | Situação verificada | Resultado / limitação |
|---|---|---|
| 1. Harness e redirect | Correções verificadas; redirect registrado | Δ de score após cache longo = 3.3e-08, abaixo de 1e-6 no caso testado; contagem HF; AUC estrita e gate sem arredondamento; dados antigos continuam com proveniência incompleta |
| 2. Corpus limpo e dois treinos | Concluídos; avaliação completa reproduzida | 2340/810/960; 18 domínios treino; zero assinaturas dos 4 holdouts em treino/val; hashes válidos e splits disjuntos |
| 3. Normalização | Piloto limpo reproduzível concluído, exploratório | Melhora pooled; não passa .90; CI do ganho unfreeze@512 inclui zero; não valida probabilidades M12 |
| 4. Cobertura | 4K n=62 concluído; fronteira 8K pendente | Todos os 186 prompts a profundidade nominal8192 foram cortados; 32K continua sem medida do checkpoint original aceito/limpo |
| 5. Detect | Comparação contra controle independente concluída, negativa | Produto das duas heads reduz D nos dois depths; treino original joint sem seed/recibos preservados |
| 6. Replay P2 | Smoke corrigido; replay real não executado | Origem SYNTHETIC, 0 labels admitidos; exige executor real, verificador de outcome e reset de ambiente |
| 7. CPU | Referência 66K sem cortes medida; M8 global reprova | Dossiê passa; bloco representativo p50 192.40 ms >50; M9 int8 não certificado |

## Métricas confirmadas no disco

Corpus `data/exp02e`, gerador v0.4 seed0: treino2340, val810, OOD960.
As três épocas estão registradas em cada `training_meta.json`, e os optimizers
existem. Não foram reconstruídos seeds/épocas ausentes dos checkpoints antigos ou
do joint. A avaliação por época do loader atual cobre60 exemplos por domínio OOD;
os IDs foram reconstruídos para validar o loader, não apresentados como recibos antigos.

| Checkpoint limpo | AUC OOD completa | AUC val completa |
|---|---:|---:|
| frozen `exp02e-line-attn` | 0.593582 | 0.890774 |
| unfreeze2 `exp02e-unfreeze2` | 0.624242 | 0.942871 |

Estas AUCs do corpus são ROC binária pos vs todos negativos, com meio crédito em
empates, conforme o treino. O gate das probes usa **P(fato > ruído)**, sem crédito
em empates. Não são a mesma população ou tarefa.

Probes v1.2, n=62 por família, janela nativa8192, MPS:

| Profundidade cl100k | frozen J/D | unfreeze2 J/D | Cortes por modelo |
|---:|---:|---:|---:|
| 0 | 0.658/0.673 | 0.748/0.760 | 0/186 |
| 512 | 0.712/0.658 | 0.815/0.713 | 0/186 |
| 4096 | 0.748/0.660 | 0.824/0.702 | 0/186 |
| 8192 | 0.632/0.545 | 0.619/0.549 | 186/186 |

Nenhuma profundidade passa .90 nas duas famílias. Contexto efetivo é o sentinel0;
não significa que o controle passou. A curva cortada em8K não demonstra que
um reasoner hierárquico funciona. O redirect formal já existe em docs/08 e Sprint2,
mas a vantagem da hierarquia e a fronteira nativa sem cortes continuam experimentais.
Não se atribui o ~37s histórico de32K a CPU: foi MPS/v0.2/n8.

A separação semântica treino/probe não tem uma contagem validada53/54. A exceção
raft/monitoring não cobre as sobreposições rollout, pool e cache. A geração separada
não garante domínios conceitualmente inéditos.

## Normalização e detecção

O novo piloto normaliza `logit(p)` por objetivo sobre os três candidatos, sem usar
labels no transform. Unfreeze J controle .7479→.8265, ganho+.0786,
CI[.0200,.1288]; a512 .8145→.8554, ganho+.0408, CI[−.0146,.0926].
D fica .8010/.7482. O candidato-set curado contém fato/decoy/ruído em proporção fixa;
esta transformação depende dos candidatos e requer confirmação fora da suite.
Ela não é uma probabilidade calibrada e não permite ajustar limiares no próprio eval.

A avaliação OOD limpa também refuta calibração como única causa: unfreeze judge
pooled .6217, macro intradomínio .7343, mas `vector_drift` intradomínio apenas .2119.
Normalizações monotônicas por objetivo não corrigem inversões dentro do objetivo.
A cifra antiga .711/.614 e os ganhos de normalização do terminal sem receita salva
não servem como provas independentes; a nova receita e todos os scores estão arquivados.

Joint-detect foi reavaliado contra `exp02e-line-attn`, checkpoint BCE independente,
no mesmo corpus, suite e max_len1024 (inputs0/512 cabem). O resultado anterior
chamava uma head do próprio joint de baseline. Agora:

| Profundidade | BCE J/D | joint-produto J/D | ΔD | CI95% ΔD |
|---:|---:|---:|---:|---:|
| 0 | 0.6582/0.6727 | 0.6907/0.6345 | -0.0382 | [-0.0731, -0.0049] |
| 512 | 0.7120/0.6582 | 0.7222/0.6129 | -0.0453 | [-0.0762, -0.0166] |

O piloto não atende D≥.70/ganho positivo. CIs refletem reamostragem de casos,
não variabilidade entre seeds de treino; o seed original joint não foi salvo.
Isso rejeita a adoção deste produto, sem provar que toda supervisão detect é inútil.

## Replay e orçamento

O simulador lia `is_decisive` e inseria `required_keywords` na resposta, que o próprio
verificador buscava. Os nomes Hermes/AST nas fixtures não correspondiam a executores
instanciados. Corrigido para SYNTHETIC:16 NECESSARY,2 UNNECESSARY,2 UNKNOWN;
90% concordância/10% UNKNOWN descrevem só o smoke. Não houve API, custo real0;
o custo por label anterior era uma estimativa de palavras acrescidas de constante.
O limiar .95 é proposto, não estimado/validado pela distribuição observada.
NECESSARY não implica CRITICAL; UNNECESSARY não implica REDUNDANT: campos extras null.

O harness agora aceita comandos JSON separados de executor/verificador, oculta
rótulos e gabarito do executor, salva respostas/hashes/recibos e marca erros como
UNKNOWN. As fixtures ainda não são checkouts com testes executáveis. O executor
precisa isolar as duas condições e informar modelo/política/seed/environment reset;
o verificador precisa comprovar sucesso da tarefa. Todos os registros ficam fora
do treino até validar essa evidência. O executor real foi solicitado ao usuário;
nenhuma execução real foi substituída por inferência sobre o simulador.

CPU unfreeze, fp32 offline,8 threads:100 blocos,66,000 tokens HF de contexto,
67,100 tokens de input pareado,0 cortes. Load+scoring20.38s≤43s; bloco
representativo p50=192.40ms>50ms. **M8 global=false**. Peak RSS915.4MiB;
int8 M9 não medido. É uma referência sintética de pair scoring, sem cache,
sem custo do reasoner hierárquico e sem integração end-to-end LCC.

## Validação e próximos passos

- Regressões: AUC estrita/empates; gate sem arredondar; controle detect independente;
  replay sem gabarito, sintético fora de treino, UNKNOWN em falha, contrato de subprocesso
  e scripts congelados; orçamento CPU sem escolher só os menores blocos.
- Verificação independente por script: hashes, assinaturas holdout, splits, cobertura,
  métricas, ausência de duplicatas e preservação integral dos5784 scores recebidos.
- Reavaliação completa:3540 exemplos dos dois checkpoints, com logits individuais salvos.
- Determinismo: score de um caso após reset de cache longo dentro de1e-6. Não é uma
  prova exaustiva de invariância em todo hardware, batch/padding ou input possível.

1. **Fornecer executor real e verificador de outcome para as20 tarefas**, com reset,
   versões/seeds e orçamento. Sucesso:120 recibos pareados completos (20×2×3),
   nenhum gabarito enviado, UNKNOWN para discordância/erro, custo medido e auditoria
   do verificador; estimar/fixar limiar em calibração e medir confiabilidade em dados
   separados antes de admitir qualquer label de P2.
2. **Confirmar normalização em objetivos intocados e candidatos variáveis.** Receita
   fixa, split por famílias, sem tuning no eval. Sucesso:ΔJ≥.03 com CI inferior>0,
   perdaD≤.01, ordenação intradomínio e ECE/reliability reportadas se houver claim
   probabilístico. O atual ganho unfreeze@512 não satisfaz o CI.
3. **Corrigir a discriminação OOD e definir o alvo detect**, com controles seeds
   pareados. Priorizar `vector_drift` (J intradomínio .212), sem ensinar no holdout
   congelado. Sucesso: D≥.70 e ganho positivo em0/512, perdaJ≤.02; depois gate .90
   nas duas famílias em OOD intocado. Usar recibos de outcome para necessidade real.
4. **Medir a fronteira sem truncamento quando a decisão de janela exigir**, contando
   orçamento total HF incluindo objetivo/tail. Sucesso:n62×3,0 cortes/erros e posição
   da evidência verificada. Comparar chunks e agregador simples com inputs iguais;
   só justificar reasoner hierárquico se houver ganho significativo e M8 completo.
5. **Otimizar CPU do candidato que passar qualidade**, medindo regressão de qualidade,
   representatividade66K, ambos limites M8 e footprint int8 M9. O resultado atual
   satisfaz apenas o limite do dossiê.

Não vale repetir agora o treino joint-produto que falhou, ampliar32K/64K ou investir
em Track C, publicar/admitir os labels sintéticos, retreinar braços já reproduzidos
ou declarar hierarquia/CPU certificadas. Resultados negativos concluídos são úteis;
o replay real e a janela nativa sem cortes permanecem trabalho pendente.

## Evidência reproduzível

- [Verificação de dados/células](/Users/Master/Downloads/LCC-judge/research/continuation-2026-10-03/verification.json)
- [Logits completos OOD/val](/Users/Master/Downloads/LCC-judge/research/continuation-2026-10-03/saved-evaluation.json)
- [Normalização protocolo/scores](/Users/Master/Downloads/LCC-judge/research/continuation-2026-10-03/normalization-results.json)
- [Detect scores/controle](/Users/Master/Downloads/LCC-judge/research/detect-supervision-results.scores.json)
- [CPU amostras/hashes](/Users/Master/Downloads/LCC-judge/research/continuation-2026-10-03/bench-cpu-unfreeze2.json)
- [Replay documentação](/Users/Master/Downloads/LCC-judge/replay/README.md)
- [Teste de ordem RoPE](/Users/Master/Downloads/LCC-judge/research/continuation-2026-10-03/score-order-check.json)
