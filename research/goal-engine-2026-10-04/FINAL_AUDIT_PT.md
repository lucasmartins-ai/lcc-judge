# Auditoria final — estado local, 2026-10-05

O workspace foi preparado para um repositório próprio, mas **a substituição geral
da Laya/Jev no LCC ainda não foi demonstrada**. O goal permanece ativo. A intenção
é eficiência e contexto útil no conjunto motor + LCC; originalidade isolada do
modelo não é critério de adoção. Nenhuma publicação externa foi feita.

## Bloqueante

1. **O alvo de treino antigo diverge da operação do LCC.**
   `specialist/corpus.py` atribui positivo ao incidente e negativo ao decoy
   saudável. O KEEP do consumidor admite evidência saudável como útil
   (`/Users/Master/LCC/src/lcc/relevance/compactor.py`, KEEP_CRITERIA).
   A família J é um diagnóstico incidente/saudável, não ground truth de
   necessidade nem demonstração de raciocínio numérico. A alegação de ausência
   de atalhos lexicais foi removida do gerador de relatório e de RESULTS.md.
   O estudo novo `direct-relevance-v1/` usa o alvo P1 correto, com seleção em
   validação; não reclassifica o antigo gate como aprovado.

2. **Não há candidato neural aprovado para remoção de contexto.**
   Os estudos de heads, normalização e fronteira HF falharam nos critérios
   pré-definidos. No Pareto de 96 execuções, native/Laya removem zero contexto;
   Jev passa o critério condicional apenas em 8K, não em 32K. Evidência:
   REPORT.md, study-analysis.json, hf-frontier/audit.json, lcc-pareto/audit.json.
   O provider neural permanece opt-in/shadow; capacidades de sequência e somas
   de janelas não demonstram contexto útil.

   O piloto novo de observações explícitas foi concluído: 144 chamadas reais,
   36/36 respostas corretas na rota local, remoção média de 92,5%/98,1% bytes
   em 8K/32K e zero perda de observações/UNKNOWN. Isso sustenta apenas esse
   fluxo literal em seis tarefas sintéticas expostas; não substitui o neural.
   O estudo semântico subsequente tem AUC final .5661 em pares completos ≤79
   tokens; todos os candidatos falham. Evidência: observation-lcc-pilot/audit.json
   e semantic-tool-cpu-v2/audit.json.
   O MiniLM compacto posterior melhora a métrica pontual, mas também falha:
   finalBCE.827947/within-goal.854167/rejection.377604, todos os seeds rejeitados.
   O controle genérico(.822627) não melhora esse gate. Dados finais têm apenas
   oito famílias novas, vocabulário/schema/autor compartilhados; não são evidência
   independente de produção. Ver compact-relation-v1/audit.json.

   A captura de68fixtures tem2108campos reais, inputs autorais e4304contradições.
   O treino posterior concluiu3seeds x3epochs finitos:pool.733249, within-goal
   .733796, rejeição.102431 eUNKNOWN DROP7/16/8, todos portugueses. Todos falham;
   pooled EN/PT.845684/.626288. Auditoria de recibos/pesos passa sem aprovar o
   modelo. O final reúne três fontes correlacionadas, não P2/produção. Evidência:
   tool-role-support-v1/RESULTS.md e audit-weights.json.

3. **P2 não tem labels admitidos.**
   O piloto referenciado tentou 120 execuções e teve três timeouts reais;
   concordância .60 e UNKNOWN .40 falham .95/.10. Dois contratos continuam
   em quarentena e não existe revisão humana independente. Evidência:
   `data/d6_referenced_pilot_v03/audit.json` e OUTCOME_CONTRACTS.md.
   Esses dados não podem virar treino de necessidade.

## Material

4. **O gate original é aritmeticamente consistente; a cobertura é insuficiente.**
   Recomputado diretamente do JSON bruto: J@16384 = 2907/3844 = .7562434964;
   D@16384 = 1965/3844 = .5111862643, n=62. Contexto efetivo = 0 nas duas
   famílias. **Não encontrei divergência nesses números.** O controle J é
   .691467, portanto “J≥.70 em todas as profundidades” era falso e foi corrigido.
   A célula original de 4096 tem **n=4**, não 62; 8192/32768 estão ausentes.
   Evidência: original-gate-reverification.json e bakeoff/results/results.json.

5. **32K .828 é resultado histórico de outra condição.**
   Usa v0.2, n=8, probe v1.1, dynamic RoPE/MPS. Não sustenta o checkpoint v0.3
   aceito na época ou o controle limpo v0.4. Sprint/log agora qualificam a
   condição histórica; a leitura como capacidade do candidato atual seria sem
   lastro. A fronteira nova v0.4 usa pares HF completos até 8192, sem aprovação.

