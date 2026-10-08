# PDB: cálculo exato antes da revisão textual — 2026-10-04

**Etapa executada. Observação pontual em controles curados: a receita separada
atingiu o alvo congelado de zero FP/FN/UNKNOWN no eval de 112 casos.** A revisão
acoplada, com o mesmo guard numérico e cutoff, teve 27 falsos negativos.
O experimento não certifica confiabilidade R19, produção ou admissão P2.
O `gateClaim` terminou em **DOWNGRADE**, detalhado abaixo.

## Resultado conferido nos recibos

| Conjunto / receita | Casos | Positivos / negativos | TP / TN | FP / FN / UNKNOWN |
|---|---:|---:|---:|---:|
| Desenvolvimento, separada | 56 | 24 / 32 | 24 / 32 | 0 / 0 / 0 |
| Desenvolvimento, acoplada | 56 | 24 / 32 | 19 / 32 | 0 / 5 / 0 |
| Eval reservado, separada | 112 | 48 / 64 | 48 / 64 | **0 / 0 / 0** |
| Eval reservado, acoplada | 112 | 48 / 64 | 21 / 64 | **0 / 27 / 0** |

O cutoff **.50** e o alvo **FP=FN=UNKNOWN=0** foram congelados antes de qualquer
chamada, incluindo desenvolvimento. Nenhuma pergunta, regra ou cutoff foi ajustado
depois de observar os resultados. Os dois FN da calibração anterior permanecem
no seu relatório original; não foram reutilizados para compor este resultado.

O eval tem 8 escalas: 9/11/13/15/17/19/23/29 réplicas; desenvolvimento tem
4/6/8/10. Nenhuma coincide com as escalas 5/7 do desafio anterior. São 14 controles
por escala: 6 positivos, 4 negativos numéricos e 4 contradições textuais.
Padrões de linguagem e o arquétipo PDB são compartilhados entre as escalas.

Os 32 negativos numéricos do eval foram rejeitados por código nas duas receitas,
sem chamada Jev. Nos 80 casos com matemática válida, cada receita fez uma chamada:
48 textos corretos e 32 contraditórios. Nenhum payload de julgamento foi repetido.

Os 27 FN da revisão acoplada: 8 em orçamento inteiro conservador, 7 em percentual
`maxUnavailable`, 4 em percentual com zeros à esquerda e 8 no inteiro equivalente
ao orçamento máximo seguro. A receita separada aceitou os 48 positivos e rejeitou
os 32 textos contraditórios. Isso compara **representação do estado e pergunta
semântica juntas**, em uma execução por braço; não identifica causalmente qual
mudança isolada produziu a diferença nem mede variabilidade entre chamadas.

## Referência numérica independente

O helper Go foi compilado com `k8s.io/apimachinery@v0.36.0`, dependências e `go.sum`
salvos. A origem do módulo, binário, fonte e arquivos upstream têm hashes.
Conversão de `IntOrString` e arredondamento usam a biblioteca oficial;
o teste de política enumera remoções legais de 0 até N, separadamente da fórmula
do candidato. A verificação dos recibos não importa o candidato ou o runner.

- **4.240 conversões**: inteiros, percentuais 0–101, representações inválidas,
  bool, float, overflow e zeros à esquerda; N=1..32.
- **290.752 comparações de política**: ambos os campos, todos os quóruns 1..N,
  pedidos de manutenção de 1/2 remoções. **Zero divergências**.
- A referência Go foi reexecutada na auditoria e reproduziu todos os outputs salvos.

