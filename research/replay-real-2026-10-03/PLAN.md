# Replay real autorizado — 2026-10-03

Autorização do usuário: executar APIs configuradas; Jev sem teto de gasto.

- [x] Smoke do executor Hermes e do cliente Jev existente (sem revelar credenciais).
- [x] Congelar protocolo e verificadores determinísticos; coding com testes executáveis.
- [x] Regressões: código errado rejeitado, ablação real sem gabarito, erros UNKNOWN.
- [x] Executar 20 tarefas × baseline/ablação × 3 repetições com recibos duráveis.
- [x] Auditar resultados e confiabilidade, atualizar docs e memória.

API Jev: docs oficiais capturados; modelo versionado jev-1.13.0.
Executor candidato: Hermes commandcode/stealth/space-bunny-alpha, one-shot, sem ferramentas.
Fixture curada não é sessão real de produção; todos os resultados são condicionais
a este executor/protocolo. Nenhuma publicação/treino autorizada por esta execução.

Concluído:120 sessões,119 respostas válidas,5 NECESSARY/11 UNNECESSARY/4 UNKNOWN.
Metas propostas reprovadas:80% concordância/20% UNKNOWN. Zero admissão P2.
Calibração independente de verificador, limiar empírico e eval intocado permanecem
novas etapas de pesquisa; não foram substituídos por inferência ou retry seletivo.
Ver `REPORT.md`, `verification.json`, `evaluation-audit.json`.
