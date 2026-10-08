# Auditoria final — inteligência local do LCC

Data: 2026-10-04. Workspace: `/Users/Master/Downloads/LCC-judge`, ainda sem Git.
O usuário definiu o destino: **repositório próprio para o modelo que deverá substituir
Laya/Jev nas decisões do LCC**, com pesquisa publicável e participação externa.
Refinamento do usuário: **motor próprio, rápido, leve, local, eficiente e hiper
especializado**. O escopo é inteligência de compilação de contexto, com capacidades
medidas e limitadas às decisões necessárias ao LCC.

**Parecer:** há um programa de pesquisa documentado, artefatos verificáveis e resultados
negativos úteis. O snapshot ainda precisa de preparação para publicação colaborativa.
**A substituição de Laya/Jev e a superioridade científica não estão demonstradas.**
O protótipo atual aprende classificação de evidência de incidentes; os contratos,
dados e avaliações das decisões mais amplas permanecem metas.

Publicar uma pesquisa experimental não exige que todos os gates do modelo passem.
Exige instalação, reprodução, licenciamento, escopo e execução seguros e claros.
Adotar o modelo como provider exige também os gates de qualidade, custo e integração.

## Escopo e método

Leitura direta de código, documentos, JSON/JSONL, checkpoints e recibos; dois passes
independentes de código e reprodução; recomputação das AUCs sem importar o runner;
controles mínimos usando o runner e o pooling reais; consulta a literatura primária.
Não houve novo treino, inferência paga, replay de modelo, publicação ou alteração de
código/dados/pesos experimentais. Os únicos arquivos criados pertencem a esta auditoria.

