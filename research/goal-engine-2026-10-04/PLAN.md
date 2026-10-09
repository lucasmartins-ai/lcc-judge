# Goal — motor especializado + LCC

Iniciado em 2026-10-04 por autorização explícita do usuário para concluir o plano.
Originalidade é avaliada no conjunto motor + LCC, não exigida do motor isolado.
Motivação: a janela útil da Laya limita seu uso; reduzir o escopo semântico para
aumentar contexto útil, qualidade e eficiência local. Adaptar backbone é permitido.

Estado consultado novamente em2026-10-08: `get_goal` retorna `goal: null`, sem
goal ativo ou orçamento informado. `usageLimited` pertence ao checkpoint anterior;
não é o estado atual desta chamada. O objetivo ainda não foi alcançado. A avaliação final local terminou e rejeitou
as três seeds; a auditoria independente dos recibos passou.
[pilotos atuais](goal-embedding-pilot-v1/RESULTS.md) registram recibos e próximos
passos. Os registros ACTIVE anteriores são históricos, não promessa de novas
continuações automáticas; a continuação aqui foi autorizada diretamente pelo usuário.

O diagnóstico offline do final está concluído; cutoffs hipotéticos não cumprem
remoção/UNKNOWN e não foram adotados. O piloto seguinte também terminou: seed101,
três epochs finitos, validação pooled .625629 / within .694824, rejeição .001953 e
UNKNOWN binário .998047. Auditoria independente dos recibos passa com errata
explícita do caminho relativo original. 247 testes / zero skips em 17.904s. A sequência
executada está fechada como falha. A [revisão semântica](semantic-goal-review-v1/REVIEW.md)
está concluída como evidência exploratória, sem revisão humana independente.
O contrato de oito campos foi congelado e o único probe de interpretação foi
executado sem treino, com pesos imutáveis e controle lexical. Ambos falham os
gates. Observações exploratórias da validação neural: precisão 197/1048=.187977,
cobertura aceita 240/240=1.0, vínculo correto 197/240=.820833 e UNKNOWN
88/896=.098214. Foram 27.696 pares completos / 2.949.948 tokens, sem cortes/erros;
auditoria dos recibos e revisão independente de código/matemática passam.
Uma lacuna na checagem do resumo/ação foi corrigida com auditor suplementar,
preservando as fontes congeladas. 252 testes / zero skips em 16.665s.
O gate bloqueou a classificação MEASURED (.82 suporte), exigindo INFERIDO — nao
medido (falta medicao repetida ou fonte independente); não houve retry. Revisão
humana de semântica permanece pendente. Etapas 1/2 concluídas; 3/4 não executadas
porque o gate de desenvolvimento falhou. A API tipada ainda exige metadados
ausentes nos registros atuais. A continuação abaixo testa a hipótese de suporte/
campo separado e também falha. Próxima proposta: perguntas completas e contrastes
por famílias, com nova separação antes do treino. Não lançar mais seeds/finais
ou ajustar definições nos probes rejeitados.

## Contrato de execução

A continuação autorizada treinou separadamente suporte/campo em dois pilotos
delimitados, ambos rejeitados. Cabeças sobre12 scores salvos (117 parâmetros)
não têm política viável no treino; o diagnóstico zero reduz falsos aceites para197,
mas acerta apenas139/240. O piloto seguinte usa384 dimensões do encoder congelado,
3.465 parâmetros/200 passos,2.308 perguntas/57.727 tokens novos. Passa no treino,
mas a política congelada acerta9/240 e aceita55 fora do escopo na validação.
Auditorias e uma revisão independente reproduzem os números;256 testes sem skips.
O gate de claims bloqueia MEASURED (.66 suporte/2.94 força); qualificação exploratória
preservada. Há uma lacuna menor de metadados start/load adiada, com bytes atuais
coerentes e pinados no manifesto geral. Sem confirmação nova, LCC, P2 ou adoção.
Próxima proposta: corpus de perguntas completas com famílias e contrastes de
suporte/ambiguidade, traduções juntas no split e revisão humana; preservar o antigo
controle197/240. Não ajustar validação ou investir mais epochs nestes candidatos.