A nova implementação aceita percentuais com zeros à esquerda e rejeita inteiros
que excedem `int32`, regras ausentes no verificador anterior. Regressões RED salvas
em `red-numeric.log` e `red-routing.log`; suite atual: **32 testes aprovados**.
Regras primárias: [IntOrString v0.36.0](https://github.com/kubernetes/apimachinery/blob/v0.36.0/pkg/util/intstr/intstr.go),
[validação PDB v1.36.0](https://github.com/kubernetes/kubernetes/blob/v1.36.0/pkg/apis/policy/validation/validation.go)
e [validação percentual v1.36.0](https://github.com/kubernetes/kubernetes/blob/v1.36.0/pkg/apis/apps/validation/validation.go).

Escopo: controlador suportado, todas as réplicas desejadas saudáveis, orçamento
para remoções voluntárias. Não houve cluster Kubernetes, validação de selectors ou
manifestos completos. Carga não saudável/controlador fora do escopo retorna UNKNOWN;
falha/ausência do julgamento textual também retorna UNKNOWN.

## Receita e proveniência

`replay/pdb_verifier.py` executa validação de tipos, orçamento, quórum, manutenção
e campos numéricos explícitos. Se passa, Jev recebe somente **fatos verificados +
explicação completa**. Os parâmetros do orçamento ficam fora desse estado;
afirmações numéricas presentes na prosa continuam sendo julgadas contra os fatos.
Texto que contradiz a manutenção, o quórum ou a proteção contra falhas involuntárias
é rejeitado. Um orçamento conservador que atende às restrições é permitido.

A comparação acoplada recebe contexto, objetivo e artefato completo, usando a
pergunta semântica da calibração anterior. Ambas usam o novo guard numérico e
cutoff .50. Não é uma comparação direta com todos os bugs do verificador legado.

Jev1.13.0, cliente canônico TypeSafe, feature `lcc_judge_pdb_routing`, quatro workers
de subprocessos, macOS arm64. **240 chamadas bem-sucedidas**, 80 em desenvolvimento
e 160 em eval, **133.932 tokens de entrada**. Ledger independente confere multiset
de tokens/probabilidades contra as respostas. Estimativa tarifária
**US$0,005625144**, usando US$0,042/M entrada; fatura efetiva indisponível.
Chamadas `gateClaim` ficam fora desses totais. Não houve Hermes, treino ou retry
seletivo neste experimento. Todos os 168 registros têm `training_eligible=false`.

O bridge novo é separado do bridge histórico. Fontes e outputs dos experimentos
anteriores foram preservados; os verificadores da calibração 80/108, replay real
120 episódios e continuação original continuam passando.

## Achados por severidade

**Bloqueante para P2/R19:** falta confirmação com referências de tarefas validadas
independentemente e execução repetida sob inputs idênticos. O replay anterior
continua em 80% concordância/20% UNKNOWN; este desafio não muda seus labels.
O candidato ainda não está integrado ao executor `replay.real_pilot`.

**Material:** os textos corretos/incorretos foram curados por um único autor.
A referência matemática é externa ao candidato; os rótulos semânticos não são
anotação independente de incidentes reais. As escalas compartilham templates.
Zero FP em 64 negativos tem intervalo descritivo Wilson95% [0, .05663]; zero FN
em 48 positivos, [0, .07410]. A correlação dos controles impede tratar esses
intervalos como certificado de erro populacional. Para somente os 32 negativos
textuais, o limite superior descritivo de FPR é aproximadamente .1072.

**Material:** a revisão acoplada continua rejeitando configurações válidas neste
conjunto, com 27/48 FN. Não deve voltar a decidir orçamento quantitativo.

**Menor, corrigido no candidato:** porcentagens com zeros à esquerda e limite de
inteiros `int32`; fórmulas comparadas à referência oficial sem divergências na grade.
Não foi encontrado vazamento dos rótulos privados nos requests, duplicação de
payload de julgamento ou alteração do cutoff depois do dispatch.

O primeiro `gateClaim`, com contadores e referências, deu BLOCK (.77 < .85).
O mesmo claim com tabela bruta dos 112 casos deu **DOWNGRADE**, suporte .88,
força de evidência2.27<2.5: “evidencia de medicao pontual — declarar como tal,
nao como comportamento geral”. O rótulo exigido pela ferramenta foi
“INFERIDO — nao medido (falta medicao repetida ou fonte independente)”.
As contagens reproduzidas acima descrevem este conjunto local; nenhum comportamento
geral ou efeito causal foi certificado. Pareceres/evidências preservados em
`gate-initial.json`, `gate-raw-evidence.json`, `gate-evidence.json`.

## Próxima etapa e critério de sucesso

1. Validar referências dos contratos de replay por implementação executável ou
   anotação independente dos outputs julgados. Sucesso: 20/20 contratos com
   referência/versão/proveniência e conflitos resolvidos antes do dispatch.
2. Integrar a receita separada em **novo protocolo**, preservando o v0.1 e a
   calibração anterior; repetir baseline/ablação 3 vezes com inputs idênticos.
   Sucesso provisório: 120/120 recibos auditáveis, ≥95% concordância, ≤10% UNKNOWN,
   zero admissão automática P2, backend/limitações de seed registrados.
3. Confirmar a revisão textual em controles de outro autor ou incidentes reservados,
   sem ajuste no eval. Fixar critérios por família antes do dispatch; não concluir
   erro populacional com a grade curada atual.

Não vale retunar .50 nos mesmos controles, repetir os 27 erros seletivamente,
rebatizar os labels antigos, escalar D6 ou treinar P2 com esta evidência.

## Reprodução sem novas APIs

```sh
python3 research/pdb-routing-2026-10-04/verify.py
python3 research/verifier-calibration-2026-10-03/verify.py
python3 research/replay-real-2026-10-03/verify_run.py
python3 research/continuation-2026-10-03/verify_completion.py
python3 -m unittest discover -s tests -v
```

Artefatos principais: `protocol.json`, `pre-dispatch-freeze.json`,
`cases-manifest.json`, `development.jsonl`, `eval.jsonl`, `receipts/`,
`summary.json`, `verification.json`, `numeric-verification.json`,
`oracle-{inputs,output}.jsonl`, `case-oracle-{inputs,outputs}.jsonl`,
`oracle/`, `upstream/`, `executed-source/`.
