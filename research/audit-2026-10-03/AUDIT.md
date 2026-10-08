# Auditoria independente — EXP-04 / Sprint 2 — 2026-10-03

O gate falhou nos scores arquivados. O encerramento da fase não está completo:
há vazamento dos holdouts, inferência dependente do cache de RoPE, cobertura
parcial e ausência de decisão formal de redirect. Esta auditoria preservou os
datasets, checkpoints, resultados e documentos originais.

## Reprodução

```sh
cd /Users/Master/Downloads/LCC-judge
python3 research/audit-2026-10-03/verify.py
/Users/Master/LCC/.venv/bin/python research/audit-2026-10-03/evaluate_saved.py
/Users/Master/LCC/.venv/bin/python research/audit-2026-10-03/check_runtime.py
/Users/Master/LCC/.venv/bin/python research/audit-2026-10-03/check_score_order.py
```

Os três últimos comandos usam o ambiente existente e os arquivos locais do
Hugging Face em modo offline. Não treinam nem alteram checkpoints. O segundo
comando reavalia os splits completos em MPS, batch 8, max_len 1024; não reroda
a suíte inteira de 16K/32K. As contagens do gate são calculadas diretamente
dos scores em `results.json`, sem importar a função de AUC do runner.

Arquivos de evidência:

- `evidence.json`: AUCs exatas, cobertura por célula, sensibilidade, hashes,
  checagem do summary e da tabela, assinaturas dos holdouts e datasets derivados.
- `saved-evaluation.json`: logits individuais, métricas integrais e identidade
  dos dois checkpoints EXP-04. torch 2.14.0; transformers 5.17.0; MPS.
- `runtime-checks.json`: contagens do tokenizer real e teste de cache de RoPE.
- `score-order-check.json`: diferença medida no score da mesma entrada.

Hash SHA-256 do `bakeoff/results/results.json` usado: ver `source_sha256` em
`evidence.json`. Foi conferido novamente ao fim das verificações e permaneceu igual.

## Gate confirmado

Checkpoint: `models/exp02d-unfreeze2`; adapter:
`specialist-exp04-unfreeze2-dyn-49k`.

| profundidade | casos | J pooled | D pooled |
|---|---:|---:|---:|
| 0 | 62 | 2658/3844 = 0.691467 | 2252/3844 = 0.585848 |
| 512 | 62 | 2996/3844 = 0.779396 | 2042/3844 = 0.531217 |
| 4096 | 4 | 12/16 = 0.750000 | 10/16 = 0.625000 |
| 8192 | 0 | ausente | ausente |
| 16384 | 62 | 2907/3844 = 0.756243 | 1965/3844 = 0.511186 |
| 32768 | 0 | ausente | ausente |

Não houve empates nessas células. Nenhuma profundidade medida passou 0.90.
O valor 0 de contexto efetivo é o sentinela do relatório para conjunto vazio;
não significa que o controle passou nem que o modelo só processa zero tokens.
Foram conferidos 1.360 campos do summary contra as linhas brutas e 1.190
campos das tabelas de detalhe de `RESULTS.md`, sem discrepância.

## Bloqueantes

1. **Os holdouts aparecem como negativos no texto de treino e val.**
   `specialist/corpus.py:412` sorteia `other_domain` em `DOMAINS`, incluindo
   holdouts, apesar da separação correta de `TRAIN_DOMAINS` em `:352`.
   O conteúdo de `data/exp02d` é exatamente reproduzido pelo gerador atual.
   Não é uma hipótese sobre uma versão futura do gerador.

   | holdout | train | val |
   |---|---:|---:|
   | vector_drift | 36 | 7 |
   | bot_traffic | 44 | 10 |
   | pdf_render | 46 | 7 |
   | sms_delivery | 46 | 8 |
   | total | 172 | 32 |

   Exemplos: `data/exp02d/train.jsonl:22` contém `pages_done=3 pages_total=120
   state=stalled`; `:34` contém `drift=0.008 threshold=0.03 samples=9021`;
   `data/exp02d/val.jsonl:8` contém `delivered_pct=61.2 carrier=vodafone
   queued=99210`. São exemplos rotulados como `neg_unrelated` para objetivos
   de outros domínios. O campo `domain` tem 18 domínios e zero holdouts em
   train/val; isso não implica exclusão do texto. Contagens, digests e hashes
   dos três splits v0.3 batem; interseção entre hashes dos splits é zero.
   A afirmação de holdout ENTIRELY em `research/experiments.md:98` é falsa.
   OOD continua sendo uma medição, mas não certifica arquétipos nunca vistos.

