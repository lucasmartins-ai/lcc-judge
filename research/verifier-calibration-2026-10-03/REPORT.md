# Calibração de verificadores — concluída em 2026-10-04

**Etapa concluída: os critérios provisórios por tipo passaram em 108 controles
reservados; certificação de ground truth P2 permanece aberta.** A pasta mantém a
data da etapa iniciada em 03/10. O piloto original e seus 120 recibos não foram
substituídos por este experimento.

## Resultado verificado

Foram congelados80 casos de calibração e108 de avaliação. Há20 arquétipos já
conhecidos:6 de código e14 de diagnóstico/decisão. As respostas, implementações
e falhas são controles novos; não são20 novos domínios ou sessões de produção.
Não há programa com AST idêntica entre os splits nem com os outputs do piloto
anterior. Os contratos e algoritmos subjacentes compartilham conceitos.

Critérios fixados antes do eval: por tipo, FP≤5%, FN≤10%, UNKNOWN≤5%; código exige
zero FP. O cutoff semântico foi escolhido só na calibração, entre
.50/.70/.80/.90/.95/.99, maximizando recall sujeito a esses critérios; empate
escolhe o menor cutoff. **Selecionado .50**, salvo e hasheado antes de existir
qualquer recibo de eval. O .95 da concordância entre replays é um critério diferente,
que permanece não validado; não foi substituído por .50.

| Eval reservado | Positivos / negativos | TP | FP | FN | UNKNOWN |
|---|---:|---:|---:|---:|---:|
| Código, verificador anterior | 12 / 12 | 11 | 2 | 1 | 0 |
| Código, candidato executável | 12 / 12 | 12 | 0 | 0 | 0 |
| Tipado, verificador anterior | 42 / 42 | 41 | 37 | 1 | 0 |
| Tipado, candidato + Jev ≥.50 | 42 / 42 | 40 | 0 | 2 | 0 |

FPR do candidato observado:0/12 em código e0/42 em tipado. FNR:0/12 e2/42=4,76%.
As metas provisórias **por tipo** passam. Essa taxa média não aprova todas as
famílias: os dois FN estão no PDB, descritos abaixo. Nenhum registro entra em treino.

Evidência: `summary.json`, `verification.json`, `eval-results.jsonl`,
`frozen-threshold.json`, `pre-eval-freeze.json`, `receipts/`.

## Achados por severidade

### Bloqueante — admissão P2 e confiabilidade de replay não estão certificadas

São controles de desafio curados por um único autor, com labels e justificativas
baseados em contratos explícitos. Não houve anotação humana externa independente,
amostragem de produção ou restauração dos serviços. Alguns textos dão diretamente
a causa e excluem competidores; isso testa contradições, sem medir a dificuldade
de diagnosticar um incidente real. A separação de splits e ausência de duplicatas
não eliminam essa dependência de curadoria.

O piloto real anterior continua com80% concordância/20% UNKNOWN; estas188 respostas
de controle não medem novamente sua repetibilidade. Jev aqui avalia consistência
da resposta e é comparado aos controles, sem produzir labels de necessidade de treino.
O número de negativos por tipo também é pequeno. Limite superior Wilson95%
descritivo de FPR com zero erros:24,25% em12 negativos de código e8,38% em42 tipados.
Os casos correlacionados não justificam tratar esses intervalos como certificação
de erro populacional≤5%.

### Material — avaliação semântica rejeita orçamentos PDB válidos