- Preservar raw scores, recibos, protocolos e checkpoints históricos.
- Congelar fontes antes de corrigir; verificar história com fontes arquivadas.
- Testes de regressão falham antes da correção; não usar APIs para matemática.
- Sem retries seletivos, treino nos holdouts ou troca de gate para fabricar sucesso.
- Publicação externa/default do LCC dependem de conclusão dos gates e autorização
  específica para publicação; preparar tudo localmente.
- Não marcar o goal como concluído enquanto houver trabalho necessário; limites
  de uso da ferramenta não são conclusão nem pausa solicitada pelo usuário.

## Etapas e critérios

1. [x] Replay confinado, IDs sem gabarito e audit offline por execução.
   Critério: controle de filesystem/rede/recursos; UNKNOWN sem runtime; históricos
   auditáveis sem paths privados, HEAD atual ou mtime.
2. [x] Instalação, versões/revisões, artefatos/licenças e entrada pública.
   Critério: ambiente limpo instala; teste/audit offline; pesos separados do Git.
3. [x] Corrigir linhas, células, loader/resume, métricas e receitas de baseline.
   Critério: regressões reais; mesma população/input; histórico preservado.
4. [x] Provider mínimo para decisões de contexto, contrato nativo e feature flag.
   Critério: integração com LCC; escopo restrito, offline e preservação em dúvida.
5. [x] Referências externas de outcome e piloto novo sob protocolo congelado.
   Critério: 20 contratos referenciados; repetição/erros/custo medidos; admissão
   condicionada à confiabilidade; nenhuma promoção dos dados antigos.
6. [x] Experimentos delimitados de normalização, detect e supervisão especializada.
   Critério: eval novo, controle justo, ranking OOD e calibração separados; reportar
   resultados negativos. Definir custo/seeds antes de executar cada experimento.
7. [x] Janela HF sem cortes e Pareto motor + LCC versus Laya/Jev.
   Critério: qualidade útil e custo completo; medir fronteira/chunks antes de expandir
   arquitetura. Otimizar/destilar/quantizar candidato útil e medir regressão.
8. [ ] Relatório final, preparação de release e decisão de adoção fundamentada.
   Critério: nada anunciado como capacidade sem evidência; tarefas e limites públicos.
   Sub-status 2026-10-08 (ainda aberto): Lacuna de metadados start/load
   fechada por auditor suplementar (`audit-metadata-v2.json` nos dois pilotos, PASS).
   Lacuna da API tipada documentada em [TYPED_API_METADATA_GAP.md](TYPED_API_METADATA_GAP.md).
   Próximo ciclo: [goal-family-corpus-v1/PLAN.md](goal-family-corpus-v1/PLAN.md).
   Revisão humana dos rótulos (v2, PT, 60 itens, revisor único): concordância .417,
   gate falha; não separa rótulo errado de pergunta técnica demais para o usuário-alvo.
   Próxima revisão sobre pedidos reais do LCC. Ver [human-review-v2-pt/RESULTS.md](human-review-v2-pt/RESULTS.md).
   Pedidos reais: 3.782 prompts próprios importados e redigidos (só em ~/.lcc); catálogo de
   13 categorias de necessidade de contexto; confirmação do dono 41/56=.732 em casos difíceis.
   Ver [request-taxonomy-v1/README.md](request-taxonomy-v1/README.md).

## Fechamento das medições e próximo ciclo

O bloco de ranking anterior passou135 testes do motor incluindo quatro integrações locais LCC, sem skips;
os52 checks focados no consumidor são do bloco anterior; pacote instalado e integrado ao LCC preserva bytes offline.
744 pares novos de fronteira HF completos: perto de 8192, J .8345 / D .7360;
nenhuma célula passa .90. Pareto: 96 execuções reais em quatro contratos curados,
dossiês de 8K/32K. Motor e Laya removem zero contexto nesta política; Jev remove
≈79% dos caracteres e passa o critério condicional apenas em 8K. Inferência Linux
arm64/Python 3.13 e macOS arm64/Python 3.14 verificada; outras plataformas não.
Normalização nova em 64 triplets holdout: parent J .6350→.7048, CI do ganho
[-.0391,.1592]; BCE selecionado .6143→.6708, CI [-.0745,.1582]. Não adotar.

