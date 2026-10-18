"""Specialist v5: v3 (frozen) + deterministic edge-case detectors as protection rules, with a cascade second stage.

Why (V4_DEV_RESULTS.md): distilling a holistic Opus relevance judgement into the local model failed; the cases v3
loses need specific relations (rule + exception, conflicting values, user statement vs guess, "o segundo",
commit conventions...), which cheap rules can carry. v5 keeps v3's score untouched and adds a fixed bonus to the
few blocks a detector protects. Everything here needs only block text + the structured metadata LCC passes
(message index, role, kind, tool; here parsed from the render header by s2.block_meta).

Stage 1 (every block, regex / bookkeeping):
    user_directive   user turn with a rule / exception / correction / "fyi" / authority marker
    goal_xling       top-2 blocks by goal match after pt<->en glossary + identifier splitting + prefix stems
    git_state        git-ish goal -> latest git status output + commit-convention docs (AGENTS.md, ## Commits...)
    wide_view        overview goal -> top-level project docs (README / ROADMAP / STATUS / TODO / CHANGELOG)
    ordinal_ref      goal says "o segundo" / "option 2" / "the first" -> latest enumerated block (options / failures)
    said_ref         goal says "do jeito que voce falou" / "what you suggested" -> latest substantive assistant turns
    hedge            assistant guess ("acho que", "I think", "pelo que lembro") -> demoted by half a bonus
    injection        tool output with instruction-shaped text -> FLAG only (kept as evidence, never a rule)
Stage 2 (cascade: only blocks at risk, i.e. inside the lowest 70% of tokens after stage 1, plus their partners):
    value_conflict   same quantity (unit class or config key) with different values in two goal-related lines
    qualifier_link   the tool output that carries the condition an exception names (shared rare terms)

    Judge.load(path).score(goal, texts) -> [float]; Judge.flags(goal, texts) -> per-block detector flags.
    python -m research.specialist_v5 {edge|trainsample|select|eval|final}
"""
import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from research import specialist_v2 as s2
from research import specialist_v3 as s3

ART = Path.home() / '.lcc/bench/specialist-v5'
OUT = s2.OUT
SEED = 20261018
UD_CAP, UD_MAXLEN = 3, 1500  # user_directive: most recent N user turns under this many chars
AT_RISK = 0.70  # cascade band: blocks that some budget <= 70% would drop after stage 1


# --- text helpers --------------------------------------------------------------------------------------------
def fold(s):
    """Lowercase, accents stripped. ASCII fast path; otherwise NFKD and drop combining marks (C-speed)."""
    if s.isascii():
        return s.lower()
    d = unicodedata.normalize('NFKD', s)
    return d.translate(_COMBINING).lower()


_COMBINING = {c: None for c in range(0x300, 0x370)}  # combining diacritical marks


IDENT_RE = re.compile(r'([a-z])([A-Z])')
WORD_RE = re.compile(r'[a-z][a-z0-9]+|\d+[a-z]*')
STOP = set('''a o as os um uma de da do das dos em no na nos nas pra pro para por com sem que se e ou mas nao sim eu
voce vc tu ele ela isso isto esse essa este esta aquele aquela aquilo ai la aqui ja so mais menos muito pouco
tem ter ta tá to vai vou faz fazer pode posso agora entao beleza blz ok okay ver olha the an of to in on at for
with from by is are was were be been it this that these those and or but not no yes you we i me my our your can
could would should will just now then so do does did done get got go make let please also still again any all some
how what why when where which who there here than too very out up off into over under about after before only'''.split())
GLOSS = {  # folded pt prefix -> English words (and the reverse is derived)
    'memori': 'memory mem ram', 'fila': 'queue', 'filas': 'queue', 'frete': 'shipping freight', 'cobr': 'charge billing fee',
    'dobr': 'double twice duplicate', 'duplic': 'duplicate dedupe double', 'limit': 'limit cap', 'requis': 'request requests rps',
    'taxa': 'rate fee', 'conver': 'conversion convert', 'servid': 'server host', 'servic': 'service', 'banco': 'database db',
    'senha': 'password secret', 'usuar': 'user', 'pedid': 'order', 'pagam': 'payment pay', 'fatur': 'invoice billing',
    'reembol': 'refund', 'estorn': 'refund chargeback', 'entreg': 'delivery delivered', 'notific': 'notification push',
    'mensag': 'message', 'erro': 'error', 'falh': 'fail failure failed error', 'quebr': 'broken break fail failing',
    'caind': 'crash down crashing', 'cai': 'crash down', 'travad': 'hang stuck', 'lent': 'slow latency', 'tempo': 'time timeout',
    'espera': 'wait timeout', 'demor': 'slow latency timeout', 'teste': 'test tests', 'testes': 'test tests', 'implant': 'deploy',
    'deploy': 'deploy release', 'subi': 'push deploy', 'sobe': 'push deploy', 'commit': 'commit', 'ramo': 'branch',
    'arquiv': 'file', 'pasta': 'folder directory dir', 'config': 'config configuration settings', 'ajust': 'adjust config tune',
    'corrig': 'fix', 'arrum': 'fix', 'consert': 'fix', 'version': 'version', 'versao': 'version', 'atualiz': 'update upgrade',
    'apag': 'delete remove purge', 'limp': 'clean cleanup prune purge', 'expurg': 'purge delete', 'remov': 'remove delete',
    'guard': 'retention keep store', 'reten': 'retention', 'dias': 'days', 'semana': 'week', 'horas': 'hours', 'minut': 'minute minutes',
    'segund': 'second seconds', 'treino': 'training train', 'trein': 'training train', 'retom': 'resume', 'model': 'model',
    'lote': 'batch', 'lotes': 'batch', 'envi': 'send', 'mand': 'send', 'reenv': 'retry resend', 'tentat': 'retry attempt attempts',
    'agend': 'schedule cron', 'tarefa': 'job task', 'rotin': 'job cron routine', 'trabalh': 'job worker', 'cliente': 'client customer',
    'chave': 'key', 'chaves': 'keys key', 'regra': 'rule policy', 'permiss': 'permission', 'acesso': 'access', 'login': 'login auth',
    'autentic': 'auth authentication', 'assinat': 'signature subscription', 'verific': 'verify verification check',
    'carrinh': 'cart', 'preco': 'price pricing', 'desconto': 'discount', 'estoque': 'inventory stock', 'produt': 'product',
    'cadastr': 'signup register', 'endere': 'address', 'tela': 'screen page', 'pagina': 'page', 'botao': 'button',
    'formul': 'form', 'campo': 'field', 'coluna': 'column', 'tabela': 'table', 'linha': 'row line', 'registr': 'record log',
    'relator': 'report', 'painel': 'dashboard panel', 'bateria': 'battery', 'veicul': 'vehicle', 'caminh': 'truck vehicle',
    'motoris': 'driver', 'entregad': 'courier driver', 'sensor': 'sensor', 'sonda': 'probe sensor', 'umidad': 'humidity moisture',
    'temperat': 'temperature', 'ordem': 'order ordering', 'fora': 'out', 'jogad': 'player', 'partid': 'match', 'pontua': 'score',
    'placar': 'leaderboard score', 'temporad': 'season', 'fila de': 'queue', 'cota': 'quota', 'custo': 'cost', 'plano': 'plan tier',
    'contrat': 'contract plan', 'produca': 'production prod', 'producao': 'production prod', 'homolog': 'staging', 'ambient': 'environment env',
    'nuvem': 'cloud', 'disco': 'disk', 'espaco': 'space disk', 'cache': 'cache', 'janela': 'window', 'alerta': 'alert',
    'aviso': 'warning', 'cert': 'cert certificate tls', 'segur': 'security', 'privac': 'privacy', 'jurid': 'legal',
    'politic': 'policy', 'convers': 'conversation', 'resum': 'summary', 'pendent': 'pending', 'migrac': 'migration',
    'esquem': 'schema', 'indic': 'index', 'consult': 'query', 'event': 'event events', 'brut': 'raw', 'dados': 'data',
    'checkpoint': 'checkpoint ckpt', 'sinistr': 'claim', 'aberto': 'open', 'fechad': 'closed', 'encerr': 'closed',
    'tamanho': 'size', 'largur': 'width', 'altur': 'height', 'espacam': 'spacing gap padding', 'rodape': 'footer',
    'cabec': 'header', 'mobil': 'mobile', 'celul': 'mobile phone', 'proxim': 'next', 'passo': 'step', 'falta': 'left remaining todo',
    'ponto': 'point', 'fort': 'strength strengths', 'frac': 'weakness weaknesses', 'projet': 'project', 'licen': 'license',
    'receb': 'receive received', 'reconcil': 'reconcile reconciliation', 'madrug': 'night nightly overnight',
    'patinet': 'scooter', 'antig': 'old legacy', 'funcion': 'work working', 'parou': 'stopped stop', 'parar': 'stop',
    'liber': 'free release', 'motiv': 'reason cause', 'explic': 'explain', 'vezes': 'times twice', 'ninguem': 'nobody',
    'termin': 'finish complete', 'chega': 'arrive receive', 'atras': 'late delay lag', 'retent': 'retention',
    'vazam': 'leak', 'travam': 'hang freeze', 'idemp': 'idempotency idempotent', 'repet': 'repeat duplicate retry',
    'sincron': 'sync', 'atual': 'current latest', 'novo': 'new', 'nova': 'new', 'velh': 'old stale', 'lento': 'slow',
    'rapid': 'fast quick', 'grand': 'large big', 'pequen': 'small', 'vazi': 'empty', 'cheio': 'full', 'aviao': 'plane',
    'loja': 'store shop', 'compra': 'purchase checkout', 'pix': 'pix payment', 'boleto': 'boleto invoice', 'nota fiscal': 'invoice',
    'fiscal': 'tax invoice', 'imposto': 'tax', 'moeda': 'currency', 'cambio': 'exchange rate', 'arredond': 'round rounding',
    'fuso': 'timezone tz', 'horari': 'time schedule timezone', 'data': 'date', 'agenda': 'schedule calendar',
    'lembret': 'reminder', 'consult': 'appointment query', 'clinic': 'clinic', 'paciente': 'patient', 'senh': 'password',
    'imagem': 'image', 'foto': 'photo image', 'video': 'video', 'audio': 'audio', 'som': 'sound audio', 'fonte': 'font source',
    'cor': 'color', 'tema': 'theme', 'escur': 'dark', 'clar': 'light',
}
EXP = defaultdict(set)  # 5-char stem -> stems in the other language
for _pt, _en in GLOSS.items():
    for _w in _en.split():
        EXP[fold(_pt)[:5]].add(_w[:5])
        EXP[_w[:5]].add(fold(_pt)[:5])