No contexto reservado há7 réplicas saudáveis, quórum4 e necessidade de uma remoção
voluntária. `max_unavailable: "40%"` permite ceil(.40×7)=3, mantendo4; `2` mantém5.
Ambos satisfazem o contrato. Jev deu .40 e.36, abaixo do cutoff .50, produzindo
dois FN entre os3 positivos dessa família. Percentuais e arredondamento para cima
seguem a [documentação oficial Kubernetes](https://kubernetes.io/docs/tasks/run-application/configure-pdb/).

O verificador numérico determinístico aprovou ambos. Próxima receita deve calcular
orçamento/quórum em código e delimitar a pergunta semântica ao texto não numérico.
Essa mudança **não foi aplicada retroativamente ao eval**, e exige outro conjunto
reservado para confirmação. Não adotar um cutoff global como certificação dessa família.

### Material — verificador anterior aceitava código inválido e valores fora do contrato

Quatro regressões reproduziram defeitos antes da correção: booleano aceito como
contagem, percentuais válidos rejeitados, reserva que funciona só nos IDs do teste,
e teste que sinaliza falha por RuntimeError em vez de AssertionError.
Evidência: `red-baseline.log`, `tests/test_verifier_calibration.py`.

O candidato, em `replay/outcome_verifier.py`, testa mais inputs de estoque/SQL,
disputa perdida de SET NX, montantes diferentes, rollback após falha de crédito,
mais taxas/capacidades e mutantes de testes. O mock de transação usa isolamento
local e SQLite; não certifica locks/isolamento do Postgres em produção. A checagem
PDB cobre o orçamento, não selector, workload/controller ou manifesto completo.

Na calibração, o verificador anterior teve4 FP de código e14 tipados. O candidato
estrutural zerou erros de código, mas ainda aceitou12 explicações contraditórias.
A combinação semântica no cutoff .50 eliminou esses erros nos controles de calibração.
Isso explica a inclusão de Jev no candidato tipado, mantendo código como outcome executável.

### Menor — fonte histórica e receita candidata permanecem separadas

`replay.real_pilot` continua usando a receita anterior. A nova receita é candidata
experimental; não foi integrada automaticamente a treino, produção ou ao piloto.
Fontes anteriores estão em `inherited/`, e as executadas neste desafio em
`executed-source/`. Rascunhos anteriores ao congelamento final foram preservados
com sufixo `draft-*`; nenhum deles foi usado para consultar o eval ou escolher cutoff.

## API, testes e reprodução

**140 chamadas Jev bem-sucedidas**,56 na calibração e84 no eval, modelo versionado
`jev-1.13.0`, cliente canônico e feature `lcc_judge_verifier_calibration`. O ledger
compartilhado confirma140 entradas e140.995 tokens de entrada. Nenhuma geração
Hermes adicional foi necessária. A [tarifa publicada](https://docs.typesafe.ai/models)
de US$0,042/M tokens de entrada dá estimativa **US$0,00592179**, sem recibo de fatura.
O payload contém objetivo, contexto, resposta e ontologia; labels esperados,
justificativas, split e contrato privado ficam fora do state enviado.

**25 regressões passaram.** A verificação independente reproduziu contagens e
cutoff, conferiu hashes/source snapshots, ASTs,140 respostas de API, ledger e
congelamento antes de eval. Verificações anteriores de corpus/gate e dos120
episódios também passaram, preservando os resultados históricos.
O gate automático aprovou apenas a alegação estreita de contagens locais, em
`claim-gate.json`; isso não aprova admissão de treino ou risco de produção.

```sh
cd /Users/Master/Downloads/LCC-judge
python3 research/verifier-calibration-2026-10-03/verify.py
python3 -m unittest discover -s tests -v
# Resume lê recibos já salvos; não altera fonte, casos ou cutoff congelados:
python3 research/verifier-calibration-2026-10-03/run.py --phase all
```

## Próximos passos com critério de sucesso

1. **Separar cálculo de orçamento da checagem semântica**, em protocolo novo.
   Sucesso: percentuais, tipos e quórum cobertos por referência determinística;
   pergunta semântica restrita às alegações textuais; zero FN/FP PDB em novos
   controles reservados, incluindo fronteiras e mudança de escala. Não retocar este eval.
2. **Confirmar em fixtures de origem independente e repetir replay com inputs iguais.**
   Congelar contratos/limiar antes do eval e validar a referência externamente.
   Sucesso:120 recibos pareados novos, concordância≥95%/UNKNOWN≤10% como metas
   provisórias ou critério empiricamente justificado antes do eval; erros reportados
   por família e limitações de seed/backend preservadas. Sem admissão P2 antecipada.
3. **Avançar qualidade do scorer separadamente.** Normalização em objetivos intocados
   exigeΔJ≥.03, CI inferior>0 e perdaD≤.01; melhoria detect requer controle de seed,
   D≥.70 e perdaJ≤.02. O gate global .90 e M8 por bloco continuam falhos.

Não vale aumentar o cutoff para .95 só por parecer mais seguro: ele perdeu3/28
positivos de calibração e não passou o limite FN. Também não vale reduzir cutoff
depois de olhar os dois FN do eval, relabelar os controles para concordarem com
Jev, escalar D6 ou admitir estes labels antes das confirmações.