O objetivo permanece em aberto: **substituição útil/eficiente não foi atingida**.
Os ensaios negativos fecham candidatos, não redefinem o objetivo como mera auditoria.
Relatório e MODEL_CARD.md registram a decisão shadow e a lacuna que determina
o próximo trabalho autorizado: treino e benchmark precisam responder à operação
KEEP-relevance. O corpus atual separa incidente anômalo de saudável, enquanto
a pergunta do LCC admite evidência saudável como útil. O antigo gate de incidente
continua falho; um gate de relevance novo deve ser explicitamente diferente.

O ciclo P1 foi concluído: dados 2016/672/504, 12 domínios de treino e seis finais,
zero overlap de entidades/content hashes e zero spans cortados (HF máximo 628).
Seis treinos × três épocas, batches/seeds/init do head pareados. Validação escolheu
last-two: AUC final média .7145 vs frozen .6380; todos falham .90. Rejeição da
anomalia em entidade errada é apenas 1.85% no candidato selecionado. Nenhuma adoção.
Controles typed/lexical/parent/Laya completos; BGE corta 99/504 inputs e só seu
subset uncut é diagnóstico. Raw/épocas/seleção/gates foram auditados offline.

A rota independente rank_observations é explícita e sem dependências ML: mantém
registros saudáveis/anômalos no escopo entity/field/UTC; opacidade/ambiguidade fica
UNKNOWN/KEEP. Não muda defaults/provider neural. Em 18 dossiês sintéticos 8K/32K/128K,
preserva 100% dos registros pedidos e UNKNOWN; remoção mínima 94.66/98.71/99.68%.
Isso demonstra recuperação literal de registros, não outcome LCC ou necessidade P2.

O piloto explícito foi concluído:144 outcomes reais, sem erros/timeouts,36/36
respostas corretas na rota local. Remoção média92.50%/98.10% bytes em8K/32K,
100% observações/UNKNOWN. Jev também36/36; full34/36; Laya33/36 com os mesmos
bytes de full, então a diferença estocástica não prova efeito da compilação.
Contabilidade inclui cache:2,178,585 tokens input/66,840 output no executor;
591 chamadas Jev/602,669 input. Custos cold/warm/RSS suplementares e auditoria
independente estão em observation-lcc-pilot/. Nenhuma promoção geral/P2.

O ciclo semântico foi executado. MPS-v1 ficou incompleto por NaN na seed 303:
15 epochs finitos e três passes inválidos, sem final/seleção inventados. A origem
não se repetiu nos primeiros144 batches instrumentados CPU/MPS; não foi explicada.
Guardas de update e checkpoint foram corrigidas com regressões. CPU-v2 é outro
protocolo completo, não substitui o fracasso:18 epochs finitos, seleção emval,
final last-two pooled.5661/paired.6910/rejection.0417; todos os seeds falham.
Os quatro controles completos também não atingem.90. Relatórios/audits preservados.

O encoder de ranking compacto e a representação enxuta foram medidos: pooled
.6720/.6929, ambos falhos. Metadados com sets causaram erro depois de todos os
scores; auditoria offline fechou a matemática sem inventar setup/RSS perdidos.
O novo treino compacto2304/576/512 reserva oito pares finais; old18 agora todos
desenvolvimento.18epochs finitos, validação escolheBCE:finalpool.827947/within-goal
.854167/rejection.377604, todos os seeds falham. Input efetivo≤31tokens, zero cortes.
Controle genérico posterior(pool.822627) também falha;sem retreino/rescoringbase.
Fontes, pesos privados, recibos e audits preservados, modelos não adotados.

A primeira captura de68fixtures e o treino P1+UNKNOWN subsequente foram concluídos.
Dados:2108campos medidos,4864/1824/2496linhas,3676views únicos de treino. Três seeds
x3epochs finitos; mean finalpool.733249/within-goal.733796/rejection.102431.
UNKNOWN DROP7/16/8, todos em português; EN/PT pool.845684/.626288. Todos falham.
Receipt audit e hashes de pesos passam; isso não aprova o candidato.162testes
naquele bloco sem skips; fontes históricas preservadas. Ver tool-role-support-v1/RESULTS.md.
Pergunta/legenda sempre pareadas0:0/1:1emtrain é lacuna observada sem causa provada.
DU/DF/GZIP são holdouts de labels/strings binárias, três fontes compartilhadas,
não ausência dos recibos raw. Aqueles finals estão expostos; retry/UDP/Git estão
fora dessa primeira coorte, mas entraram na fase seguinte descrita abaixo.

