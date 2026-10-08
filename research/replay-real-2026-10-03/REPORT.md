# Replay real — execução e auditoria, 2026-10-03

**Execução concluída; confiabilidade proposta reprovada; nenhum label admitido em treino.**
Após autorização explícita do usuário para chamadas reais, foram executadas 20 tarefas
curadas × baseline/ablação × 3 repetições: **120 chamadas Hermes, 120 sessões distintas**.
São respostas reais de modelo sobre fixtures, não replays de sessões de produção.
Esta etapa complementa a auditoria e a remediação anteriores; não altera a reprovação
do gate de qualidade do Sprint 2 nem do M8 por bloco.

## Resultado independente

| Medida | Resultado auditado |
|---|---:|
| Chamadas Hermes / sessões distintas | 120 / 120 |
| Respostas válidas no contrato JSON | 119 |
| Baseline aprovado no verificador | 60/60 |
| Ablação aprovada no verificador | 39/60 |
| NECESSARY / UNNECESSARY / UNKNOWN | 5 / 11 / 4 |
| Concordância por tarefa nas duas condições | 16/20 = 80% |
| UNKNOWN | 4/20 = 20% |
| CI95% Wilson descritivo de concordância | [58,4%, 91,9%] |
| Meta proposta, congelada antes das chamadas | concordância ≥95%; UNKNOWN ≤10% |
| Registros elegíveis para treino | 0 |

Concordância exige três resultados iguais e válidos **em cada condição**. NECESSARY
exige baseline aprovado e ablação reprovada nas três repetições; UNNECESSARY exige
ambas aprovadas. Discordância, saída inválida ou verificador indisponível geram UNKNOWN.
São rótulos condicionais a este executor e a estes contratos; NECESSARY não implica
CRITICAL, nem UNNECESSARY implica REDUNDANT. Esses dois campos permanecem null.

Evidência: `data/d6_real_pilot/{protocol.json,summary.json,records.jsonl}` e
`research/replay-real-2026-10-03/verification.json`. O script independente verifica
os recibos brutos, hashes, chaves das 120 execuções, sessões, rótulos e tokens.

## Achados por severidade

### Bloqueante — a confiabilidade para D6/P2 permanece não estabelecida

O piloto dá 80% de concordância e 20% UNKNOWN, falhando as duas metas propostas.
Além disso, a cláusula de Sprint 1 requer um limiar fundamentado na distribuição
do piloto: .95 continua uma proposta, não uma calibração validada. Os verificadores
foram desenvolvidos nestas fixtures e ainda precisam de avaliação em casos intocados.
Não há base para treinar P2 com estes registros como ground truth certificado.

### Material — repetição não congela geração e backend

Hermes não expõe seed de geração; 42/59/76 eram metadados e também apareceram no
input da versão executada v0.1. Portanto os prompts entre repetições não eram
literalmente idênticos, embora cada par baseline/ablação usasse o mesmo metadado.
O modelo `stealth/space-bunny-alpha` é um alias sem snapshot imutável disponível.
O experimento mede consistência observada dessa configuração, sem isolar toda a
variabilidade de amostragem/backend. Na receita futura v0.2, o seed não aplicado
foi removido do input; essa receita **ainda não foi executada**.

### Material — escopo do verificador é limitado e houve um falso negativo

Seis tarefas executam Python gerado em processos isolados, com estado novo e testes
comportamentais; as outras 14 verificam respostas tipadas de diagnóstico/decisão.
Elas não restauram Kubernetes, Kafka ou os serviços originais. Aprovação de mecanismo
tipado não prova que todas as alegações em texto livre estejam corretas.

O verificador original da tarefa 18 rejeitava `maxUnavailable: 1`, embora isso preserve
o quórum de três em cinco e permita manutenção de um nó. A correção reapurou as
respostas salvas, sem repetir chamadas: três verdicts de ablação passaram a aprovados,
e a tarefa mudou de NECESSARY para UNNECESSARY. Não houve outra mudança de aprovação.
Os recibos originais continuam intactos; fonte e resumo anteriores estão arquivados
em `executed-source/`, e a reapuração está em `evaluation-audit.json`.

Os seis programas de referência passaram, e seis controles deliberadamente errados
foram rejeitados. Isso valida os controles testados; não certifica a taxa de erro do
verificador em uma população externa. Evidência: `verifier-positive-controls.json`,
`verifier-negative-controls.json`, `tests/test_real_replay.py`.

### Material — Jev não substitui o verificador de outcome

Foram feitas 119 chamadas Jev do piloto, todas bem-sucedidas, via cliente canônico,
modelo `jev-1.13.0`, feature `lcc_judge_replay_real` e ledger compartilhado. A tarefa
com resposta JSON inválida não foi enviada a Jev. Jev recebe objetivo/contexto e a
resposta submetida, sem gabarito, e serve apenas como diagnóstico semântico.

