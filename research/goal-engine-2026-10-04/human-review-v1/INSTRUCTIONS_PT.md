# Revisão humana dos rótulos — instruções (Lucas)

Você é o revisor independente (PLAN.md seção 4): os itens foram escritos por agentes, não por você.

## O que abrir

- Abra só `packet.csv` (Excel, Numbers ou Google Sheets; salve de volta como CSV UTF-8).
- **Não abra `key.json` nem `build-receipt.json` antes de terminar.** Eles dizem de qual split e de qual fonte cada item veio, e isso tira a cegueira da revisão.

## Para cada linha

Leia `question` e decida se `proposed_label` é a resposta certa, usando apenas `registry_definition`.

| Coluna | O que fazer |
| --- | --- |
| `item_id`, `family_id`, `language`, `question`, `proposed_label`, `registry_definition` | Não edite. O `score` rejeita o arquivo se a pergunta ou o rótulo mudar. |
| `verdict` | Escreva exatamente `agree`, `disagree` ou `ambiguous`. |
| `corrected_label` | Obrigatório quando `disagree`. Use um dos 12 rótulos: `retry_attempts`, `retry_failures`, `retry_scheduled_sleep_ns`, `retry_actual_sleep_ns`, `udp_sent_datagrams`, `udp_sent_payload_bytes`, `git_index_edits`, `git_worktree_edits`, `UNKNOWN:derived`, `UNKNOWN:diagnosis`, `UNKNOWN:broader`, `UNKNOWN:other`. Opcional em `ambiguous`. |
| `note` | Livre. Uma frase curta basta quando não for `agree`. |

## Os três vereditos

- `agree`: a pergunta pede exatamente esse campo (com essa unidade), ou de fato não tem campo suportado do tipo indicado (`UNKNOWN:*`).
- `disagree`: outro rótulo é claramente o correto. Ex.: pede tentativas que falharam e o rótulo diz todas as tentativas.
- `ambiguous`: uma pessoa razoável poderia escolher dois rótulos, ou a pergunta não deixa claro o que quer. Pela regra do contrato, pergunta ambígua deveria ser `UNKNOWN:other`; se o rótulo proposto for um campo, marque `ambiguous` (ou `disagree` com `UNKNOWN:other`, se tiver certeza). `ambiguous` conta como não-concordância.

## Tempo estimado

60 itens, uns 30 a 45 segundos cada: **35 a 45 minutos**. Pode parar e continuar depois; só salve o CSV.

## Depois de preencher

Na raiz do repo:

```bash
python3 -m research.review_packet score
```

Isso valida o arquivo e grava `score.json` nesta pasta. Passa com concordância >= 0,95 no total e >= 0,90 em cada estrato.

## Limite conhecido

O plano pede 240 itens em 16 estratos. Os dados atuais só têm 4 (EN/PT x suportado/UNKNOWN, todos `authored`). Faltam contraste, ambiguidade e `genuine_lcc`, por isso o pacote tem 60 itens e o `score` sempre informa `plan_complete: false`. Um resultado aprovado aqui valida os rótulos atuais. Ainda não permite adoção.