6. **A separação original de treino/teste foi violada no conteúdo.**
   Os 18 nomes de domínio dos itens não incluem os quatro holdouts, mas v0.3
   contém assinaturas deles em distractors: 172 train / 32 val. A afirmação
   “inteiramente fora” foi refutada. O corpus limpo v0.4 tem zero dessas
   assinaturas e splits disjuntos, verificados no audit histórico arquivado.
   A cifra “53/54 inéditos” não tem validação semântica e foi retirada; há
   sobreposição além de monitoring_flap/raft_leader_flap.
   Evidência: research/continuation-2026-10-03/verification.json e COMPLETION.md.

7. **As comparações históricas e a proveniência têm limites explícitos.**
   RESULTS.md reúne v1.0/v1.1/v1.2: não permite comparar modelos como se os
   inputs/populações fossem iguais. Os novos controles usam hashes iguais de
   input e populações identificadas. O protocolo matched-controls esqueceu o
   hash do summarizer; seu snapshot posterior não certifica execução temporal.
   Os cinco fontes registrados foram preservados e os AUCs recalculados do raw.
   training_meta antigo foi reconstruído de terminal: não é um estado de resume
   completo nem prova independente das épocas. Os novos treinos salvam um
   recibo por época e hashes. Evidência: MODEL_CARD.md,
   matched-controls/source-preservation.json e os audits arquivados.

8. **Havia perda de observações no treino a 1024 HF tokens.**
   Com o tokenizer atual fixado, 1135/2340 pares excedem o limite; 15 linhas
   relevantes são afetadas (11 parciais, quatro ausentes). Não são 1135 fatos
   perdidos. Isso não reexecuta nem explica causalmente o treino antigo.
   Evidência: training-input-coverage-details.json. O corpus novo tem zero
   cortes e zero spans incompletos no preflight.

9. **Houve treino não finito sem interrupção imediata.**
   semantic-tool-v1/last-two-303/epoch-1.json até epoch-3.json contêm NaN.
   O run falhou antes de salvar weights/val/seleção/final. Os outros cinco runs
   são preservados; a auditoria distingue 15 epochs finitos de três passes
   inválidos. O primeiro epoch instrumentado foi finito em CPU/MPS; a causa
   original permanece sem explicação. Guardas de loss/gradientes/update e loader
   foram corrigidas com regressões. CPU-v2 é um protocolo separado, não um
   resultado substituído: 18 epochs finitos e comparação final negativa.
   Comandos: audit_semantic_study --allow-incomplete; audit_semantic_study --out
   research/goal-engine-2026-10-04/semantic-tool-cpu-v2. Nenhuma estabilidade MPS
   é inferida dos testes ou do smoke de inferência.

10. **Input do executor estava contado sem cache no summary congelado.**
   O campo observed_input_tokens do piloto é input não cacheado. A auditoria
   independente agora concilia input + cache_read + cache_write + output:
   2.178.585 input com cache, incluindo 1.819.832 cache-read, e 66.840 output.
   Jev: 591 chamadas bem-sucedidas / 602.669 input. Não são valores de fatura.
   Os raws e o summary original ficam preservados, com a semântica documentada.
   Evidência: observation-lcc-pilot/audit.json e RESULTS.md.

11. **O resumo do MiniLM falhou após a inferência completa.**
   reranker-known-control/ não temrun.json: o processo não serializou os sets do
   loader. Todos os2304scores/threshold estavam salvos e a auditoria confirmou os
   números. O erro de gravação foi corrigido com regressão;setup/RSS originais
   perdidos ficam desconhecidos. Fontes executadas e traceback preservados.
   Comando:python -m research.audit_reranker_diagnostic.

12. **“Paired” identifica eixos diferentes nos ensaios.**
   Nos triplets antigos é fato/ruído sob o mesmo objetivo. No estudo semântico é
   o mesmo relatório sob dois objetivos. Os números são válidos para as definições
   registradas, mas não comparáveis entre eixos. Audits/relatórios novos mostram
   within_objective separadamente: BCE.8542 vs contraste de objetivos.9180.

13. **A proteção estrutural ainda não reconhece objetivo fora do escopo.**
   `measurement_projection.py` projeta as192/72/144perguntas semanticamente
   UNKNOWN do novo corpus; rejeita apenas os64/24/48registros sem vínculo
   estrutural. Não autoriza DROP, mas um futuro scorer não pode converter os
   primeiros em negativos silenciosamente. Três candidatos executados aprenderam
   o suporte emval, mas descartam7/16/8UNKNOWN no final português. O guard
   estrutural continua seguro; a generalização semântica foi refutada nessa
   coorte. Evidência:tool-role-support-v1/final raw/metrics e audit-weights.json.