Há 9 discordâncias entre `noul ≥.5` e os verificadores, usando .5 somente para a
comparação diagnóstica. Por exemplo, a ablação SQL recebeu .92, mas o Python gerado
falhou na execução por uso inválido de parâmetros da API SQLite. No caso de
idempotência, três respostas reprovadas pelo contrato executável receberam >.5.
Não há motivo para converter esses scores em labels P2. Todas as discordâncias
estão em `verification.json`.

### Menor — hash de protocolo e contagem Jev corrigidos com história preservada

A versão v0.1 calculava o hash com chaves numéricas e depois serializava as chaves
como texto; recalcular diretamente do JSON não reproduzia o hash. A verificação
independente reproduz essa receita histórica e confere a fonte arquivada. A receita
v0.2 normaliza o JSON antes de calcular o hash e permite comparação fiel no resume.
A contagem original de Jev era 120 por incluir uma entrada sem chamada; o resumo
auditado conta os 119 recibos existentes. Nenhum recibo de episódio foi alterado.

## UNKNOWN e custos

| Tarefa | Baseline | Ablação | Causa |
|---|---|---|---|
| 005, websocket leak | T/T/T | F/F/T | diagnóstico varia |
| 006, SQL injection | T/T/T | T/F/T | uma função falha na API SQLite |
| 008, circuit breaker | T/T/T | T/F/F | timeout varia frente ao contrato ≤1500 ms |
| 016, rate limiter | T/T/T | T/T/null | uma resposta não é um único JSON válido |

A saída inválida foi mantida como erro, sem retry seletivo ou aproveitamento parcial.
Hermes reportou 118.008 tokens de entrada e 91.522 de saída. Jev reportou 74.931
tokens de entrada; pela [tarifa publicada](https://docs.typesafe.ai/models) de
US$0,042/M tokens de entrada e saída gratuita, a estimativa tarifária **do piloto**
é **US$0,003147102**. Isso não é uma fatura: o custo efetivamente debitado de Hermes
e Jev não foi retornado. Smokes de conectividade e eventual gate de alegação ficam
separados da contagem do piloto. Não foi aplicado teto de gastos.

## Reprodução e próximos passos

Os executores usaram Hermes v0.21.5+5430.g5d07710, provider commandcode, one-shot,
safe-mode, sem tools/MCP/memória/rules/plugins. Cada chamada criou processo e sessão
novos. Versões e recibos estão em `executor-environment.json` e `episodes/`.

Validação local:20 regressões passaram, com log em `tests.log`; os scripts de
verificação do replay e da continuação anterior passaram. O ledger compartilhado
tem120 entradas da feature deste replay:119 do piloto e1 smoke, todas `ok`.
O gate automático de alegações bloqueou o primeiro resumo narrativo; ao receber
os contadores JSON extraídos dos recibos e o resultado independente, aprovou
somente a alegação estreita de contagens locais (suporte .86). Ambos os recibos
estão preservados em `claim-gate*.json`; essa aprovação não valida confiabilidade
de labels, inferência causal ou prontidão de produção.

```sh
cd /Users/Master/Downloads/LCC-judge
python3 research/replay-real-2026-10-03/verify_run.py
python3 -m unittest discover -s tests -v
# Nova execução apenas em diretório novo; fonte v0.2, diferente da já executada:
/Users/Master/LCC/.venv/bin/python -m replay.real_pilot --out-dir data/d6_real_pilot_v02
```

1. **Calibrar o verificador em fixtures intocadas antes de ampliar replay.** Separar
   calibração/eval e auditar falsos positivos/negativos com referências independentes.
   Sucesso: contratos e limiar congelados antes do eval, erros reportados por tipo,
   e critério de admissão justificado nessa calibração; nenhum label entra antes.
2. **Medir repetibilidade sob o contrato corrigido.** Mesmos prompts entre repetições,
   registrar seed efetiva se o provider a expuser e versão imutável se disponível.
   Sucesso: 120 recibos completos em eval novo, ≥95% concordância e ≤10% UNKNOWN
   como metas provisórias, ou limiar revisado e justificado antes do eval. Se o alias
   continuar mutável, restringir a conclusão a ele e ao período observado.
3. **Confirmar normalização em objetivos intocados e candidato variável.** ΔJ≥.03,
   limite inferior CI95%>0 e perda D≤.01; ECE se alegar probabilidade calibrada.
4. **Melhorar transferência OOD e alvo detect com controles pareados.** D≥.70 em
   0/512, ganho positivo e perda J≤.02; depois exigir .90 em ambas as famílias.
5. **Medir fronteira nativa sem cortes quando necessário.** n62×3, zero cortes/erros,
   orçamento total HF e posição da evidência comprovados; comparar chunks simples
   antes de uma hierarquia. Otimização CPU vem após qualidade útil e exige ambos M8.

Não vale rerodar seletivamente os quatro UNKNOWN para obter um resultado favorável,
admitir labels Jev sem outcomes, ampliar este replay antes da calibração, repetir o
produto joint-detect reprovado ou gastar agora com Track C/32K/64K.