O consumidor público foi conferido no commit
[`0a782c2fd229c01e8548bc0b979963e6c84245e0`](https://github.com/lucasmartins-ai/lcc/commit/0a782c2fd229c01e8548bc0b979963e6c84245e0).
Seu [SemanticProvider](https://github.com/lucasmartins-ai/lcc/blob/0a782c2fd229c01e8548bc0b979963e6c84245e0/src/lcc/relevance/provider.py#L31)
está copiado nesta pasta para conferir a fronteira entre projetos. Ausências locais
não são atribuídas ao repositório público do LCC.

Comandos executados na raiz durante esta auditoria:

```sh
python3 -m unittest discover -s tests -v
python3 research/continuation-2026-10-03/verify_completion.py
python3 research/replay-real-2026-10-03/verify_run.py
python3 research/verifier-calibration-2026-10-03/verify.py
python3 research/pdb-routing-2026-10-04/verify.py
python3 research/final-audit-2026-10-04/verify_snapshot.py
/Users/Master/LCC/.venv/bin/python research/final-audit-2026-10-04/verify_snapshot.py --controls
```

**32 testes passaram**, assim como os quatro verificadores existentes, neste ambiente.
Isso confirma suas invariantes locais; não resolve as dependências privadas descritas
abaixo. O script novo salva [checks.json](checks.json) e
[checks-with-controls.json](checks-with-controls.json); sua opção padrão usa só a
biblioteca padrão. `--controls` precisa do ambiente ML existente, não baixa modelos.

## Bloqueantes

### B1 — Ainda não há evidência para substituir o provider do LCC

**Bloqueia adoção e alegação de substituição.** O alvo do corpus é anomalia versus
execução saudável/ruído, em [corpus.py:387](/Users/Master/Downloads/LCC-judge/specialist/corpus.py:387).
A entrada é objetivo + um bloco, em [model.py:152](/Users/Master/Downloads/LCC-judge/specialist/model.py:152).
Necessidade, criticalidade, redundância e suficiência dependem também do conjunto:
[taxonomia:39](/Users/Master/Downloads/LCC-judge/docs/01-decision-taxonomy.md:39).
O mesmo bloco, isolado ou acompanhado de cópia, gera a mesma entrada para o modelo,
embora sua necessidade possa mudar. O alvo atual não comprova essas capacidades.

O provider do LCC recebe `evaluate(state, questions)`, declara operações suportadas,
disponibilidade, contexto e identidade do modelo. `prob(objective, text)` devolve
um float. Não encontrei adapter do specialist que cumpra aquele contrato, nem
schema nativo executável, abstention ou teste de substituição integrado. A arquitetura
é corretamente marcada como conceitual em
[docs/03:3](/Users/Master/Downloads/LCC-judge/docs/03-target-architecture.md:3);
sua ausência no experimento atual não é um bug, mas impede apresentá-la como entregue.

As próprias medidas continuam negativas: qualidade clean falha, M8 por bloco falha,
replay tem 80% concordância/20% UNKNOWN e **zero registros admitidos em P2**.
Evidências: [Sprint:79](/Users/Master/Downloads/LCC-judge/SPRINT_02_BAKEOFF.md:79),
[replay:12](/Users/Master/Downloads/LCC-judge/research/replay-real-2026-10-03/REPORT.md:12).

**Correção necessária:** definir primeiro as perguntas do LCC que o provider pode
responder, com rejeição explícita das demais; medir outcomes e custo no mesmo fluxo
antes de habilitar drops. A meta pode continuar abrangente; cada capacidade precisa
de uma evidência própria.

### B2 — Código gerado não está protegido por uma sandbox

**Bloqueia a execução de contribuições/outputs não confiáveis no release público.**
[real_fixtures.py:88](/Users/Master/Downloads/LCC-judge/replay/real_fixtures.py:88)
filtra importações, nomes de chamadas e alguns atributos, mas em
[:99](/Users/Master/Downloads/LCC-judge/replay/real_fixtures.py:99) usa `exec` com
builtins completos. O candidato faz o mesmo em
[outcome_verifier.py:51](/Users/Master/Downloads/LCC-judge/replay/outcome_verifier.py:51).

O controle **apenas estático** em `verify_snapshot.py --controls` demonstra que o
acesso a `open` por indexação de `__builtins__` passa as regras atuais. O exemplo não
foi executado. Diretório temporário, Python `-I`, ambiente reduzido e timeout não
restringem os privilégios do processo sobre o host.

**Correção necessária:** desabilitar esse caminho por padrão no pacote público até
executá-lo em ambiente descartável com filesystem do host inacessível, sem credenciais
ou rede, limites de recursos e encerramento de subprocessos. Validar controles de
contenção dentro desse ambiente. Não encontrei evidência de exploração passada.

### B3 — Um clone público não reproduzirá o pacote de auditoria completo

**Bloqueia reprodução pública.** O bridge importa cliente de outro workspace:
[jev_bridge.ts:3](/Users/Master/Downloads/LCC-judge/replay/jev_bridge.ts:3),
[pdb_jev_bridge.ts:3](/Users/Master/Downloads/LCC-judge/replay/pdb_jev_bridge.ts:3).
O executor usa paths pessoais de Hermes/TSX e fonte externa:
[real_pilot.py:22](/Users/Master/Downloads/LCC-judge/replay/real_pilot.py:22).
Até a auditoria sem chamadas novas exige o ledger privado de LOOKAORCHESTRATOR:
[PDB verify:133](/Users/Master/Downloads/LCC-judge/research/pdb-routing-2026-10-04/verify.py:133),
[calibração verify:115](/Users/Master/Downloads/LCC-judge/research/verifier-calibration-2026-10-03/verify.py:115).

Não há manifesto de instalação/lock na raiz. Backbone e tokenizer são carregados
sem revisão imutável em [model.py:100](/Users/Master/Downloads/LCC-judge/specialist/model.py:100).
Um nome de modelo não identifica todos os bytes necessários à reprodução de pesos
que salvam só os parâmetros treinados.

**Correção necessária:** adapters configuráveis, dependências públicas fixadas,
revisão HF/tokenizer e extrato sanitizado do ledger por run. Separar audit offline,
que deve funcionar sem key/rede, de rerun de provider, que depende de backend/API.

## Materiais

### M1 — A proposta ampla de novidade tem precedentes diretos

**Bloqueia a alegação de originalidade ampla, não a publicação experimental.**
Encoders pequenos para compressão já aparecem em
[LLMLingua-2](https://arxiv.org/abs/2403.12968). Compressão condicionada à pergunta
aparece em [LongLLMLingua](https://aclanthology.org/2024.acl-long.91/).
Treinar seleção/compressão pelo efeito no LM downstream aparece em
[RECOMP](https://arxiv.org/abs/2310.04408). Portanto esses componentes isolados não
sustentam uma contribuição inédita.

Os precedentes mais próximos encontrados são:

| Trabalho primário | Sobreposição relevante | Diferença que merece experimento |
|---|---|---|
| [CICL v4, 2026-09-21](https://arxiv.org/html/2606.08151v4) | utilidade de decisão, necessidade/outcome como componentes, grafo, schema tipado e substituto local | usa estimativas inspiradas em contrafactuais e memory cards; a avaliação principal é retrieval de arquivos, com limite explícito sobre patch success |
| [CMI, 2026](https://arxiv.org/html/2605.17641) | intervenções com/sem memória e memória perturbada, benefício na tarefa | foco em memória conversacional; scorer interno determinístico usa critérios/gabarito, avaliação final híbrida; não estabelece esta implantação no LCC |
| [RepoShapley v2, 2026](https://arxiv.org/abs/2601.03378v2) | utilidade depende da coalizão, supervisão marginal, decisões verificadas destiladas | code completion com teacher-forced probing e controle no gerador; precisa comparação com provider pequeno separado |
| [ContextCite](https://arxiv.org/abs/2409.00729) | ablação de contexto e atribuição | atribui uma geração; não certifica sucesso executável da tarefa |
| [Sufficient Context](https://arxiv.org/abs/2411.06037) | suficiência de contexto e abstenção | motivação próxima da futura head set-level; deve entrar em related work |

**Inferência desta auditoria:** a combinação que vale investigar é um provider CPU
pequeno e independente do gerador, treinado com outcomes verificáveis, que preserva
blocos originais e trata incerteza/restauração no LCC. Isso é uma **hipótese de
diferenciação**, não uma certificação de que ninguém a propôs. Nem “causal” nem
“outcome-aware” sozinhos podem ser vendidos como novidade. A revisão foi dirigida,
não uma busca bibliográfica exaustiva; os trabalhos acima não foram reproduzidos aqui.

### M2 — `line-attn` deixa linhas inexistentes participarem da atenção

[model.py:203](/Users/Master/Downloads/LCC-judge/specialist/model.py:203) toma
`max(line_id)+1` como número de linhas. O softmax mascara apenas o final, em
[:225](/Users/Master/Downloads/LCC-judge/specialist/model.py:225), e inclui IDs
intermediários sem tokens, representados por zero.

Controle com hidden `[2,4]`, scorer uniforme e head identidade: IDs `[0,1]` dão
**3.0**; `[0,2]` dão **2.0**. São tensores de controle, não scores do checkpoint.
Linhas vazias podem criar lacunas nos IDs. Mascarar por `counts>0` e testar exemplos
sem texto e batches mistos. **Não atribuo mudanças nas AUCs históricas a este bug.**

### M3 — O resumo admite comparações inválidas e cobertura fictícia

[runner.py:119](/Users/Master/Downloads/LCC-judge/bakeoff/runner.py:119) agrupa
modelo/profundidade/kind sem validar a identidade da execução nem correspondência
de case IDs. O merge em [:267](/Users/Master/Downloads/LCC-judge/bakeoff/runner.py:267)
não garante identidade de pesos/config/input na substituição parcial.

Controles reproduzidos: um caso repetido em duas versões/runs vira `n=2`, J=.25;
fact apenas do caso A e dois ruídos apenas do caso B produzem **J=D=1 e contexto
efetivo=512**, embora não haja caso completo. Exigir triplets completos, unicidade,
suite/case-set, input hash, checkpoint/config/tokenizer/device e run compatíveis.

**Não encontrei corrupção desse tipo nos 5.784 rows atuais:** zero duplicatas por
célula/caso/kind, conjuntos por kind balanceados e nenhuma célula com versões ou
devices distintos. Muitos registros antigos têm proveniência desconhecida; isso
continua desconhecido, não certificado por ausência de conflito.

### M4 — Loader aceita head incompleta; resume pode reescrever época incorretamente

Em [adapters.py:259](/Users/Master/Downloads/LCC-judge/bakeoff/adapters.py:259),
`strict=False` rejeita `unexpected` mas ignora `missing`. O passe independente
demonstrou que uma head inteira ausente é aceita. Exigir todos os tensores da head,
pooling e camadas adaptadas; permitir ausências apenas do backbone congelado correto.
**Os 12 checkpoints com config auditados têm as heads esperadas.**

[train.py:157](/Users/Master/Downloads/LCC-judge/specialist/train.py:157) reinicializa
RNG; resume não salva/restaura RNG ou valida dataset/pooling/hiperparâmetros.
Retomar época 3 com `--epochs 2` não treina e pode gravar `current_epoch=2` em
[:269](/Users/Master/Downloads/LCC-judge/specialist/train.py:269), apesar de pesos e
histórico da época 3. Registrar a última época efetiva e recusar incompatibilidades.

**Não encontrei incoerência nova nos dois checkpoints clean:** epoch=3, histórico
[1,2,3]. Os antigos exp02d ainda declaram reconstrução a partir de logs em
[training_meta.json:36](/Users/Master/Downloads/LCC-judge/models/exp02d-unfreeze2/training_meta.json:36).
Esses metadados não viram recibos originais de treino pela existência do JSON.

### M5 — Baselines de embeddings não usam as receitas oficiais

[adapters.py:193](/Users/Master/Downloads/LCC-judge/bakeoff/adapters.py:193) aplica
mean pooling genérico. O [BGE oficial](https://huggingface.co/BAAI/bge-small-en-v1.5)
recomenda CLS; o [GTE oficial](https://huggingface.co/Alibaba-NLP/gte-multilingual-base)
usa primeiro token e sua implementação específica. O roster GTE ainda prefixa
ambos os lados; a receita oficial consultada não faz isso. O erro real de carga
de GTE está no JSON e não é um resultado de qualidade.

Preservar as linhas históricas como receita genérica; medir baselines oficiais
em inputs/suite/custos iguais. Revisar e fixar qualquer implementação remota antes
de executá-la. O bakeoff antigo com n=8 versus specialist n=62 não sustenta ranking
de superioridade. O aviso atual de versões é correto; não elimina o confundimento.

### M6 — Probes não isolam apenas valores nem comprovam 53/54 domínios inéditos

“Pure lexical matching cannot” em
[probes.py:8](/Users/Master/Downloads/LCC-judge/bakeoff/probes.py:8),
[runner.py:169](/Users/Master/Downloads/LCC-judge/bakeoff/runner.py:169) e
[Sprint:27](/Users/Master/Downloads/LCC-judge/SPRINT_02_BAKEOFF.md:27) é forte demais.
No controle body-only, removendo implicitamente números via regex `[a-z]+`,
**46/62 pares têm conjuntos de palavras alfabéticas diferentes**. Exemplo:
[retry_storm:159](/Users/Master/Downloads/LCC-judge/bakeoff/probes.py:159) inclui
`deadlock/abort` versus `none/ok`. O seed inclui `kind` em
[:568](/Users/Master/Downloads/LCC-judge/bakeoff/probes.py:568), mudando também filler.
Isso demonstra confounds, não a acurácia de um classificador lexical não executado.

A afirmação 53/54 não tem contagem semântica independente. O log atual já a retirou
e registra overlap de rollout/pool/cache, além de raft:
[experiments.md:269](/Users/Master/Downloads/LCC-judge/research/experiments.md:269).
Autoria manual independente do gerador não equivale a domínio novo.

v1.2 foi usada repetidamente para seleção/diagnóstico; deve ficar como conjunto
exploratório. Criar eval novo por famílias com filler idêntico, objetivos trocados,
anomalias irrelevantes e controle de palavras de saúde. Congelar antes do treino;
reportar paired, pooled e macro sem substituir a métrica do gate.

### M7 — Cobertura nativa e comparação de eficiência continuam incompletas

O checkpoint histórico aceito tem 0/512/4096/16384; **4K só n=4**, sem 8K/32K.
O clean tem n=62 até 4K, mas **186/186 inputs em depth nominal8192 foram cortados**.
Nem isso nem o dado v0.2 de 32K certificam a janela do clean. Evidência:
`verify_snapshot.py`, [Sprint:81](/Users/Master/Downloads/LCC-judge/SPRINT_02_BAKEOFF.md:81).

O “judge ≥.70 floor holding through 16K” em
[Sprint:50](/Users/Master/Downloads/LCC-judge/SPRINT_02_BAKEOFF.md:50) precisa de
qualificação: no histórico aceito, **J@0=2658/3844=.691467**, abaixo de .70;
off-control existem .779@512, .750@4096 somente n=4 e .756@16384, sem 8192.
Se a frase incluir o controle, é falsa; se descrever só as células off-control
medidas, não demonstra todo o intervalo nem cobertura completa de n=62.

A medição CPU clean tem dossiê load+scoring **20.38 s**, warm por bloco
**192.40 ms**, RSS fp32 **915.4 MiB**; M8 exige também <50 ms/bloco. M9 int8 não
medido. Não há comparação end-to-end, com quality matching, cache/restauração/
geração/retries, contra Laya/Jev. O Laya warm com cache e este workload sem cache
não devem ser confundidos. Evidência: `bench-cpu-unfreeze2.json`,
[AUDIT_RESOLUTION:131](/Users/Master/Downloads/LCC-judge/research/audit-2026-10-03/AUDIT_RESOLUTION.md:131).

### M8 — Replay e verificador ainda não produzem ground truth admitido

O piloto real falha as metas provisórias e varia metadado seed entre repetições;
o backend é alias mutável. Seis fixtures executáveis e 14 contratos tipados não
reproduzem serviços originais. O acerto do campo mecanismo não certifica toda a
prosa — limitação **já documentada**, não descoberta ocultada.
[replay report:45](/Users/Master/Downloads/LCC-judge/research/replay-real-2026-10-03/REPORT.md:45).

A nova receita PDB teve 0FP/0FN/0UNKNOWN em 112 controles curados, contra 27FN da
revisão acoplada, mas muda pergunta/representação simultaneamente e compartilha
arquétipo/autor. Não isola uma causa única nem valida o modelo specialist.
O próprio relatório registra gateClaim DOWNGRADE e zero P2:
[PDB report:92](/Users/Master/Downloads/LCC-judge/research/pdb-routing-2026-10-04/REPORT.md:92).
Faltam referências independentes dos contratos e replay do protocolo corrigido.

### M9 — Harness genérico deixa anotação de gabarito no ID

[tasks.py:28](/Users/Master/Downloads/LCC-judge/replay/tasks.py:28) conserva
`block_id`; há `blk_02_decisive` em
[:89](/Users/Master/Downloads/LCC-judge/replay/tasks.py:89).
[harness.py:127](/Users/Master/Downloads/LCC-judge/replay/harness.py:127) envia esses
IDs enquanto o comentário afirma ocultar o gabarito. O controle puro confirma.

**Não encontrei esse vazamento no piloto real de 120 chamadas:** `make_packet`
troca os IDs por hashes. Aplicar a mesma disciplina ao harness genérico e auditar
IDs/metadados/caminhos, não apenas o campo `is_decisive`.

### M10 — Verificações históricas são dependentes do HEAD, ledger e mtime

[PDB verify:42](/Users/Master/Downloads/LCC-judge/research/pdb-routing-2026-10-04/verify.py:42)
e [calibração verify:37](/Users/Master/Downloads/LCC-judge/research/verifier-calibration-2026-10-03/verify.py:37)
exigem hash da fonte atual igual à executada. Um conserto legítimo quebra a
reprodução histórica. Ledgers filtrados por feature exigem exatamente 240/140
registros; novas chamadas legítimas também quebram essas auditorias.

`mtime` em [PDB:83](/Users/Master/Downloads/LCC-judge/research/pdb-routing-2026-10-04/verify.py:83)
e calibração:74 muda com clone/cópia/extração; não prova portablemente preregistro.
Conferir fontes/ledger do run arquivado, independentemente do código atual, e
registrar congelamento/eventos/commits. Isso não implica que os experimentos
passados tenham sido ajustados após eval; implica que a prova atual não é portátil.

### M11 — Payload e licenças precisam de seleção para distribuição

O inventário novo exclui esta pasta de auditoria e registra aproximadamente 869 MiB.
`models/exp05-joint-detect/weights.pt` tem **599.271.059 bytes**, acima do limite
de arquivo do Git comum no [GitHub](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).
Há optimizers, `.pyc`, `.freebuff/project-id` e binário compilado. O comando
`file research/pdb-routing-2026-10-04/pdb-oracle` retorna Mach-O arm64; o verifier
exige esse binário/hash, portanto não roda como está no Linux.

Não há LICENSE raiz, política de licença dos dados/pesos nem avisos agregados de
terceiros. Os cabeçalhos Apache do código Kubernetes copiado estão preservados;
não concluo violação em um workspace ainda não publicado. Escolher licenças e
proveniência antes da distribuição, separar pesos em registry/release com hashes,
arquivar estados contaminados com marcação explícita e oferecer build portátil
do oracle. Não apagar história experimental para maquiar o release.

## Menores

### L1 — Entrada pública e contribuição não estão preparadas

O inventário não encontra README raiz, CONTRIBUTING, CITATION.cff, SECURITY,
CODE_OF_CONDUCT, `.github/workflows` ou `.gitignore`. O
[bakeoff README:10](/Users/Master/Downloads/LCC-judge/bakeoff/README.md:10) usa venv
pessoal e ainda descreve n=8 em [:35](/Users/Master/Downloads/LCC-judge/bakeoff/README.md:35).
Documentos internos extensos não substituem um percurso de instalação/demo/contribuição.

### L2 — Requisitos históricos precisam de status de supersessão

[docs/00:3](/Users/Master/Downloads/LCC-judge/docs/00-vision.md:3) ainda diz que nenhum
treino começou; [docs/02:15](/Users/Master/Downloads/LCC-judge/docs/02-model-requirements.md:15)
mantém 32K mínimo como MUST, enquanto o redirect atual seleciona ≤8K por bloco.
Os documentos identificam Sprint 0, portanto são históricos; sem índice de decisões
ativas/superseded, o leitor público não sabe qual requisito vigora. Manter o
histórico e adicionar ponte explícita para requisitos/ADR atuais.

### L3 — RSS do bakeoff assume macOS

[adapters.py:72](/Users/Master/Downloads/LCC-judge/bakeoff/adapters.py:72) divide
`ru_maxrss` por 1e9. No Linux a unidade é KiB, o que produz erro próximo de 1024×.
Corrigir por plataforma e medir processos isolados; high-water mark do processo
compartilhado não mede o footprint individual de cada candidato. As medidas CPU
dedicadas posteriores devem permanecer separadas das linhas antigas.

## Fechamento dos sete itens da auditoria original

| Item | O que encontrei no estado atual |
|---|---|
| 1. Gate a partir do JSON | **Confere:** J16K=2907/3844=.7562434964; D16K=1965/3844=.5111862643; nenhum depth passa .90; contexto efetivo 0 é sentinel, não controle aprovado. Não achei divergência desses números com o status vigente. |
| 2. 32K | Sem medição do checkpoint aceito/clean. As cifras .828/37s são v0.2/n8/MPS; o redirect as qualifica corretamente em Sprint:58. Há dado histórico para elas, mas não sustentam 32K atual ou CPU. A narrativa de prova de posições foi enfraquecida após o bug RoPE. |
| 3. Redirect docs/08 | **Cumprido documentalmente agora:** Sprint:56–75 e docs/08:38–47 selecionam abandono de >8K por sequência e envelope experimental por bloco. Não achei ausência atual da decisão. A hierarquia continua sem vitória medida. |
| 4. Docs, versões, caminhos, epochs | Métricas centrais e verificadores atuais conferem. Os avisos de versões/dispositivos e de metadados reconstruídos existem. Cross-version não permite comparação direta; paths privados e novas falhas de portability/resume são achados, não todos os números falsos. Não houve certificação exaustiva de toda frase numérica histórica. |
| 5. Treino/teste | **v0.3 ainda contaminado:** 172 train +32 val exemplos com assinaturas holdout. IDs de domínio sozinhos escondem distractors. **v0.4 clean:** 18 domínios, zero assinaturas dos quatro holdouts em train/val; splits/hashes passam. Não achei novo vazamento literal no clean. 53/54 novidade semântica não se sustenta e já foi retirada. |
| 6. Buracos adicionais | Provider/target, sandbox, agregação de linhas/células, loader/resume, recipes de baseline, gabarito em IDs, reprodução pública, novidade e release packaging descritos acima. TODO dentro de fixture de código não foi contado como trabalho de implementação abandonado. |
| 7. Prioridade real | Confiabilidade, contrato e reprodução precedem novo treino/32K; normalização pode ser controle barato, mas não corrige ranking invertido; custo deve incluir todo o fluxo e qualidade. Ordem e gates abaixo. |

**Pontos positivos preservados:** resultados negativos atuais estão explícitos;
raw scores e fontes executadas foram conservados; empates não contam como vitória
no gate; contexto usa AUC sem arredondar; clean e contaminado estão distinguidos;
produto joint negativo não foi adotado; sintéticos e replay real estão fora do treino.
Não encontrei evidência de que o resultado PDB tenha sido apresentado atualmente
como certificado populacional ou avanço do modelo.

A checagem limitada de padrões em 3.292 arquivos de texto não encontrou tokens/chaves
evidentes. **Não é certificado de ausência de segredos, dados pessoais ou direitos
de terceiros**, nem auditoria completa de segurança. Não invento um segredo encontrado.

## Conceito recomendado e contribuição testável

Posicionamento de projeto: **motor local hiper especializado em decisões de
compilação de contexto com preservação de outcomes**, provider independente usado
pelo LCC. É uma meta
de pesquisa; a descrição pública deve separar o que existe do que será treinado.

| Camada | Responsabilidade e primeiro contrato |
|---|---|
| LCC | Context IR, proteção, orçamento, seleção, dependências, restauração, policy e recibos |
| Novo modelo | sinais tipados de utilidade/necessidade e incerteza; escopo explícito de perguntas; nenhum texto gerado substitui evidência |
| Adapter | converte contrato nativo para SemanticProvider; declara o que suporta; erro/OOD/truncamento leva a preservação/abstenção |
| Pesquisa/eval | executor/verificador independentes, dados de outcome, frozen eval e custo completo |

Primeiro marco: substituir a pergunta de preservação de bloco usada por LCC num
escopo validado. Não anunciar suporte a todo `noul/choice/score` só porque há um float.
Depois expandir necessidade/criticalidade/redundância; suficiência e routing precisam
de datasets e gates próprios. Essa progressão conserva a intenção de inteligência
local ampla sem fabricar capacidades.

“Próprio” deve significar contrato, dados, treinamento, pesos adaptados e runtime
controlados pelo projeto. A adaptação de um backbone existente é compatível com esse
objetivo; pretraining do zero precisa de justificativa empírica. A versão inicial
deve priorizar poucas decisões com grande efeito no LCC, execução não generativa,
reuso de scores por hash de input/modelo e abstenção fora do escopo. O caminho de
inferência não deve depender de Jev/Hermes; seu uso em pesquisa/rotulagem é separado.

“Rápido e leve” requer publicar latência fria/quente, p50/p95, memória residente,
tamanho baixado, cobertura útil e qualidade no mesmo workload. A medida fp32 atual
não certifica esse objetivo. Reduzir backbone/destilar/quantizar são candidatos
posteriores à definição do alvo, comparados por Pareto. Uma head pequena sobre um
backbone grande não deve ser descrita como se só a head fosse o custo do motor.

O estimando do futuro label deve declarar tarefa, conjunto, executor e verificador.
Uma definição operacional possível é:

```text
Δ_i(x, C, E, V) = média_z [V(E(x, C, z)) − V(E(x, C sem bloco i, z))]
```

`z` representa variação de geração/ambiente; controlar pareamento, resets e ordem.
Esse label é condicionado ao executor, não necessidade universal. Três chamadas
concordantes não identificam, por si, uma probabilidade causal estável.

Um buraco conceitual adicional: duas cópias podem ser removidas individualmente
sem efeito, mas remover ambas causa falha. Drops simultâneos a partir de labels
independentes são inseguros. Criar controles de grupo (quatro coalizões de dois
blocos) e evidência complementar/contraditória antes de alegar redundância set-level.
Isso não exige inventar agora um Transformer hierárquico.

Para um paper positivo, comparar supervisão de outcome versus relevância/teacher
com mesmo backbone, dados/custo comparáveis e, como protocolo proposto, pelo menos
três seeds; testar famílias e executor externos ao treino. A unidade estatística
é tarefa/família, não os 3.844 pares como observações independentes. Dimensionar eval
pela precisão/poder requerido; declarar margem de não inferioridade antes de olhar
resultados. AUC de probe é diagnóstico; task success, critical recall, restauração e
custo end-to-end sustentam a contribuição. O paper pode relatar resultado negativo
se a hipótese falhar, sem mudar o gate.

## Próximos passos, em ordem

Critérios abaixo são propostas para execução futura, não resultados já alcançados.

1. **Conter replay e congelar evidência por run.** Desabilitar execução não confinada,
   ocultar anotação em IDs, exportar ledger sanitizado e verificar fontes arquivadas
   sem depender do HEAD/mtime. **Sucesso:** 100% dos casos dos controles de contenção
   bloqueiam filesystem/rede do host; todo timeout encerra descendentes; zero gabarito
   no payload; audits históricos continuam passando após editar código atual e
   acrescentar um novo run. Custo baixo de engenharia; evita invalidar dados novos.

2. **Preparar pacote público reproduzível e entrada comunitária.** Manifestos/locks,
   revisão HF, pesos separados e checksums, licenças/avisos de código-dados-modelo,
   README com estado real, quickstart, model/dataset cards, CONTRIBUTING, CITATION e
   CI. Atualizar requisitos ativos e related work com CICL/CMI/RepoShapley.
   **Sucesso:** instalação em ambiente vazio; suite + audit offline em Linux e macOS
   sem paths privados/keys/rede; links de entrada válidos; nenhum arquivo >100MiB no
   payload Git comum; cada artefato distribuído com origem/licença/hash. Documentação
   comunitária pode avançar em paralelo; publicação experimental não espera um modelo
   vencedor. Escolha autoral de nome/licença permanece decisão do projeto.

3. **Corrigir invariantes do código e congelar um benchmark justo.** Guards de head,
   células/runs, linhas sem tokens, RNG/resume e unidades RSS; baseline oficial;
   novos controles de objective/filler/famílias. **Sucesso:** todos os contraexemplos
   desta auditoria viram regressões; célula inválida é rejeitada; retomada tem trace
   equivalente sob ambiente determinístico; cada célula compara mesmos inputs/casos;
   eval novo permanece intocado. Não sobrescrever scores antigos após correções.

4. **Entregar o contrato mínimo de provider atrás de feature flag.** Selecionar as
   perguntas reais do LCC, schema versionado, identity/usage/window e abstention;
   manter policy/proteção no LCC. **Sucesso:** 100% dos fixtures de contrato suportado
   passam; perguntas fora do escopo recusadas; inferência com rede bloqueada;
   erro/OOD/truncamento nunca causa drop automático. Isso comprova integração,
   ainda não qualidade; não é autorização para substituir o default.

5. **Validar contratos de outcome e repetir o piloto corrigido.** Obter referência
   independente para 20/20 tarefas, incorporar a receita de verificador em protocolo
   novo, usar prompts idênticos e registrar backend/seed efetiva. **Sucesso inicial:**
   120 recibos completos; ≥95% concordância e ≤10% UNKNOWN como metas provisórias,
   ou critério justificado/congelado antes do eval; erros por tipo e custo disponíveis.
   Manter zero admissão quando referência/confiabilidade falhar. Crescer por famílias
   e adicionar coalizões antes de tratar esses labels como treino de necessidade.

6. **Escolher supervisão pelo menor experimento decisivo.** Primeiro confirmar receita
   fixa de normalização em objetivos e conjuntos candidatos novos: **ΔJ≥.03, limite
   inferior CI95%>0, perda D≤.01**; reportar ECE/reliability se alegar probabilidade.
   Depois controle pareado para detect/transferência: **D≥.70 em 0/512, ganho positivo,
   perda J≤.02** como milestone, preservando o gate final **.90 nas duas famílias**.
   Não treinar nas quatro famílias OOD para melhorar seu número. Para necessidade
   real, usar outcome admitido e informação do conjunto; comparar ao teacher com
   orçamento/seeds pareados. O z-score monotônico não cura inversão intradomínio.

7. **Medir janela nativa e Pareto no LCC; então otimizar.** Fixar total HF incluindo
   objetivo/special tokens/tail e testar evidência perto da janela, n=62×3, **zero
   cortes/erros**, sem chamar 8192 cl100k de 8192 HF. Comparar chunks/agregador simples
   antes de hierarquia. Contra mechanical/Laya/Jev no mesmo eval: qualidade de outcome
   não inferior sob margem pré-fixada, direção Pareto positiva com CI por tarefa e
   custo completo (compile+score+geração+restauração/retries, frio/quente/cache).
   Para o orçamento atual, exigir **ambos M8: <50ms warm/bloco e ≤43s/dossiê**;
   M9 só após medir int8/regressão. **Sucesso de substituição:** gates de qualidade e
   custo passam no escopo declarado; falhas fora dele preservam evidência. Só então
   promover o provider; paper/weights seguem exatamente a conclusão observada.

Não priorizar agora 32K/64K ou Track C, o produto joint já reprovado, treino das
dezenas de heads planejadas, arquitetura hierárquica antes de beat simples,
retentativas seletivas de UNKNOWN, novos claims de SOTA/originalidade universal ou
quantização como substituto de qualidade. Medir 32K do checkpoint contaminado só
completa arqueologia; oferece menos decisão que contratos, OOD e replay confiável.

Para atrair contribuição, abrir problemas reproduzíveis como estes guards, receitas
oficiais, fixtures externas e ports do oracle, com critério de aceitação. Um demo
local pequeno que exponha limites, uma tabela justa e um protocolo de contribuição
curto tornam o projeto avaliável. Não há evidência que permita prometer estrelas.