def words(s):
    """Folded word tokens with identifiers split (camelCase, snake_case, dotted / slashed paths)."""
    return [w for w in WORD_RE.findall(fold(IDENT_RE.sub(r'\1 \2', s)).replace('_', ' ')) if w not in STOP]


def stems(s):
    return {w[:5] for w in words(s) if len(w) >= 3 and not w.isdigit()}


def expand(st):
    out = set(st)
    for x in st:
        out |= EXP.get(x, set()) | EXP.get(x[:4], set())  # 4-letter keys ('cobr', 'dobr', 'fila') match longer stems
    return out


# --- stage-1 patterns (folded text) ------------------------------------------------------------------------
DIRECTIVE_RE = re.compile(
    r"\b(?:regra|nunca|sempre|jamais|proibid\w*|nao (?:mex|toc|us|rod|mand|envi|commit|fa[cz]|apag|edit|confi|mud|"
    r"deix|esquec|pod|quer|precis|e |eh )\w*|so (?:se|quando|em|no|na|pra|com|depois)|somente|apenas|exceto|excecao|"
    r"menos (?:o|a|os|as|quando|se|em|no|na|pra|com)\b|a menos que|a nao ser|salvo|fica(?:m)? (?:fora|de fora|com)|esqueci|"
    r"importante|lembrando|lembra que|obs\b|atencao|cuidado|fyi|mudei de ideia|na verdade|corre[cç]\w*|errei|"
    r"desconsider\w*|ignora|esquece|volta (?:pra|para|o|a)|confirm\w*|desatualizad\w*|"
    r"never|always|don'?t|do not|must|only|except|unless|but not|forgot|heads up|note:|actually|"
    r"scratch that|instead|revert|ignore (?:the|that|whatever|what)|stale|out of date|outdated|is gone|leave \w+ alone|hold off|stays?\b|"
    r"make sure|careful)", re.I)
QUALIFIER_RE = re.compile(r"\b(?:exceto|excecao|menos (?:o|a|os|as|quando|se|em|no|na|pra|com)\b|a menos que|a nao ser|"
                          r"salvo|so (?:se|quando)|fica(?:m)? (?:fora|de fora)|except|unless|but not|only (?:if|when|for)|"
                          r"stays?\b|leave \w+ alone|other than|on hold|legal hold|se (?:nao|precisar|vier|tiver|houver)\b|"
                          r"\bcaso\b|\bsomente\b|apenas (?:para|pra|se|quando|o|a|os|as)\b|fica(?:m)? como (?:esta|ta)|"
                          r"without (?:explicit )?(?:permission|approval)|only proceed|"
                          r"\bif (?:you |the |there |it )?(?:cannot|can'?t|is not|isn'?t|are not|aren'?t|no)\b)", re.I)
