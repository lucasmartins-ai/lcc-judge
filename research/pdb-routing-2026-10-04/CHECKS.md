# Checagens locais — 2026-10-04

Executadas após implementar a receita, sem substituir resultados históricos:

- `python3 -m unittest discover -s tests -v`:32 testes, OK;7 do novo módulo PDB.
- `python3 research/pdb-routing-2026-10-04/numeric_check.py`:4240 conversões,
  290752 comparações de política, zero divergências.
- `python3 research/pdb-routing-2026-10-04/run.py`:168 recibos;240 APIs bem-sucedidas.
- `python3 research/pdb-routing-2026-10-04/verify.py`:hashes/freeze/contagens,
  referência Go reexecutada e ledger conferidos; resultado em `verification.json`.
- `python3 research/verifier-calibration-2026-10-03/verify.py`:PASS,140 chamadas
  históricas e seus0FP/2FN tipados permanecem reproduzíveis.
- `python3 research/replay-real-2026-10-03/verify_run.py`:PASS,120 episódios/sessões,
  recibos inalterados,80% concordância/20% UNKNOWN/0 admissão.
- `python3 research/continuation-2026-10-03/verify_completion.py`:PASS corpus,
  signatures/hashes, checkpoints,5784 scores preservados e quarentena de replay.
- Parse AST de7 arquivos Python novos:PASS. O bridge TypeScript foi executado
  nas240 chamadas pelo `tsx`; este workspace não tem configuração de typecheck TS.

As falhas RED iniciais foram preservadas nos dois arquivos `red-*.log`.
GateClaim:BLOCK inicial; depois DOWNGRADE com os valores brutos; sem retries adicionais.
