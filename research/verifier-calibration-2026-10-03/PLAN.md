# Calibração de verificadores — 2026-10-03

Pedido: avançar para o próximo passo, preservando autorização de API já dada.
Não reutilizar os 120 outputs para escolher limiares ou declarar confirmação.

- [x] Criar desafios novos com positivos/negativos, labels curados e justificativas.
- [x] Separar calibração/eval por caso, AST e família de falha; congelar hashes; conceitos compartilhados declarados.
- [x] Medir o verificador anterior na calibração, reproduzir defeitos com regressões.
- [x] Corrigir contratos com o mínimo de código; manter fontes anteriores e resultados históricos.
- [x] Calibrar cutoff Jev em calibração somente; congelar decisão antes do eval.
- [x] Executar eval reservado sem ajustes/retries seletivos; reportar FP/FN/UNKNOWN por tipo.
- [x] Verificação independente, docs, memória e relatório final.

Ground truth: controles escritos a partir de contratos explícitos e testemunhos
de falha, não labels de produção ou uma anotação humana independente. Separar
checagem executável de diagnóstico semântico; Jev não decide labels de treino.
Metas provisórias por tipo: FP≤5%, FN≤10%, UNKNOWN≤5%; zero FP nos códigos
incorretos executáveis. Limiar escolhido só em calibração. Reportar contagens,
intervalos descritivos e correlação entre casos sem inferir erro populacional.
Admissão P2 permanece false, inclusive se este desafio passar.

Concluído2026-10-04:80/108 casos,140 chamadas Jev,25 regressões.
Cutoff .50 escolhido em calibração e congelado antes de eval. Eval código0FP/0FN,
tipado0FP/2FN; critérios por tipo passam, ambos FN em orçamentos PDB válidos.
Futuros passos: separar cálculo/semântica em protocolo novo e confirmar em controles
novos; referência externa e repetibilidade R19 seguem abertas. Relatório `REPORT.md`.