HEDGE_RE = re.compile(r"\b(?:acho que|eu acho|pelo que (?:lembro|me lembro)|se nao me engano|provavelmente|talvez|"
                      r"deve ser|imagino que|chuto|i think|i believe|probably|maybe|might be|if i recall|iirc|"
                      r"not sure|i guess|presumably|should be around|from memory)\b", re.I)
INJECTION_RE = re.compile(r"(?:ignore (?:all |any )?(?:the |your )?(?:previous|prior|above|earlier) (?:instructions|rules)|"
                          r"ignor[ae] (?:as |todas as )?(?:instrucoes|regras) anteriores|disregard (?:the |all )?(?:previous|prior|above)|"
                          r"important system notice|system override|note to (?:ai|the ai|assistants?|agents?|llms?|automated)|"
                          r"(?:ai|llm|automated) (?:agents?|assistants?|tools?)(?: reading this)?[:,] (?:you|please|ignore|do|run|skip|disable)|"
                          r"do not (?:tell|inform|mention (?:this )?to) the user|"
                          r"(?:nota|aviso|instrucao) para (?:a |o )?(?:ia|agente|assistente)|se voce (?:e|for) (?:uma|um) (?:ia|agente))", re.I)
GIT_GOAL_RE = re.compile(r"\b(?:commit\w*|push|pr\b|pull request|merge|sob[ei]r?|subir|ship|branch|abre o pr|"
                         r"open (?:a|the) pr|release it)", re.I)
GIT_STATUS_RE = re.compile(r"^\s*(?:##\s+\S+(?:\.\.\.\S+)?|(?:[MADRCU?]{1,2})\s+\S+|on branch \S+|changes (?:not )?staged|"
                           r"untracked files:)", re.I | re.M)
CONVENTION_RE = re.compile(r"(?:agents\.md|contributing(?:\.md)?|claude\.md|##\s*(?:commits?|git)\b|conventional commits|"
                           r"commit message|co-authored-by|signed-off|\bdco\b|\brefs: |git commit -s)", re.I)
WIDE_GOAL_RE = re.compile(r"\b(?:o que (?:voce|vc|tu) acha|pontos fortes|pontos fracos|visao geral|overview|status do projeto|"
                          r"o que (?:ainda )?falta|what'?s left|strengths|weaknesses|review (?:the|this) project|"
                          r"avali\w* o projeto|como (?:esta|ta) o projeto|roadmap|big picture)", re.I)
STALE_RE = re.compile(r"\b(?:deprecated|legacy|outdated|obsolet\w*|desatualizad\w*|nao (?:e|eh) mais usad\w*|"
                      r"no longer used|kept for reproducing|last updated:? 20(?:0\d|1\d|2[0-4])|"
                      r"ultima (?:revisao|atualizacao):? \S* ?20(?:0\d|1\d|2[0-5])|old version|versao antiga)", re.I)
PROD_GOAL_RE = re.compile(r"\b(?:prod|producao|production|live|em prd)\b", re.I)
NONPROD_RE = re.compile(r"\b(?:staging|stg|sandbox|homolog\w*|dev(?:elopment)? env|ambiente de (?:teste|dev)|local\.dev)\b", re.I)
PROD_RE = re.compile(r"\b(?:prod|producao|production|prd)\b", re.I)
DOC_RE = re.compile(r"\b(?:readme|roadmap|status|todo|changelog|plan|architecture|arquitetura)\.md\b", re.I)
ORDINAL_RE = re.compile(r"\b(?:o|a) (?:primeir|segund|terceir|ultim)\w*|\b(?:op[cç]ao|option|alternativa|item) ?\d\b|"
                        r"\bthe (?:first|second|third|last) (?:one|fix|option|approach|failure|test|error|suggestion)|"
                        r"\b(?:first|second|third) (?:fix|option|approach|one)\b|^\s*\d(?:\s*(?:e|and|,)\s*\d)+\s*$|"
                        r"\bnaquele (?:primeiro|segundo|terceiro)|\bdaquele (?:primeiro|segundo)", re.I)
ENUM_RE = re.compile(r"(?:^|\s)(?:\(?[1-3][).:]|option [1-3]|op[cç]ao [1-3]|[1-3]\. )\s*\S", re.I)
SAID_RE = re.compile(r"\b(?:(?:tu|voce|vc) (?:falou|disse|sugeriu|propos|comentou)|do jeito que (?:tu|voce|vc)|"
                     r"(?:you|u) (?:said|suggested|proposed|mentioned|recommended)|what you (?:said|suggested)|"
                     r"as you (?:said|suggested)|your (?:suggestion|plan|fix)|que (?:eu )?(?:te )?falei|i told you|"
                     r"combinad\w*|we agreed|agreed on|we settled|settled on|ended up with)\b", re.I)


META_RE = re.compile(r"[|\\]|\binject|regex|pattern|detect|guard|sanitiz", re.I)


INJ_HINTS = ('ignor', 'disregard', 'system', 'note to', 'agent', 'assistant', 'tool', 'do not', 'para ', 'se voce')


def injected(text):
    """INJECTION_RE outside quotes / code / text about injection itself (seen in the owner's own tooling)."""
    t = text[:20000]
    if not any(k in t for k in INJ_HINTS):  # cheap pre-filter: every INJECTION_RE branch contains one of these
        return False
    for m in INJECTION_RE.finditer(t):
        lo, hi = text.rfind('\n', 0, m.start()) + 1, text.find('\n', m.end())
        line = text[lo:hi if hi >= 0 else None]
        if not META_RE.search(line.replace(m.group(0), '')):
            return True
    return False


# --- stage-2: facts with units ------------------------------------------------------------------------------
NUM = r'(\d+(?:[.,]\d+)?(?:e-?\d+)?)'
UNIT_RE = re.compile(NUM + r"\s*(%|ms\b|s\b|seg\w*|segundos?|seconds?|secs?\b|min\b|minutos?|minutes?|h\b|horas?|hours?|"
                     r"d\b|dias?|days?|(?:ki|mi|gi|k|m|g)i?b?\b|req(?:uests?|uisi\w+)?\s*(?:/|por|per)\s*(?:min\w*|s\w*|"
                     r"h\w*)|rpm\b|rps\b)", re.I)
KV_RE = re.compile(r"^[\s>|#*-]*\"?([A-Za-z_][\w.\-]*)\"?\s*[:=]\s*\"?([^\s\",#]+)", re.M)
UNIT_CLASS = [(re.compile(r'^%'), 'pct'), (re.compile(r'^ms'), 'ms'), (re.compile(r'^(?:s|seg|segundo|second|sec)', re.I), 's'),
              (re.compile(r'^(?:min|minuto|minute)', re.I), 'min'), (re.compile(r'^(?:h|hora|hour)', re.I), 'h'),
              (re.compile(r'^(?:d|dia|day)', re.I), 'd'), (re.compile(r'^(?:ki|mi|gi|k|m|g)', re.I), 'bytes'),
              (re.compile(r'^(?:req|rpm|rps)', re.I), 'rate')]


