# Revisão humana dos rótulos — v2 (só português)

Substitui o v1 (EN+PT), cancelado em 2026-10-08: o revisor não conseguia entender
as perguntas. Este pacote tem 60 perguntas em português: 30 pedem um dado que existe
no catálogo e 30 pedem algo que o catálogo não tem (UNKNOWN). Leva uns 30–40 minutos
e pode ser feito em várias sessões.

## Como revisar

```bash
cd /Users/Master/Downloads/LCC-judge && python3 -m research.review_packet review
```

Para cada pergunta você vê o rótulo proposto e a definição dele. Responda:

| Tecla | Quando usar |
|---|---|
| `a` | A pergunta pede exatamente o que a definição descreve. |
| `d` | A pergunta pede outra coisa. Em seguida escolha o número do rótulo certo. |
| `?` | Entendi a pergunta, mas ela pode ser lida de dois jeitos. |
| `n` | **Não entendi a pergunta.** Use sem culpa: isso também é um resultado. |
| `s` / `q` | Pular / sair. O progresso fica salvo. |

Quando terminar: `python3 -m research.review_packet score`.

## Glossário em linguagem simples

As perguntas falam de medições de três ferramentas:

- **retry**: quando uma operação falha, o programa tenta de novo algumas vezes.
  - `retry_attempts`: quantas vezes a operação foi chamada no total (inclui a primeira).
  - `retry_failures`: quantas dessas chamadas deram erro.
  - `retry_scheduled_sleep_ns`: quanto tempo de espera entre tentativas foi **programado** (o plano).
  - `retry_actual_sleep_ns`: quanto tempo de espera **realmente passou** (medido).
- **UDP**: envio de mensagens pela rede, sem confirmação de entrega.
  - `udp_sent_datagrams`: quantas mensagens foram enviadas.
  - `udp_sent_payload_bytes`: quantos bytes de conteúdo essas mensagens levavam.
- **git**: controle de versão de arquivos.
  - `git_index_edits`: arquivos alterados que já foram preparados para commit (`git add`).
  - `git_worktree_edits`: arquivos alterados no disco que ainda não foram preparados.
- **UNKNOWN** (o catálogo não responde com um dado só):
  - `UNKNOWN:diagnosis`: pergunta "por quê" ou a causa de algo.
  - `UNKNOWN:derived`: pede um cálculo ou uma combinação de vários dados.
  - `UNKNOWN:broader`: pede contexto amplo para uma investigação.
  - `UNKNOWN:other`: pede um dado que não está no catálogo, ou é ambígua.

## Limites

Abra só o terminal ou o `packet.csv`; não abra `key.json` antes de terminar.
As perguntas foram geradas por agentes a partir de modelos de frase, então algumas
soam artificiais. Responder `n` quando for o caso é exatamente o que queremos medir.
Faltam ainda os grupos de contraste, ambiguidade e pedidos reais do LCC; por isso o
`score` sempre informa `plan_complete: false`. Um resultado aprovado valida os rótulos
atuais em português, não permite adoção.
