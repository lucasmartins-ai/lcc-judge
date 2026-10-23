"""Keyword baseline for intake judge v1: what a regex intake can do with the 14 categories.

Written from the taxonomy-v2 definitions only, before any training label or held-out prompt was read
(intake-judge-v1/PROTOCOL.md). First matching rule wins; the fallback is specified_task.
"""
from __future__ import annotations

import re

_I = re.IGNORECASE

RULES = [
    ('handoff_prompt', re.compile(
        r'\b(?:prompt|handoff|briefing)\b.*\b(?:para|pra|for)\b.*\b(?:outr[oa]|nova|another|new|codex|sess[ãa]o|session|agente|agent)\b'
        r'|\bescrev\w* (?:um|o) (?:prompt|plano)\b|\bwrite (?:a|the) (?:prompt|plan|handoff)\b', _I)),
    ('git_ship', re.compile(
        r'^\W*(?:faz |fa[çc]a |pode |can you |please )?(?:o |a |um |uma )?'
        r'(?:commit\w*|comit\w*|push\w*|pusha|merge\w*|mergea|pr\b|pull request|abre (?:o |um )?pr)\b'
        r'|\b(?:\.gitignore|limpa\w* (?:as )?branch\w*|delete (?:the )?branch\w*)\b', _I)),
    ('failure_report', re.compile(
        r'traceback|exception|\berror\b|\berro\b|\bfailed\b|\bfalhou\b|n[ãa]o funcionou|not working|'
        r'doesn\'?t work|deu (?:erro|ruim|pau)|quebrou|\bcrash\w*|aconteceu de novo|happened again|'
        r'\b(?:4\d\d|5\d\d)\b|exit (?:code|status)', _I)),
    ('environment_and_infra', re.compile(
        r'\b(?:mcp|skill\w*|harness|claude\.md|agents\.md|hook\w*|vercel|cloudflare|supabase|dns|cron\w*|'
        r'env var\w*|vari[áa]ve\w* de ambiente|\.env|docker|railway|wrangler|ollama|modelo local|local model)\b', _I)),
    ('external_accounts_and_comms', re.compile(
        r'\b(?:whatsapp|linkedin|instagram|threads|e-?mail\w*|inbox|caixa de entrada|crm|lead\w*|'
        r'prospec\w*|outreach|upwork|candidat\w*|posta\w*|post\b|mensage\w*|dm\b)\b', _I)),
    ('handoff_prompt', re.compile(r'\bprompt\b', _I)),
    ('correct_approach_or_rule', re.compile(
        r'\b(?:usa|use|utiliza) (?:o |a )?\w+ (?:em vez|ao inv[ée]s|instead)\b|'
        r'\bn[ãa]o (?:é|era) (?:isso|assim)\b|\berrado\b|\bwrong\b|\bnão gostei da solu|'
        r'\b(?:daqui pra frente|from now on|sempre que|always|nunca|never)\b|'
        r'\b(?:corrige|otimiza) tudo\b|\bna verdade\b|\bactually\b', _I)),
    ('revise_recent_output', re.compile(
        r'\bficou\b|\b(?:tira|remove|muda|troca|aumenta|diminui)\b.*\b(?:cor|texto|t[íi]tulo|bot[ãa]o|imagem|'
        r'fonte|layout|footer|header|se[çc][ãa]o|p[áa]gina|v[íi]deo|logo|copy)\b|'
        r'\b(?:cara de ia|looks? like ai|feio|ugly)\b', _I)),
    ('project_audit_or_direction', re.compile(
        r'\b(?:pontos? (?:fortes|fracos)|pr[óo]ximos passos|next steps|estrat[ée]gia|strategy|'
        r'viabilidade|vale a pena|consigo vender|can i sell|avali[ae]\w* o projeto|review the (?:whole )?project|roadmap)\b', _I)),
    ('task_status_or_control', re.compile(
        r'\b(?:status|onde (?:paramos|estamos)|o que falta|what\'?s left|como (?:est[áa]|ficou) (?:a|o)|'
        r'para\b|stop\b|deixa\b|agora (?:faz|fa[çc]a)|e (?:o|a) \w+\?|revisa (?:primeiro|antes)|'
        r'verifica se|check (?:if|whether)|terminou|done\?)', _I)),
    ('general_question', re.compile(
        r'^\W*(?:o que [ée]|what is|qual (?:o melhor|plano|modelo)|which (?:plan|model)|'
        r'quanto custa|how much|vale mais|compar\w*)\b.*\?\s*$', _I)),
    ('approve_or_pick', re.compile(
        r'^\W*(?:sim|s|yes|y|ok|okay|pode|podes|manda|vai|go|continua\w*|continue|segue|siga|bora|'
        r'tenta de novo|try again|retry|faz|fa[çc]a|isso|perfeito|[0-9]+(?:\s*(?:,|e|and)\s*[0-9]+)*)\W*$', _I)),
    ('supply_fact_or_step_done', re.compile(
        r'^\W*(?:j[áa] (?:fiz|loguei|rodei|instalei|criei|configurei)|feito|done|rodei|loguei|pronto)\b|'
        r'^\W*(?:https?://\S+|<\w+>|[0-9a-f]{7,40})\W*$', _I)),
]
FALLBACK = 'specified_task'


def classify(text: str) -> str:
    t = (text or '').strip()
    if not t:
        return 'UNKNOWN'
    for label, pattern in RULES:
        if pattern.search(t):
            return label
    return FALLBACK


if __name__ == '__main__':
    assert classify('sim') == 'approve_or_pick'
    assert classify('1 e 3') == 'approve_or_pick'
    assert classify('faz o commit e push') == 'git_ship'
    assert classify('deu erro no deploy: Traceback ...') == 'failure_report'
    assert classify('escreve um prompt para outra sessão continuar') == 'handoff_prompt'
    assert classify('cria uma landing page com hero e CTA') == 'specified_task'
    assert classify('') == 'UNKNOWN'
    print('ok')