def unit_class(u):
    u = u.strip().lower()
    if re.match(r'^req', u):
        return 'rate'
    for r, c in UNIT_CLASS:
        if r.match(u):
            return c
    return None


DIGIT_RE = re.compile(r'\d')
NOFACT_RE = re.compile(r'\{"|\\n|</?[a-z]|classname|class=|style=|https?://|wall time|\bcommit [0-9a-f]{7}|^\s*[0-9a-f]{7} |'
                       r'\b(?:in|took|elapsed) \d[\d.]*\s*(?:ms|s|sec)|\bpassed\b|\bfailed\b|\[\s*\d+%\]|uploaded|'
                       r'\btests?:|\d+/\d+\)', re.I)


def same_subject(a, b):
    """Two fact lines talk about the same thing: >= 2 shared non-numeric stems (beyond the common ones)."""
    return len({x for x in a & b if not x[0].isdigit()}) >= 2


def facts(body, cap=40):
    """[(qty, value, line stems, line)]: numbers with a unit class, and config 'key: value' leaves (qty = 'k:<key>')."""
    out = []
    for line in body[:12000].splitlines():
        if len(line) > 300 or not DIGIT_RE.search(line) or NOFACT_RE.search(line):
            continue
        st = stems(line)
        for m in UNIT_RE.finditer(line):
            c = unit_class(m.group(2))
            if c:
                out.append((c, m.group(1).replace(',', '.'), st, line))
        for m in KV_RE.finditer(line):
            k, v = m.group(1).lower(), m.group(2).lower()
            if any(ch.isdigit() for ch in v) and len(k) >= 3:
                suf = re.search(r'(?:_|\b)(ms|seconds?|secs?|s|minutes?|min|hours?|h|days?|d|pct|percent|mb|gb|mi|gi)$', k)
                c = unit_class(suf.group(1)) if suf else None
                out.append((c or 'k:' + re.sub(r'.*[.]', '', k), re.sub(r'[^\w.]', '', v), st, line))
        if len(out) >= cap:
            break
    return out