A fase seguinte capturou 68 fixtures novas e 1.224 campos reais de retry/UDP/Git,
mais quatro fixtures de calibração excluídas. Build offline e auditorias de raw
passam. Supervisão de registro direto: 4.864/1.824/2.496 linhas, 3.592/996/864
inputs projetados únicos, quatro combinações de redação no treino, zero overlap
entre splits e zero cortes, recontagem real de tokens. As seis combinações finais
são novas, mas os 18 campos e três tools aparecem no treino. Não há holdout de
fonte nem ground truth de produção. Derivação/diagnóstico/utilidade ampla ficam
UNKNOWN; igualdade de campo não rotula a relevância geral do LCC.

O inicializador mantém o margin de ranking aprendido, encoder e dense do XLM-R;
testes reais e dois smokes expostos no artefato fixado passam (12 forwards).
Correção com gerador local evita alterar RNG de aceleradores. A preparação tinha
185 testes sem skips; o protocolo subsequente foi congelado e executado.

O treino retenção+suporte concluiu3seeds x3epochs:117.6Mparâmetros totais/3.7M
traináveis,2.025updates aceitos/1.111.464tokens de treino. Finalpool.643959,
within-goal.666233,rejeição.088252; todos falham,PTrejeição0. UNKNOWN DROP0,
mas oito UNKNOWN portugueses por seed viram KEEP. Auditorias de matemática,
seleção, pesos e parâmetros congelados passam sem aprovar qualidade. Final exposto.
Diagnóstico fixo da primeira seed em treino:pool.807571/within-goal.800130;
grafo de nove componentes desconectados. Quatro famílias finais UDP/Git mantêm
a preferência por um relatório sob ambos os objetivos, todos os seeds; limiar
global não corrige esse ordering. Causa por objetivo/capacidade/cobertura não isolada.
Ver tool-relation-support-v1/RESULTS.md e NEXT_DESIGN.md. Naquele bloco194
testes passaram sem skips. O objetivo condicional e suporte separado foram depois
implementados e verificados em um ensaio delimitado de desenvolvimento.

Seed101 x3epochs finitos,1.428updates/785.304tokens:treinopool.976310/within-goal
.972222,masvalpool.556345/within-goal.613426/rejeição.012731. UNKNOWNsemântico
reconhecido1.0/0DROP;78.18%dosbinários devalviramUNKNOWN. Objetivo e LR dohead
mudam juntos, sem causa isolada. Nenhum final original foi pontuado; ambos os
gates de política em desenvolvimento falham. Auditoria independente/bytes de
pesos PASS. Ver factorized-relation-dev-v1/RESULTS.md e NEXT_COVERAGE.md.
Naquele bloco199testes/0skips/19.210s incluindo LCC,RuffF/E9PASS. O goal
continua ativo; a ampliação dos dados descrita abaixo foi depois concluída.

Nova fase de dados concluída:96fixtures reais autorais/1.728campos,16calibração
excluídos/288campos. Retrysucesso/falha terminal,UDPleitura total/parcial/zero,
Gitclean/add/delete/mixed; rawcontagens/timestamps/blobs/status/diskPASS. Grafo
52pares conectado, redações/legendas/EN/PTcruzados32combinações. Supervisão
60.288/30.144linhas,50.084/23.692inputs efetivos únicos;0overlap/cortes/conflitos,
maxHFprojetado76tokens recontados. Na conclusão dos dados ainda não havia novo
score/treino; ver tool-relation-states-v2/RESULTS.md e NEXT_TRAINING.md.
O desenvolvimento balanceado posterior concluiu seed101 x3épocas finitas:
18.819updates/11.667.693tokens. Treino/valpool.983074/.968897,within.988845/
.977276; rejeiçãoval.810472,UNKNOWNbinário.389235. Preservação inclui KEEP ou
UNKNOWN; todos os campos/tools/52pares/redações são conhecidos. Ambos os gates
passam, assim como auditorias de métricas/calibração/ordem/bytes de pesos/custo.
Tentativa anterior incompleta preservada; custo treino combinado registrado
339.884pares/13.193.976tokens é limite inferior.232testes/0skips19.919s incluindo
LCC,RuffF/E9PASS. Sem final fresco, outcomesLCC, adoção ou publicação.
Ver varied-relation-dev-v2/RESULTS.md e NEXT_CONFIRMATION.md. Goal ativo.