2. **O score depende do estado prévio do RoPE dinâmico.** O cache cresce e
   só volta à escala original abaixo de 8192 posições. Uma sequência menor
   acima desse limite reutiliza as frequências de uma sequência maior.
   Evidência: `transformers/modeling_rope_utils.py:82` no ambiente LCC;
   `specialist/model.py:55`; `runtime-checks.json`.
   No teste com o checkpoint aceito, `booking_timeout/fact@8192` tem 9.505
   tokens do tokenizer real. Score inicial 0.486358; após inicializar as
   frequências rotárias com posições até 20.000, score 0.642083, diferença
   0.155725. O teste inicializa o cache diretamente pelo módulo rotário,
   sem executar um segundo forward do encoder longo. Essa é uma condição
   de cache alcançável por uma chamada longa anterior. Conflita com M7 em
   `docs/02-model-requirements.md:21`. Não muda a aritmética arquivada do gate,
   mas compromete reprodução entre lotes e atribuição causal de diferenças.

3. **Redirect formal ausente.** `docs/08-roadmap.md:33` exige a alternativa
   negativa com redirect para Track C ou abandono das ambições acima de 8K.
   `SPRINT_02_BAKEOFF.md:39` declara a cláusula satisfeita; `:55` apenas
   repete condicionalmente as opções; `:165` aceita o stack e `:183` agenda
   novos experimentos. `research/experiments.md:160` faz o mesmo. Nenhum
   desses trechos escolhe uma das alternativas, define escopo ou substitui
   formalmente o requisito M1 de 32K. A documentação da falha existe;
   a decisão de redirect não.

## Materiais

4. **Cobertura incompleta e populações diferentes.** Em 4K há somente
   `payment_decline_spike`, `tls_cert_expiry`, `dns_resolver_timeout` e
   `rate_limit_flood`. `RESULTS.md:283` omite n e parece uma célula comparável
   às de 62 casos. O braço frozen v0.3 só tem 0 e 512, sem controle 16K.
   `SPRINT_02_BAKEOFF.md:39` não sustenta um piso contínuo ≥.70: controle
   é .691, 4K é parcial e 8K está ausente. A afirmação de retirar posições
   como causa em `:167` é mais forte que os dados.

   J@32K = .828125 existe: checkpoint v0.2 `exp02c-line-attn`, probe v1.1,
   oito casos. `research/experiments.md:24`/`:26` e `:185`/`:196` qualificam
   corretamente origem, população e ausência de rerun. A seção histórica
   EXP-03 do sprint também identifica v1.1. Não é um resultado inventado nem
   uma contradição histórica; extrapolá-lo ao checkpoint aceito/v1.2 seria
   uma afirmação sem lastro. A tabela atual mistura n=62 até 16K e n=8 em 32K.

5. **Calibração é uma hipótese útil, não um mecanismo causal isolado.**
   Reavaliação integral reproduziu OOD/val: frozen .5726/.9305; unfreeze
   .6734/.9494. Não foi encontrada receita nem arquivo de scores que suporte
   exatamente o diagnóstico .711 paired/.614 pooled ou os logits citados
   em `research/experiments.md:151`. No checkpoint final, judge no OOD
   completo é .710400 pooled; média simples das AUCs dentro dos quatro
   domínios é .740023. Essas definições estão explicitadas no script e não
   são substitutos silenciosos para um diagnóstico paired não especificado.
   J dentro de `vector_drift` = .427172 e de `bot_traffic` = .612500; logo
   a ordenação dentro de domínios também falha. O vazamento oferece outra
   explicação para os offsets. Normalização monotônica por objetivo mantém
   as inversões dentro desse objetivo; temperatura global mantém toda AUC.

   Atribuição de +.10 somente ao unfreeze também exagera o isolamento.
   J@512, all62: baseline .683923 → frozen v0.3 .722164 → unfreeze v0.3
   .779396. Ganho isolado ao trocar frozen por unfreeze no v0.3: .057232;
   no new54: .047668. O +.10 é aproximadamente o ganho combinado de corpus
   e adaptação no new54. Frozen@16K não foi medido. Não há CIs nem múltiplas
   seeds para essas afirmações de superioridade.

6. **53/54 semanticamente inéditos não foi demonstrado.** Há 54 IDs novos,
   mas IDs e conjuntos completos de campos distintos não provam arquétipos
   distintos. Além de `raft_leader_flap` ↔ `monitoring_flap`, há:
   `flag_rollout_exposure` (`probes.py:256`) ↔ `deploy_rollout`
   (`corpus.py:165`), `connection_pool_exhaust` (`:270`) ↔
   `pool_saturation` (`corpus.py:116`), e `ci_cache_miss` (`:459`) ↔
   `cache_perf` (`corpus.py:128`). São o mesmo tipo de evidência/pergunta
   com outra terminologia ou subsistema. A exceção conhecida é confirmada;
   sua exclusividade é refutada. Não atribuí uma nova contagem exata sem
   uma rubrica de equivalência semântica e revisão de todos os casos.