# --- detectors ------------------------------------------------------------------------------------------------
def detect(goal, texts, base=None, cascade=True, meta=None):
    """-> (strong set, weak set, demote set, flags {i: [names]}). base: stage-1 scores (cascade needs them)."""
    n = len(texts)
    meta = meta or s2.block_meta(texts)
    bodies = [s2.HEADER_RE.sub('', t).strip() for t in texts]
    fb = [fold(b[:6000]) for b in bodies]
    gfold = fold(goal)
    gst = stems(goal)
    gx = expand(gst)
    flags = defaultdict(list)
    strong, weak, demote = set(), set(), set()
    role = [m[1] for m in meta]
    kind = [m[2] for m in meta]
    is_user = [role[i] == 'user' and kind[i] == 'text' for i in range(n)]
    is_asst = [role[i] == 'assistant' and kind[i] == 'text' for i in range(n)]
    is_tool = [kind[i] == 'tool_result' for i in range(n)]
    # user_directive: a user statement of a rule / exception / correction / authority
    ud = [i for i in range(n) if is_user[i] and len(bodies[i]) < UD_MAXLEN and DIRECTIVE_RE.search(fb[i])]
    for i in ud[-UD_CAP:]:
        strong.add(i)
        flags[i].append('user_directive')
    # injection: flag only (the block stays evidence; never a rule)
    for i in range(n):
        if not is_user[i] and injected(fb[i]):
            flags[i].append('injection')
    # hedge: an assistant guess
    for i in range(n):
        if is_asst[i] and HEDGE_RE.search(fb[i][:2000]):
            demote.add(i)
            flags[i].append('hedge')
    # stale docs / other-environment blocks: demoted (frees budget for the current, matching evidence)
    prod_goal = bool(PROD_GOAL_RE.search(gfold))
    for i in range(n):
        if is_tool[i] and STALE_RE.search(fb[i][:3000]):
            demote.add(i)
            flags[i].append('stale')
        elif prod_goal and not is_user[i] and NONPROD_RE.search(fb[i][:3000]) and not PROD_RE.search(fb[i][:3000]):
            demote.add(i)
            flags[i].append('other_env')
    # goal_xling: goal match after pt<->en expansion and identifier splitting (counts distinct stems, idf-weighted)
    bst = [stems(b[:6000]) for b in bodies]
    df = Counter(x for s in bst for x in s & gx)
    xs = np.zeros(n)
    for i in range(n):
        hit = bst[i] & gx
        xs[i] = sum(math.log(1 + n / df[x]) for x in hit) if len(hit) >= 2 else 0.0
    for i in [int(k) for k in np.argsort(-xs, kind='stable')[:2] if xs[k] > 0]:
        weak.add(i)
        flags[i].append('goal_xling')
    # translated_only: evidence that matches the goal ONLY through the other language (pt goal, English code / logs)
    tx = gx - gst
    if tx:
        ts = np.array([sum(math.log(1 + n / df[x]) for x in bst[i] & tx) if len(bst[i] & tx) >= 2 and not bst[i] & gst
                       else 0.0 for i in range(n)])
        for i in [int(k) for k in np.argsort(-ts, kind='stable')[:1] if ts[k] > 0]:
            weak.add(i)
            flags[i].append('translated_only')
    # git_state / conventions
    if GIT_GOAL_RE.search(gfold):
        gs = [i for i in range(n) if is_tool[i] and len(GIT_STATUS_RE.findall(bodies[i][:4000])) >= 2]
        for i in sorted(set(gs[:1] + gs[-2:])):  # the first status (what was dirty before) and the latest ones
            strong.add(i)
            flags[i].append('git_state')
        conv = [i for i in range(n) if is_tool[i] and CONVENTION_RE.search(fb[i]) and not STALE_RE.search(fb[i])]
        conv.sort(key=lambda i: ('agents.md' not in fb[i], -i))
        for i in conv[:2]:
            strong.add(i)
            flags[i].append('convention')
    # wide view: project docs
    if WIDE_GOAL_RE.search(gfold):
        for i in [i for i in range(n) if is_tool[i] and DOC_RE.search(fb[i][:300])][:3]:
            strong.add(i)
            flags[i].append('wide_doc')
    # ordinal reference -> latest enumerated block
    if ORDINAL_RE.search(gfold):
        en = [i for i in range(n) if (is_asst[i] or is_tool[i]) and len(ENUM_RE.findall(bodies[i][:4000])) >= 2]
        en.sort(key=lambda i: (len(bst[i] & gx), i))
        for i in en[-1:]:
            strong.add(i)
            flags[i].append('ordinal_ref')
    # "what you said" -> latest substantive assistant turns
    if SAID_RE.search(gfold):
        sub = [i for i in range(n) if is_asst[i] and len(bodies[i]) >= 120][-6:]
        for i in sorted(sub, key=lambda i: (len(bst[i] & gx), i))[-2:]:
            strong.add(i)
            flags[i].append('said_ref')
    # --- stage 2 (cascade) ---------------------------------------------------------------------------------
    if cascade is None:
        return strong, weak, demote, flags
    if base is not None and cascade:
        s1 = np.asarray(base, float) + 3.0 * np.isin(np.arange(n), list(strong | weak))
        tok = np.array([max(1, math.ceil(len(t) / 4)) for t in texts], float)
        order = np.lexsort((np.arange(n), s1))
        cum = np.cumsum(tok[order]) / tok.sum()
        risk = set(order[cum <= AT_RISK + 1e-9].tolist())
    else:
        risk = set(range(n))
    # value_conflict: the same quantity with different values in two goal-related lines
    fx = {i: facts(bodies[i]) for i in range(n) if not is_asst[i] or i in risk}
    common = {x for x, c in Counter(x for s in bst for x in s).items() if c > max(3, n // 4)}
    by_q = defaultdict(list)
    for i, fs in fx.items():
        qc = Counter(q for q, _, _, _ in fs)
        for q, v, st, _ in fs:
            rel = len((st & gx) - common)
            if rel and qc[q] <= 2:  # a distinctive quantity of this block, not a repeated log field
                by_q[q].append((i, v, rel, st - common))
    cands = []
    for q, hs in by_q.items():
        if len({h[1] for h in hs}) < 2 or not 2 <= len({h[0] for h in hs}) <= 4:  # many holders = record data
            continue
        for i, v, rel, st in hs:
            if i in risk and any(j != i and v2 != v and same_subject(st, st2) for j, v2, _, st2 in hs):
                cands.append((rel, i))
    for _, i in sorted(set(cands), key=lambda t: (-t[0], -t[1]))[:3]:
        strong.add(i)
        flags[i].append('value_conflict')
    # qualifier_link: the tool output that carries the condition an exception names
    quals = [i for i in ud if QUALIFIER_RE.search(fb[i])]
    if quals:
        dfa = Counter(x for s in bst for x in s)
        recent_users = [i for i in range(n) if is_user[i]][-4:]
        for q in [q for q in quals if q in recent_users][-2:]:
            terms = bst[q] - gx
            best, bi = 0.0, None
            for i in range(q + 1, n):
                if i in risk and is_tool[i]:
                    w = sum(math.log(n / dfa[x]) for x in terms & bst[i] if dfa[x] <= max(2, n // 10))
                    if w > best:
                        best, bi = w, i
            if bi is not None and best >= 3.0:
                strong.add(bi)
                flags[bi].append('qualifier_link')
    return strong, weak, demote, flags


WEAK, DEMOTE, FLAG_ONLY = {'goal_xling'}, {'hedge', 'stale', 'other_env'}, {'injection'}


def combine(base, flags, bonus, weak, off=(), sizes=None, max_chars=None):
    """Stage-1 v3 score + bonus for protected blocks (weak detectors: weak x bonus), - bonus/2 for demoted ones.
    max_chars: blocks longer than this get no bonus (protection is for short evidence; bounds the token cost)."""
    add = np.zeros(len(base))
    for i, names in flags.items():
        on = [x for x in names if x not in off]
        big = max_chars is not None and sizes[i] > max_chars
        if big and not any(x in DEMOTE for x in on):
            continue
        if any(x not in WEAK | DEMOTE | FLAG_ONLY for x in on):
            add[i] = bonus
        elif any(x in WEAK for x in on):
            add[i] = bonus * weak
        elif any(x in DEMOTE for x in on):
            add[i] = -0.5 * bonus
    return np.asarray(base, float) + add


class Judge:
    """model json: {kind: 'v5', v3: <v3 model dict>, bonus, weak, cascade}. Higher = keep."""

    def __init__(self, model):
        self.model = model
        self.v3 = s3.Judge(model['v3'])

    @classmethod
    def load(cls, path=None):
        return cls(json.loads(Path(path or ART / 'model.json').read_text()))

    def score_full(self, goal, texts):
        if not texts:
            return [], {}
        X = s2.featurize(goal, texts)
        base = np.asarray(self.v3.score_x(X))
        m = self.model
        flags = detect(goal, texts, base, m['cascade'])[3]
        return combine(base, flags, m['bonus'], m['weak'], m.get('off', ()), [len(t) for t in texts],
                       m.get('max_chars')).tolist(), dict(flags)

    def score(self, goal, texts):
        return self.score_full(goal, texts)[0]

    def flags(self, goal, texts):
        return self.score_full(goal, texts)[1]


OFF = ('stale', 'hedge')  # detected and flagged, but no score change (train-sample cost, no dev-edge gain)


def build(bonus=3.0, weak=0.25, cascade=True, max_chars=1000, off=OFF):
    v3 = json.loads((s3.ART / 'model.json').read_text())
    return dict(kind='v5', v3=v3, bonus=bonus, weak=weak, cascade=cascade, max_chars=max_chars, off=list(off))


# --- development helpers (edge suites; train sample) --------------------------------------------------------
def edge_counts(cases, judge):
    from research import edge_suite as es
    sc = {c['id']: dict(zip([b['id'] for b in c['blocks']], judge.score(c['goal'], s2.edge_texts(c)))) for c in cases}
    return es.summary(cases, es.run(cases, sc)), sc


def by_type(cases, sm):
    out = defaultdict(lambda: [0, 0, 0, 0])
    for c in cases:
        t = out[c.get('edge_type', c['category'])]
        t[3] += 1
        for k, b in enumerate((30, 50, 70)):
            t[k] += c['id'] not in sm[b]['failed']
    return dict(sorted(out.items()))


def edge_phase(bonus=3.0, weak=0.25, cascade=True):
    from research import edge_suite as es
    from research import edge_v2 as e2
    out = {}
    for name, cases in (('old', es.load_cases()), ('dev2', e2.load_dev())):
        for arm, j in (('v3', s3.Judge.load()), ('v5', Judge(build(bonus, weak, cascade)))):
            sm, _ = edge_counts(cases, j)
            out[f'{name}/{arm}'] = dict(cuts=[sm[b]['passed'] for b in (30, 50, 70)], by_type=by_type(cases, sm),
                                        failed50=sm[50]['failed'])
    return out


def train_sample(n=200):
    """Seeded sample of plain TRAIN items (specialist_v4.train_guard): development regression check only."""
    import random
    from research import specialist_v4 as s4
    ids = s4.train_guard(s4.train_ids())
    random.Random(SEED).shuffle(ids)
    return sorted(ids[:n])


def item_aucs(it, sc):
    from research import matched_budget_v2 as mb
    pm = mb.item_metrics(it, sc)
    return {m: mb.auc([(0, 1.0)] + [(b, float(pm[b][m])) for b in mb.BUDGETS]) for m in ('recall', 'all_kept')}


def trainsample_phase(bonus=3.0, weak=0.25, cascade=True, n=200):
    """v5 - v3 per-item AUC on a train sample (v3 was fit on these items: a regression guard, not evidence)."""
    from research import matched_budget_v2 as mb
    j3, j5 = s3.Judge.load(), Judge(build(bonus, weak, cascade))
    d = defaultdict(list)
    for it, texts in s2.load_items(train_sample(n)):
        if not mb.eligible(it):
            continue
        cand = [k for k, b in enumerate(it['blocks']) if not b['protected']]
        a3, a5 = j3.score(it['goal'], texts), j5.score(it['goal'], texts)
        r3 = item_aucs(it, {it['blocks'][k]['id']: a3[k] for k in cand})
        r5 = item_aucs(it, {it['blocks'][k]['id']: a5[k] for k in cand})
        for m in r3:
            d[m].append(r5[m] - r3[m])
    return {m: dict(n=len(v), mean=round(float(np.mean(v)), 4), worse=sum(x < 0 for x in v), better=sum(x > 0 for x in v))
            for m, v in d.items()}


def cache_items(ids, name, cascade=True):
    """Private cache: per item v3 base scores + detector flags + labels needed for metrics (train sample only)."""
    import pickle
    p = ART / f'cache-{name}.pkl'
    if p.exists():
        return pickle.loads(p.read_bytes())
    from research import matched_budget_v2 as mb
    j3 = s3.Judge.load()
    rows = []
    for it, texts in s2.load_items(ids):
        if not mb.eligible(it):
            continue
        base = np.asarray(j3.score_x(s2.featurize(it['goal'], texts)))
        rows.append((it, base, texts))
    ART.mkdir(parents=True, exist_ok=True, mode=0o700)
    p.write_bytes(pickle.dumps(rows))
    p.chmod(0o600)
    return rows


def with_flags(rows, cascade=True):
    """cached (item, base, texts) -> (item, base, flags) with the current detectors."""
    return [(it, base, dict(detect(it['goal'], texts, base, cascade)[3]), [len(t) for t in texts]) for it, base, texts in rows]


def ablate(rows, bonus=3.0, weak=0.5, offs=((),), max_chars=None):
    """{variant: {metric: mean(v5 - v3), worse, better}} from (item, base, flags) rows."""
    out = {}
    for off in offs:
        d = defaultdict(list)
        for it, base, flags, sizes in rows:
            cand = [k for k, b in enumerate(it['blocks']) if not b['protected']]
            v5 = combine(base, flags, bonus, weak, off, sizes, max_chars)
            r3 = item_aucs(it, {it['blocks'][k]['id']: base[k] for k in cand})
            r5 = item_aucs(it, {it['blocks'][k]['id']: v5[k] for k in cand})
            for m in r3:
                d[m].append(r5[m] - r3[m])
        out['-'.join(off) or 'all'] = {m: (round(float(np.mean(v)), 4), sum(x < 0 for x in v), sum(x > 0 for x in v))
                                       for m, v in d.items()}
    return out


# --- system-1 teacher: candidates (loose heuristics) and detector agreement ------------------------------------
def loose_pairs(goal, texts, cap=6):
    """Candidate fact pairs for the conflict / newer questions: same quantity, different values, both lines share
    any goal stem (no distinctiveness filter). -> [(i, j, line_i, line_j, strict)] where strict = the
    value_conflict detector's own filter (distinctive in both blocks, goal stems beyond the common ones)."""
    meta = s2.block_meta(texts)
    bodies = [s2.HEADER_RE.sub('', t).strip() for t in texts]
    gx = expand(stems(goal))
    n = len(texts)
    bst = [stems(b[:6000]) for b in bodies]
    common = {x for x, c in Counter(x for s in bst for x in s).items() if c > max(3, n // 4)}
    hold = defaultdict(list)
    for i in range(n):
        if meta[i][1] == 'assistant' and meta[i][2] == 'text':
            continue
        fs = facts(bodies[i])
        qc = Counter(f[0] for f in fs)
        for q, v, st, line in fs:
            if st & gx:
                hold[q].append((i, v, line, bool((st & gx) - common) and qc[q] <= 2, st - common))
    out, seen = [], set()
    for q, hs in hold.items():
        for a in range(len(hs)):
            for b in range(a + 1, len(hs)):
                (i, vi, li, si, ti), (j, vj, lj, sj, tj) = hs[a], hs[b]
                if i != j and vi != vj and (i, j) not in seen:
                    seen.add((i, j))
                    out.append((i, j, li.strip(), lj.strip(), si and sj and same_subject(ti, tj)))
    return out[:cap]


def build_questions(set_name, seed=SEED):
    """Questions for research.teacher_v5 (private). train: the cached TRAIN sample; edge: dev-edge v2 fixtures."""
    import random
    from research import teacher_v5 as tv
    rng = random.Random(seed)
    if set_name == 'train':
        items = [(it['item_id'], it['goal'], texts) for it, _, texts in cache_items(train_sample(300), 'train300')]
    else:
        from research import edge_v2 as e2
        items = [(c['id'], c['goal'], s2.edge_texts(c)) for c in e2.load_dev()]
    qs = []
    pools = defaultdict(list)
    for iid, goal, texts in items:
        meta = s2.block_meta(texts)
        bodies = [s2.HEADER_RE.sub('', t).strip() for t in texts]
        fl = detect(goal, texts, None, False)[3]
        for i, b in enumerate(bodies):
            if not b or len(b) > 3000:
                continue
            r = 'user' if meta[i][1] == 'user' and meta[i][2] == 'text' else (
                'assistant' if meta[i][2] == 'text' else 'tool output')
            f = fl.get(i, [])
            key = (r, 'user_directive' in f or 'hedge' in f or 'injection' in f)
            pools[key].append(dict(qid=f'{iid[:12]}-{i}', kind='flags', item=iid, block=i, roles=[r], texts=[b],
                                   det={x: x in f for x in ('user_directive', 'hedge', 'injection')}))
        for i, j, li, lj, strict in loose_pairs(goal, texts):
            r = lambda k: 'user' if meta[k][1] == 'user' and meta[k][2] == 'text' else 'tool output'  # noqa: E731
            for kind in ('conflict', 'newer'):
                pools[('pair', strict)].append(dict(qid=f'{iid[:12]}-{kind[0]}{i}-{j}', kind=kind, item=iid, block=[i, j],
                                                    roles=[r(i), r(j)], texts=[li, lj], det={'value_conflict': strict}))
        if ORDINAL_RE.search(fold(goal)) or SAID_RE.search(fold(goal)):
            for i in range(len(bodies)):
                if meta[i][2] in ('text', 'tool_result') and meta[i][1] != 'user' and 40 < len(bodies[i]) < 3000:
                    pools['coref'].append(dict(qid=f'{iid[:12]}-r{i}', kind='coref', item=iid, block=i,
                                               roles=['user goal', 'earlier block'], texts=[goal, bodies[i]],
                                               det={'ref': any(x in fl.get(i, []) for x in ('ordinal_ref', 'said_ref'))}))
    caps = {('user', True): 250, ('user', False): 250, ('assistant', True): 120, ('assistant', False): 80,
            ('tool output', True): 120, ('tool output', False): 80, ('pair', True): 300, ('pair', False): 300,
            'coref': 150}
    if set_name == 'edge':
        caps = {k: 10 ** 6 if k in (('user', True), ('user', False), ('tool output', True), ('assistant', True),
                                     ('pair', True), ('pair', False), 'coref') else 60 for k in caps}
    for k, pool in sorted(pools.items(), key=lambda kv: str(kv[0])):
        if k[0] == 'pair':  # keep both questions of a pair together
            pairs = sorted({q['qid'][:-len(q['qid'].split('-')[-1])] + '|' + str(q['block']) for q in pool})
            keep = set(rng.sample(pairs, min(len(pairs), caps[k] // 2)))
            qs += [q for q in pool if q['qid'][:-len(q['qid'].split('-')[-1])] + '|' + str(q['block']) in keep]
        else:
            qs += rng.sample(pool, min(len(pool), caps.get(k, 60)))
    rng.shuffle(qs)
    tv.ART.mkdir(parents=True, exist_ok=True, mode=0o700)
    (tv.ART / f'questions-{set_name}.json').write_text(json.dumps(qs, ensure_ascii=False))
    return dict(questions=len(qs), by_kind=Counter(q['kind'] for q in qs), est_calls=len(tv.batches(qs)))


def prf(pairs):
    tp = sum(d and o for d, o in pairs)
    fp = sum(d and not o for d, o in pairs)
    fn = sum(o and not d for d, o in pairs)
    return dict(n=len(pairs), opus_yes=tp + fn, det_yes=tp + fp, precision=round(tp / (tp + fp), 3) if tp + fp else None,
                recall=round(tp / (tp + fn), 3) if tp + fn else None)


def detector_agreement(set_name):
    """Detector vs Opus answers on the asked candidates (recall is relative to the loose candidate pools)."""
    from research import teacher_v5 as tv
    qs = json.loads((tv.ART / f'questions-{set_name}.json').read_text())
    ans = tv.answers(set_name)
    out, nans = defaultdict(list), 0
    for q in qs:
        a = ans.get(q['qid'])
        if not isinstance(a, dict) or 'yes' not in a:
            continue
        nans += 1
        if q['kind'] == 'flags':
            r, t = q['roles'][0], fold(q['texts'][0])
            det = dict(user_directive=len(q['texts'][0]) < UD_MAXLEN and bool(DIRECTIVE_RE.search(t)),
                       hedge=bool(HEDGE_RE.search(t[:2000])), injection=injected(t))
            if r == 'user':
                out['user_directive (user turns)'].append((det['user_directive'], bool(a.get('directive'))))
                out['qualifier marker (user turns)'].append((bool(QUALIFIER_RE.search(fold(q['texts'][0]))),
                                                             bool(a.get('qualifier'))))
            elif r == 'assistant':
                out['hedge (assistant turns)'].append((det['hedge'], bool(a.get('guess'))))
            if r != 'user':
                out['injection (non-user blocks)'].append((det['injection'], bool(a.get('injection'))))
        elif q['kind'] in ('conflict', 'newer'):  # strict filter at build time + the same-subject check added after
            det = (q['det']['value_conflict'] and all(facts(t) for t in q['texts'])
                   and same_subject(stems(q['texts'][0]), stems(q['texts'][1])))
            out['value_conflict' if q['kind'] == 'conflict' else 'value_conflict vs newer'].append((det, bool(a['yes'])))
        else:
            out['ordinal/said ref'].append((q['det']['ref'], bool(a['yes'])))
    return dict(questions=len(qs), answered=nans, detectors={k: prf(v) for k, v in out.items()})


DETECTORS = ('user_directive', 'goal_xling', 'translated_only', 'git_state', 'convention', 'wide_doc', 'ordinal_ref', 'said_ref', 'hedge',
             'stale', 'other_env', 'value_conflict', 'qualifier_link')


# --- selection (V5_SELECTION_RULE.md) and the one-time sealed measurement ----------------------------------
GRID = [dict(bonus=b, cascade=c) for b in (2.0, 3.0) for c in (True, None)]  # cascade None = stage 1 only
BOOT_SEED = 20261018
V5_BENCH = s2.BENCH.replace('from research.specialist_v2 import Judge', 'from research.specialist_v5 import Judge')


def cfg_name(g):
    return f"b{g['bonus']:g}_{'s12' if g['cascade'] else 's1'}"


def bench(model_path, items):
    orig = s2.BENCH
    s2.BENCH = V5_BENCH
    try:
        return s2.bench(model_path, items, n=len(items))
    finally:
        s2.BENCH = orig


def select_phase():
    """V5_SELECTION_RULE.md, verbatim. Dev = the 325 eligible dev items, full-text scoring (as live)."""
    import os
    from research import edge_suite as es
    from research import edge_v2 as e2
    from research import matched_budget_v2 as mb
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    ART.mkdir(parents=True, exist_ok=True, mode=0o700)
    items, skip = mb.eligible_dev()
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    j3 = s3.Judge.load()
    names = ['v3'] + [cfg_name(g) for g in GRID]
    per = {a: {} for a in names}
    for it, texts in s2.load_items([it['item_id'] for it in items]):
        base = np.asarray(j3.score_x(s2.featurize(it['goal'], texts)))
        fl = {c: dict(detect(it['goal'], texts, base, c)[3]) for c in (True, None)}
        sizes = [len(t) for t in texts]
        cand = [k for k, b in enumerate(it['blocks']) if not b['protected']]
        for a in names:
            sc = base if a == 'v3' else combine(base, fl[GRID[names.index(a) - 1]['cascade']],
                                                GRID[names.index(a) - 1]['bonus'], 0.25, OFF, sizes, 1000)
            pm = mb.item_metrics(it, {it['blocks'][k]['id']: float(sc[k]) for k in cand}, groups=groups[it['item_id']])
            per[a][it['item_id']] = {m: mb.auc([(0, 1.0)] + [(b, float(pm[b][m])) for b in mb.BUDGETS])
                                     for m in ('recall', 'all_kept')}
    mean = {a: {m: round(float(np.mean([v[m] for v in per[a].values()])), 4) for m in ('recall', 'all_kept')} for a in names}
    old, dev2 = es.load_cases(), e2.load_dev()
    judges = {'v3': j3} | {cfg_name(g): Judge(build(g['bonus'], cascade=g['cascade'])) for g in GRID}
    edge = {}
    for a, j in judges.items():
        so, _ = edge_counts(old, j)
        sd, _ = edge_counts(dev2, j)
        edge[a] = dict(old=[so[b]['passed'] for b in (30, 50, 70)], dev2=[sd[b]['passed'] for b in (30, 50, 70)],
                       dev2_by_type=by_type(dev2, sd), old_by_category=by_type(old, so))
    log = []
    for g in GRID:
        a = cfg_name(g)
        boot = {m: s3.group_bootstrap(items, {k: v[m] for k, v in per[a].items()}, {k: v[m] for k, v in per['v3'].items()},
                                      seed=BOOT_SEED) for m in ('recall', 'all_kept')}
        r = dict(config=a, **g, dev=mean[a], dev_vs_v3=boot, **edge[a])
        r['eligible_dev'] = all(boot[m]['ci95'][0] > -0.005 for m in boot)
        r['eligible_old_edge'] = all(x >= y for x, y in zip(edge[a]['old'], edge['v3']['old']))
        r['eligible_dev_edge'] = sum(edge[a]['dev2']) > sum(edge['v3']['dev2'])
        r['eligible'] = r['eligible_dev'] and r['eligible_old_edge'] and r['eligible_dev_edge']
        log.append(r)
        print(json.dumps({k: v for k, v in r.items() if 'by_' not in k}), flush=True)
    ok = [r for r in log if r['eligible']]
    pick = max(ok, key=lambda r: (sum(r['dev2']), sum(r['old']), r['dev']['recall'] + 0.25 * r['dev']['all_kept'])) if ok else None
    cost = None
    if pick:
        model = build(pick['bonus'], cascade=pick['cascade'])
        (ART / 'model.json').write_text(json.dumps(model))
        cost = dict(dev_v5=bench(ART / 'model.json', items), dev_v3=s3.bench(s3.ART / 'model.json', items))
        c = cost['dev_v5']
        pick['budgets_ok'] = c['ms_median'] < 250 and c['peak_rss_mb'] < 300 and c['model_file_kb'] < 1024
    adopt = bool(pick and pick['budgets_ok'])
    res = dict(schema='specialist-v5/dev', rule='V5_SELECTION_RULE.md', items=len(items), excluded=dict(skip),
               v3=dict(dev=mean['v3'], **edge['v3']), log=log, pick=pick and pick['config'], adopt=adopt, cost=cost)
    (ART / 'select-log.json').write_text(json.dumps(res, indent=1))
    (OUT / 'v5-dev-results.json').write_text(json.dumps(res, indent=1) + '\n')
    return dict(pick=res['pick'], adopt=adopt, v3=res['v3']['dev'], cost=cost and {k: {x: v.get(x) for x in (
        'ms_median', 'ms_p90', 'peak_rss_mb', 'model_file_kb')} for k, v in cost.items()})


def sealed_opus_caller(arm, text, cwd):
    """llm_judge_arm caller that routes through research.opus_cli (ledger + cap); same argv as the Opus arm."""
    from research import llm_judge_arm as lj
    from research import opus_cli
    obj = opus_cli.call(lj.SYSTEM, lj.SCHEMA, text, 'sealed')
    return json.dumps(dict(is_error=False, structured_output=obj)), '', 0


def final_phase(opus=True):
    """Opens the sealed edge v2 ONCE (V5_SELECTION_RULE.md step 4): v3, v5 pick, bm25, recency, Opus."""
    from research import edge_suite as es
    from research import edge_v2 as e2
    from research import llm_judge_arm as lj
    marker = ART / 'sealed-opened.json'
    sealed = e2.load_sealed(i_mean_it=True)
    if not marker.exists():
        marker.write_text(json.dumps(dict(opened=__import__('time').time(), n=len(sealed))))
    arms = {}
    diag = ART / 'model-diag.json'  # Amendment 1: no eligible pick; the sealed diagnostic config is b3_s12
    if not (ART / 'model.json').exists() and not diag.exists():
        diag.write_text(json.dumps(build(3.0, cascade=True)))
    v5 = Judge.load(ART / 'model.json' if (ART / 'model.json').exists() else diag)
    for name, j in (('v3', s3.Judge.load()), ('v5', v5)):
        arms[name] = edge_counts(sealed, j)[1]
    arms['bm25'] = es.arm_scores(sealed, es.bm25)
    arms['recency'] = es.arm_scores(sealed, es.recency)
    arms['oracle'] = es.arm_scores(sealed, es.oracle)
    run = None
    if opus:
        items = [(c['id'], c['goal'], [(b['id'], b['text']) for b in c['blocks']]) for c in sealed]
        run = lj.run('opus', 'edge-v2-sealed', items=items, caller=sealed_opus_caller)
        sc = lj.scores('opus', 'edge-v2-sealed')
        if len(sc) == len(sealed):
            arms['opus'] = sc
    out = {}
    for a, sc in arms.items():
        sm = es.summary(sealed, es.run(sealed, sc))
        out[a] = dict(cuts=[sm[b]['passed'] for b in (30, 50, 70)], by_type=by_type(sealed, sm))
    from research import opus_cli
    res = dict(schema='specialist-v5/sealed-edge-v2', n=len(sealed), arms=out, opus_run=run,
               opus_calls_total=opus_cli.calls_used())
    (ART / 'sealed-results.json').write_text(json.dumps(res, indent=1))
    (OUT / 'v5-sealed-results.json').write_text(json.dumps(res, indent=1) + '\n')
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('edge', 'trainsample', 'select', 'final'))
    ap.add_argument('--no-opus', action='store_true')
    ap.add_argument('--bonus', type=float, default=3.0)
    ap.add_argument('--weak', type=float, default=0.25)
    ap.add_argument('--no-cascade', action='store_true')
    ap.add_argument('--n', type=int, default=200)
    a = ap.parse_args(argv)
    if a.phase == 'select':
        out = select_phase()
    elif a.phase == 'final':
        out = final_phase(not a.no_opus)
    elif a.phase == 'edge':
        out = edge_phase(a.bonus, a.weak, not a.no_cascade)
    else:
        rows = with_flags(cache_items(train_sample(a.n), f'train{a.n}'))
        fired = Counter(x for _, _, f in rows for v in f.values() for x in v)
        out = dict(items=len(rows), fired=fired, ablate=ablate(rows, a.bonus, a.weak, [()] + [(d,) for d in DETECTORS]))
    print(json.dumps(out, indent=1, default=str)[:12000])


if __name__ == '__main__':
    sys.exit(main())