Sequência histórica anterior à confirmação e ao piloto rejeitados acima:
1. Controle multilíngue congelado concluído:pool.785710/within-goal.846788;
   PTpool.742775vsoriginal.574650, ainda falho.4248forwards completos e auditoria
   raw/source/mathPASS. Sem suporte/DROP ou confirmação nova.165testes passam.
   Esse diagnóstico está fechado, sem retreinar nos finals expostos.
2. Capturas reais, redações cruzadas e nova confirmação de combinações foram
   preparadas e auditadas. Critério cumprido nesse escopo: raw/labels/tokens e
   zero overlap de inputs efetivos. A qualidade do modelo segue por demonstrar;
   dados de ferramentas em fixtures autorais não são sessões reais do LCC.
3. O candidato com prior preservado e o ensaio condicional foram executados e
   rejeitados. O segundo aprende ordering emtrain, masval/rejeição falham.
   Ampliação de redações/idiomas/UNKNOWN/grafo e estados reais concluída na
   coorte variada auditada. Treino balanceado após dedup implementado e fit/
   desenvolvimento agora passam. Congelar captura/redações/combinações finais
   inéditas e três seeds sob a mesma receita antes de nova confirmação.
   Preservar guarda finita e UNKNOWN. Cada seed/idioma pooled e within-goal
   ≥.90, recall≥.95, rejeição≥.70, reconhecimento UNKNOWN≥.95e0UNKNOWN DROP.
   Não aumentar épocas nem ajustar anchors nos candidatos/finals rejeitados.
4. Candidato aprovado requer outcome LCC fresco comfull/Laya/Jev,custo total e
   dossiês8K/32K/maior:success≥.90, perda≤.02, remoção≥.25eUNKNOWN inteiro.
   Quantização/adoção seguem somente depois desse resultado.
5. Ground truth P2 exige piloto confiável e revisão independente. Replay atual
   rejeitado; publicação/default depende de evidência e autorização específica.

Publicação/model hosting/manuscrito não estão prontos. Fonte e recibos estão
preparados localmente; o modelo continua experimental e sem download público.

32K não está proibido: uma nova medição só ganha prioridade quando responde uma
decisão concreta de cobertura/qualidade/custo. Não confundir tamanho declarado,
profundidade cl100k, input HF e cobertura útil de blocos do LCC.

## Estado após o primeiro bloco de implementação

Este registro do primeiro bloco é histórico. Estado atual: REPORT.md,
study-analysis.json e data/d6_referenced_pilot_v03/audit.json. Receitas oficiais
e cinco controles novos concluídos; três objetivos × três seeds × três épocas
concluídos, sem candidato aprovado. Novo replay: 120 chamadas tentadas, três
timeouts, 60% concordância/40% UNKNOWN; zero admissão P2. A tag antiga do bridge
e o campo execution_errors ambíguo estão preservados e auditados. Inferência do
wheel instalado em Linux arm64/Python 3.13 CPU/offline passou. 82 testes atuais
do workspace passam. Fronteira HF e Pareto do pipeline continuam em execução.

- Etapa 2: instalação limpa em macOS arm64, wheel/API e audit offline em Linux
  arm64 verificados. A instalação ML/inferência em Linux e outras versões Python
  continuam na matriz de release, sem alegação de suporte já certificado.
- Etapa 3: pooling, integridade de células, loader, resume/RNG e unidades RSS
  corrigidos. Restam receitas oficiais de baseline e medições novas sob essas fontes.
- Etapa 4: somente shadow, via `provider="specialist"` no checkout local do LCC,
  com contrato `rank_context`; defaults do consumidor não foram promovidos.
- 66 testes do pacote, incluindo integração com LCC, constam no log final.
- O gateClaim agregado retornou BLOCK; não interpretar esses controles como
  superioridade, segurança certificada ou aumento de contexto útil.
- O workspace agora tem Git local em `main`, sem commit inicial ou publicação.
- Próxima decisão: receitas/células de controle, seguida de contratos externos de
  outcome e protocolo novo; só então treino/normalização e Pareto de contexto.