7. **Há erros numéricos nas narrativas, apesar das tabelas calculadas corretas.**

   - `research/experiments.md:46` chama de clean54 a curva .657/.743/.726:
     são valores all62. New54 correto: .639232/.722222/.700274.
   - `research/experiments.md:107`: retirar raft muda D@16K de .511186
     para .495297, queda .015889, acima do declarado ≤.006. J muda .006445.
   - `SPRINT_02_BAKEOFF.md:164` e `research/experiments.md:156`: D .46–.59
     em todas as profundidades mistura populações; all62@512 é .531 e
     4K parcial é .625. O intervalo corresponde aproximadamente ao new54
     nos pontos completos, não a toda a tabela.
   - `SPRINT_02_BAKEOFF.md:176`: controle de quatro épocas DONE, mas EXP-04
     descreve e arquiva três épocas de um protocolo diferente (corpus v0.3,
     line-attn, max_len 1024, sem currículo longo). O plano original não foi
     executado literalmente nem formalmente substituído.
   - `SPRINT_02_BAKEOFF.md:190`: CPU-only contradiz as execuções MPS
     descritas em `:116`/`:148`. A latência histórica extrap@32K de 38.4 s
     em `research/experiments.md:205` não bate com a mediana atual 37.88125 s;
     não há recibo separado para recuperar a execução anterior.

8. **Metadados não certificam o histórico real de épocas.** Ambos os EXP-04
   declaram reconstrução de logs (`training_meta.json:36`); não há logs de
   terminal arquivados no workspace. As três épocas são compatíveis com o
   relato, mas não verificáveis independentemente. EXP-02c line-attn/line-max
   têm somente uma época, args.epochs=1, resume=true, apesar das três épocas
   no log (`research/experiments.md:260`). O código salva os pesos por época
   (`train.py:184`) e o histórico apenas no fim (`:218`); uma interrupção
   pode deixar pesos e histórico de momentos diferentes. Resume recria AdamW
   e reinicia o contador de épocas. AUC por época EXP-04 usa as primeiras
   160 linhas; no OOD são todas `vector_drift`. Não sustenta a narrativa de
   trajetória dos quatro holdouts completos.

9. **Flags e proveniência do relatório são incompletas.** `adapters.py:255`
   determina truncamento com tiktoken contra uma janela do tokenizer HF.
   exp02c-512@256: 24/24 inputs têm 563–607 tokens HF e são truncados,
   mas 24/24 registros dizem truncated=false. Para o checkpoint aceito em
   16K, conferi 186 entradas: 18.576–18.826 tokens HF, todas cabem em 49.152;
   não achei truncamento nessa célula. Os oito casos históricos de 32K
   também cabem (36.976–37.254). O defeito da flag não elimina esses resultados.

   Há 1.728 linhas sem probe_version explícito, tratadas como 1.0 por default.
   O merge (`runner.py:235`) sobrescreve device global; as linhas não guardam
   device, run ID, hash de entrada/checkpoint/config ou revisão do modelo
   base. `RESULTS.md:3` diz MPS para um arquivo com histórico CPU e MPS.
   O aviso sobre versões é correto, mas não torna válidas comparações
   v1.0→v1.1 que mudaram construção, nem n=62→n=8 na curva atual.
   Não há validação de CPU do checkpoint aceito contra M8.

10. **Datasets auxiliares não estão íntegros como artefatos de reprodução.**
    `data/exp02b_short/manifest.json` diz 2400/640/960; os JSONLs têm
    786/205/296 e digests diferentes. `data/exp01_padded` não tem manifest
    e mantém hashes antigos em todos os 5.200 textos alterados.
    `data/exp02b_taildec` não tem manifest; 2.693 hashes divergem do texto.
    Controles padded/taildec possuem weights.pt, sem config/training_meta.
    Afeta a auditabilidade da cadeia histórica; não muda as frações do gate atual.

## Menores

- `research/failures.md` não existe, embora exigido por `docs/08-roadmap.md:88`
  e `docs/05-benchmark-strategy.md:114`. Os outros caminhos locais de artefatos
  citados no sprint/log existem; não encontrei links locais quebrados nesses
  documentos. A falha está descrita em experiments, mas falta o registro exigido.
- Há sete entradas no log, porém -03-01 vem antes de -03-02, contrariando
  newest-first e deixando OPEN no primeiro relato que o leitor encontra.