14. **As relações difíceis anteriores não entram nessa primeira captura.**
   Pacotes/bytes, espera de retry/contagem e tracked/untracked ficaram fora dessa
   primeira coorte. A fase posterior capturou retry, UDP e Git, com os limites
   detalhados em tool-relations-grounded-v1/RESULTS.md; não é captura de IP/wire.
   As seis famílias finaisDU/DF/GZIP compartilham três fontes e
   alguns conceitos primitivos comstat.3676/1292/1674inputs projetados únicos
   entre4800/1800/2448linhas projetadas tornam inadequado tratá-las como tarefas
   independentes. Auditoria confirma0overlap entre splits, sem certificar
   independência semântica. Nenhuma correção daqueles fracassos foi demonstrada.
   DU/DF/GZIP estão fora das strings/labels binárias de treino, mas seus campos
   existem nos recibos brutos de todas as fixtures. Não são fontes ausentes do
   arquivo completo; UNKNOWN ainda usaWC entre splits. Não alimentar metadados
   ou comandos raw no modelo. Ver a definição exata em RESULTS.md.

15. **A cobertura de redação é pareada, sem combinações cruzadas.**
   Treino usa apenas alias0/caption0 e alias1/caption1; validação2:2. A diferença
   EN/PT é medida, mas causa por idioma/prior/redação não foi isolada. O controle
   multilíngue posterior melhoraPTpool.574650→.742775, ainda falho (global.785710).
   Fonte/input/raw/math/accounting auditPASS;165testes passam. Evidência:
   tool-role-support-v1/wording-coverage.json e semantic-next/multilingual-frozen-v1/
   RESULTS.md/audit.json. O final está exposto; próximo treino precisa confirmação
   fresca e relações reais ausentes. Não há aprovação geral de idioma/arquitetura.

16. **Igualdade do campo não é relevância geral do LCC.**
   O corpus novo pede explicitamente um registro direto. Contadores relacionados
   podem ser úteis para derivação ou diagnóstico, então essas perguntas amplas
   estão marcadas UNKNOWN e devem preservar o bloco. As 68 fixtures novas medem
   1.224 campos reais, mas continuam autorais. Os seis pares finais recombinam
   campos já vistos em treino; não são seis ferramentas ou domínios inéditos.
   Git mantém contagens de alterações fixas2/3, UDP bem-sucedido tem envio=recepção;
   864 inputs finais únicos entre2.448linhas projetadas impedem tratá-las como
   tarefas independentes. Auditoria de bindings/redação/tokens passa; o treino
   subsequente falhou, e outcomes LCC desse candidato não foram executados. Fonte:
   tool-relations-grounded-v1/supervision-v1/ e tool-relation-support-v1/RESULTS.md.

17. **Retenção do prior não resolveu ordering; treino também não passa.**
   Três seeds x3epochs finitos, final meanpool.643959/within-goal.666233/rejeição
   .088252; todas falham. PTnão descarta negativos; UNKNOWN DROP0, mas oito UNKNOWN
   semânticos portugueses por seed viram KEEP. Quatro famílias finais UDP/Git
   mantêm a preferência pelo mesmo relatório quando o objetivo muda (96/96matrizes
   por família/seed), portanto within-goal.50. No diagnóstico fixo da primeira
   seed em treino:pool.807571/within-goal.800130, abaixo de.90. O grafo de treino
   contém nove componentes de dois campos desconectados; os seis pares finais
   cruzam componentes. Não prova qual componente da receita causou a falha,
   mas invalida tratar o gargalo como simples escolha de cutoff. Auditorias
   independentes de scores/fit/contrastes/pesos PASS. Fonte:
   tool-relation-support-v1/{summary,audit,audit-weights-v2}.json e
   tool-relation-support-v1/fit-contrast-analysis.json.

18. **O objetivo condicional ajusta treino, mas transferência e remoção falham.**
   Ensaio separado de desenvolvimento,seed101/3epochs finitos:treinopool.976310/
   within-goal.972222,valpool.556345/within.613426,rejeição.012731. 78.18%dos
   binários devalviramUNKNOWN,emboraUNKNOWNsemântico reconhecimento1.0/0DROP.
   Ambos gates falham; nenhuma confirmação fresca nem score do final original.
   Objetivo e LRmudam juntos, não há causa isolada. Raw/axes/cutoffs/updates/epochs/
   hashes/bytes congelados passam na auditoria independente. Ampliar cobertura e
   estados reais/redações/idiomas é a próxima decisão. Evidência:
   factorized-relation-dev-v1/{summary,audit}.json e NEXT_COVERAGE.md.

