# Continuação independente — 2026-10-03

Pedido: conferir onde o outro agente parou e concluir o trabalho autorizado.
Snapshot dos artefatos recebidos em `inherited/`; não retreinar braços já concluídos.

- [x] Conferir corpus 0.4, épocas, cobertura e determinismo no disco.
- [x] Reproduzir normalização com protocolo e scores salvos, em dados limpos.
- [x] Avaliar joint-detect contra checkpoint BCE independente; preservar scores.
- [x] Corrigir replay sintético e preparar executor real sem acesso ao gabarito.
- [x] Medir CPU do braço escolhido sem truncamento silencioso; reportar ambos critérios M8.
- [x] Corrigir relatório/status/log com resultados e limitações; executar regressões.

Atualização: o usuário autorizou chamadas reais; o executor Hermes configurado foi
identificado e executado. Ver `research/replay-real-2026-10-03/REPORT.md`.
Não confundir execução negativa de piloto com gate aprovado.

- [x] Executar replay REAL:120 chamadas em120 sessões;80% concordância/20% UNKNOWN;
  calibração/verificadores e admissão P2 permanecem não certificados.
- [ ] Fronteira nativa sem cortes e vantagem da agregação: experimento futuro, não certificado pela curva nominal8K.

Verificações concluídas:20 regressões atuais (12 originais +8 de replay real);
py_compile; corpus/hashes/scores/splits;
3540 exemplos reavaliados de checkpoints; RoPE delta3.31e-8; recibos CPU e pilotos com hashes.
Gate de qualidade e M8 por bloco continuam falhos. Nenhuma admissão P2 nem publicação.