- README ainda descreve n=8 e substituição de resultados por modelo inteiro.
  Não há TODO/FIXME escondido que explique a conclusão; o trabalho incompleto
  aparece como células ausentes/parciais, histórico incompleto e pilotos pendentes.
- Runner usa meio crédito para empates, apesar da fórmula escrita como P(>).
  Não afeta os números neurais confirmados, que não têm empates; afeta a leitura
  literal dos resultados lexicais.

## Próximos passos, por decisão desbloqueada/custo

1. **Corrigir instrumentos e registrar redirect.** Separar janela do tokenizer
   do limite original do RoPE; fazer frequências dependerem apenas da entrada
   atual; calcular truncamento com o tokenizer efetivo; guardar identidades e
   população por run/célula. Registrar escolha entre Track C restrito e envelope
   ≤8K com agregação, ou declarar a decisão ainda pendente. Sucesso: mesma entrada
   antes/depois de uma longa e em ordens diferentes varia ≤1e-6 e preserva rankings;
   zero flags incorretas; documento com alternativa, escopo e gate explícitos.

2. **Consertar corpus e refazer a base OOD.** Distratores de train/val só podem
   vir dos 18 domínios permitidos. Regenerar com versão nova, atualizar hashes,
   auditar semanticamente probes×domínios e preservar v0.3 como contaminado.
   Repetir os dois braços curtos, arquivando logs, estado do optimizer e scores
   integrais por época. Sucesso: zero assinaturas holdout em train/val, zero
   interseção de conteúdo, históricos completos e OOD estratificado cobrindo 4/4
   domínios. Não exige atingir .90 para tornar o diagnóstico útil.

3. **Piloto barato de normalização.** Primeiro 0/512, com calibração independente,
   contexto/candidatos disponíveis na operação real e sem labels de teste na
   normalização. Temperatura global não aumenta AUC. Sucesso pré-registrável:
   ganho J pooled ≥.03, limite inferior do CI pareado por caso acima de zero,
   sem perda de D >.01; registrar também inversões dentro de objetivo. Manter
   a barra original .90. Se falhar, cortar o lever; se melhorar, ainda não
   declarar calibração como causa única. Checkpoint contaminado serve só como
   exploração antecipada, não como validação desse sucesso.

4. **Cobertura escalonada do checkpoint estável.** Medir os 58 casos faltantes
   de 4K e 62/62 em 8K; então 32K, em batches com recibos. Sucesso: cada célula
   tem 62 fatos, 62 decoys e 62 ruídos, mesmo protocolo, zero erros/truncamentos
   reais, scores invariantes à ordem, custo por device. ≥16K efetivo continua
   exigindo AUC≥.90 por família e orçamento CPU definido. Como 32K custa ~37 s
   por score no histórico (186 scores ≈1.9 h), completá-lo só vale se influenciar
   a decisão sobre ambição >8K; não bloqueia aceitar um envelope menor.

5. **Objetivo detect correto, com ablação.** Já existem neg_unrelated; é preciso
   corrigir como são gerados e alinhar a supervisão à relevância por objetivo,
   incluindo anomalias irrelevantes. Comparar BCE conjunta com objective/head
   separado no mesmo corpus limpo. Sucesso inicial pré-registrável: D pooled≥.70
   em 0/512 com CI de ganho acima de zero e perda J≤.02. Depois medir 8K/16K;
   .70 é gate de diagnóstico, não substitui .90 do Sprint 2.

6. **Replay de 20 tarefas, iniciado em paralelo ao passo 2.** Não há harness,
   tarefas congeladas ou recibos de replay neste workspace. Pin executor,
   verifier, seed e baseline; repetir controles e ablações e marcar UNKNOWN
   em desacordo. Sucesso: 20/20 tarefas com pares baseline/ablação auditáveis,
   taxa de concordância, UNKNOWN e custo por label medidos; congelar o limiar
   de confiabilidade a partir da distribuição do piloto antes de treinar P2.

7. **CPU do envelope escolhido.** Depois de escolher os comprimentos/blocos,
   medir CPU real, p50/p95, RAM e uma sessão de referência. Sucesso: M8 satisfeito
   (<50 ms p50 warm por bloco e ≤43 s por dossiê) ou orçamento alternativo
   explicitamente aprovado no redirect. Não usar MPS como certificação CPU.

Não vale agora: modelo nativo Track C sem decisão e diagnóstico limpo; 48K/64K;
currículo longo caro antes de separar erro de dados, ranking e posição;
shopping amplo de encoders; quantização/export como prioridade; mudar gate para
paired; nem rerodar todos os modelos antigos apenas para polir uma tabela única.