19. **Cobertura dos dados ampliada; qualidade do novo modelo ainda não medida.**
   Nova fase concluída:96fixtures autorais reais/1.728campos,16calibração/288campos
   excluídos. Retries com sucesso/falha terminal, leitura UDPtotal/parcial/zero e
   Gitclean/add/delete/mixed variam; contagens/auditoria de eventos/timestamps/
   blobs HEAD/índice/status/disco PASS. O gap de contagens fixas2/3/envio=recepção
   continua verdadeiro no histórico, mas foi tratado nesta coorte separada.
   Grafo52pares conectado; redações/legendas/idiomas cruzados32combinações.
   60.288/30.144linhas,50.084/23.692inputs projetados únicos;0overlap/cortes/
   conflitos e tokens completos recontados (maxprojetado76). Labels de igualdade
   de campo permanecem estreitos; não há confirmação nova nem qualidade LCC.
   Dados deduplicados desbalanceiam0/1:25.016/18.282,UNKNOWN6.786. A próxima
   receita precisa pesos globais auditados. Fonte:tool-relation-states-v2/RESULTS.md,
   cohort-audit.json e supervision-v1/audit.json. Nenhum novo score/treino nesta fase.

## Menor / resolvido

- **Redirect:** agora está formalmente registrado em docs/08-roadmap.md e
  SPRINT_02_BAKEOFF.md: adiar Track C e sequências >8K, testar agregação por
  bloco. **Não encontrei a ausência de decisão no estado atual.** A escolha
  arquitetural está documentada; a qualidade da agregação continua a validar.
- Contagem da API corrigida: entradas apenas contadas são separadas de tokens
  realmente enviados ao encoder; rejeição de janela não infla encoded_tokens.
- A tag de ledger do replay referenciado foi corrigida no bridge; o defeito
  histórico permanece documentado e os 62 calls foram conciliados sem repetição.
- A métrica comum inicialmente contava só um tipo antigo de UNKNOWN semântico.
  Regressão e correção antes do novo treino incluem todas as três categorias
  broad/derived/diagnostic. Fontes antigas executadas continuam intactas. O
  auditor opcional F32-only não lê o bufferI64do upstream; checker aditivo verifica
  o arange conhecido e pesos/parâmetros congelados sem mudar protocolo ou scores.
- Links da entrada pública e artefatos essenciais foram conferidos; weights e
  containers ficam separados do Git. Falta hosting imutável para release de
  modelo. O scan de publicação é delimitado, não certificado de ausência de
  segredos em qualquer arquivo possível.

## Próximos passos, em ordem

1. O treino com prior preservado foi rejeitado. O ensaio com objetivo condicional
   de relevance e suporte separado foi diagnosticado e também rejeitado:
   aprende ordering emtrain,masnão transfere emval. Nenhuma nova época,
   anchor ou ajuste de cutoff nesses pesos/finals expostos.
2. Capturas e supervisão conectada/bilíngue concluídas e auditadas. Implementar
   reader gzip compatível e perda balanceada após dedup, congelar receita nova
   de desenvolvimento e medir fit/transferência antes de reservar outra
   confirmação fresca. Cada seed/idioma pooled e within-goal≥.90,
   recall/contradiction≥.95,rejection≥.70,semanticUNKNOWN≥.95e0UNKNOWN DROP.
3. Candidato útil precisa de piloto semântico LCC: sucesso≥.90,perda≤.02,
   remoção≥.25,zero drop deUNKNOWN,controlfull,custo cache/RSS/cold/warm.
   O piloto literal36/36 já concluído não substitui essa medição semântica.
4. Restaurar referências e confiabilidade de ground truth antes de admitir P2;
   o replay atual permanece rejeitado. Sem retry seletivo do NaN original.
5. Quantização/hosting/manuscrito/release de modelo após gates. Não ampliar RoPE
   nem repetir epochs dos heads perdidos. Publicação externa/default pendentes.

Verificação do bloco anterior:135 testes do motor com integração local LCC passaram sem skips;
os52 pertinentes no consumidor passaram no bloco anterior;
instalação/inferência offline dos guards atuais em macOS arm64/Python 3.14 e
Linux arm64/Python 3.13 passam. O primeiro run perdeu a imagem Docker do worker:
retornou UNKNOWN e falhou nos checks; reconstruído com o digest fixado, passou.
Isso é validação delimitada, não certificação de segurança ou suporte geral.
Verificação histórica após o ensaio condicional:199 testes, zero skips,19.210s,
incluindo integração local LCC; scoped Ruff0.16.10 F/E9 passa. Fonte:
goal-full-tests-factorized-relation.log. O UNKNOWN final nesse log é
um caso mock de falha do transporte; as capturas/treinos principais reais concluíram.
Verificação atual após captura/supervisão variada:221testes/0skips16.880s, incluindo
LCC,scopedRuffF/E9PASS. Fonte:goal-full-tests-varied-tool-states-final.log e
tool-relation-states-v2/scoped-ruff-supervision.log. Zero modelos/APIs executados
nessa fase de dados; seu PASS não modifica o gate de qualidade falho.
