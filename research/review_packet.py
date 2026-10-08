"""Blind human label review packet (goal-family-corpus-v1 PLAN section 4); no model outputs, no inference."""
import argparse
from collections import Counter
import csv
import hashlib
import html
import json
from pathlib import Path
import random
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/goal-engine-2026-10-04'
PROBE = BASE / 'goal-interpreter-probe-v1'
OUT = BASE / 'human-review-v2-pt'  # v1 (EN+PT) was cancelled: reviewer could not follow the questions
SEED = 20261008
QUOTA = 15
LANGUAGES = ('en', 'pt')
GROUPS = ('supported', 'unknown', 'contrast', 'ambiguity')
PROVENANCES = ('authored', 'genuine_lcc')
COLUMNS = ['item_id', 'family_id', 'language', 'question', 'proposed_label', 'registry_definition',
           'verdict', 'corrected_label', 'note']
VERDICTS = ('agree', 'disagree', 'ambiguous', 'unclear')  # unclear: reviewer could not understand the question
KIND_LABELS = {'diagnosis_goal': 'UNKNOWN:diagnosis', 'derived_or_multifield_goal': 'UNKNOWN:derived',
               'broader_usefulness_goal': 'UNKNOWN:broader', 'out_of_registry': 'UNKNOWN:other'}
PASS_OVERALL, PASS_STRATUM = .95, .90
UNITS_PT = {'calls': 'chamadas', 'nanoseconds': 'nanossegundos', 'datagrams': 'datagramas',
            'bytes': 'bytes', 'paths': 'caminhos'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def pt_definition(definition):
    """Registry definitions are 'English. Portuguese.'; the Portuguese part starts at Conte/Leia/Esta."""
    cut = min((i for i in (definition.find(f'. {w} ') for w in ('Conte', 'Leia', 'Esta')) if i >= 0), default=-1)
    if cut < 0:
        raise ValueError(f'No Portuguese part in definition: {definition[:60]!r}')
    return definition[cut + 2:]


def label_id(label):
    return label.strip().split(' (', 1)[0]


def candidates(probe, pt_only=False):
    """Every exposed development question with its authored label; current data is authored only."""
    registry = json.loads((probe / 'registry.json').read_text())
    text = pt_definition if pt_only else (lambda d: d)
    unit = 'unidade' if pt_only else 'unit'
    units = UNITS_PT if pt_only else {}
    labels = {f['id']: (f"{f['id']} ({f['unit']})",
                        f"{unit}: {units.get(f['unit'], f['unit'])}. {text(f['definition'])}")
              for f in registry['fields']}
    labels.update({u['id']: (u['id'], text(u['definition'])) for u in registry['unsupported']})
    items = []
    for split in ('train', 'validation'):
        annotations = json.loads((probe / f'{split}-annotations.json').read_text())
        for q in json.loads((probe / f'{split}-inputs.json').read_text()):
            a = annotations[q['id']]
            label = a['target'] if a['kind'] == 'direct' else KIND_LABELS[a['kind']]
            # ponytail: contrast/ambiguity groups and genuine_lcc provenance do not exist in current data yet.
            group = 'supported' if a['kind'] == 'direct' else 'unknown'
            items.append(dict(query_id=q['id'], split=split, language=q['language'], question=q['question'],
                              label=label, proposed_label=labels[label][0], definition=labels[label][1],
                              family_id=text_sha('|'.join(a['wording_families']))[:12],
                              wording_families=a['wording_families'], source_ids=a['source_ids'],
                              stratum=f"{q['language']}|{group}|authored"))
    return items, set(labels)


def pick(pool, quota, rng):
    """Round-robin over labels (field/kind), distinct families first, seeded order."""
    by_label = {}
    for item in sorted(pool, key=lambda x: x['query_id']):
        by_label.setdefault(item['label'], []).append(item)
    queues = []
    for label in sorted(by_label):
        shuffled, seen = rng.sample(by_label[label], len(by_label[label])), set()
        first = [x for x in shuffled if not (x['family_id'] in seen or seen.add(x['family_id']))]
        queues.append(first + [x for x in shuffled if x not in first])
    chosen = []
    while len(chosen) < quota and any(queues):
        for q in queues:
            if q and len(chosen) < quota:
                chosen.append(q.pop(0))
    return chosen


def build(out=OUT, seed=SEED, probe=PROBE, force=False, languages=LANGUAGES, quota=QUOTA):
    out = Path(out)
    if not force and (out / 'packet.csv').exists():
        with open(out / 'packet.csv', newline='', encoding='utf-8-sig') as f:
            if any((r.get(c) or '').strip() for r in csv.DictReader(f) for c in ('verdict', 'corrected_label', 'note')):
                raise FileExistsError(f'{out / "packet.csv"} already holds reviewer work; pass --force to overwrite it')
    items, _ = candidates(probe, pt_only=tuple(languages) == ('pt',))
    strata, chosen = {}, []
    for lang in languages:
        for group in GROUPS:
            for prov in PROVENANCES:
                name = f'{lang}|{group}|{prov}'
                pool = [x for x in items if x['stratum'] == name]
                taken = pick(pool, quota, random.Random(f'{seed}:{name}'))
                chosen += taken
                strata[name] = dict(available=len(pool), sampled=len(taken), shortfall=quota - len(taken),
                                    by_label=dict(sorted(Counter(x['label'] for x in taken).items())))
    random.Random(f'{seed}:order').shuffle(chosen)
    out.mkdir(parents=True, exist_ok=True)
    key = {}
    with open(out / 'packet.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for n, x in enumerate(chosen, 1):
            item_id = f'HR-{n:03d}'
            writer.writerow(dict(item_id=item_id, family_id=x['family_id'], language=x['language'],
                                 question=x['question'], proposed_label=x['proposed_label'],
                                 registry_definition=x['definition'], verdict='', corrected_label='', note=''))
            key[item_id] = dict(stratum=x['stratum'], split=x['split'], query_id=x['query_id'],
                                source_ids=x['source_ids'], wording_families=x['wording_families'],
                                label=x['label'], question_sha256=text_sha(x['question']),
                                proposed_label=x['proposed_label'])
    (out / 'key.json').write_text(json.dumps(dict(seed=seed, items=key), indent=1, sort_keys=True) + '\n')
    sources = {str(p.relative_to(ROOT)): sha(p) for p in sorted(probe.glob('*-inputs.json'))
               + sorted(probe.glob('*-annotations.json')) + [probe / 'registry.json', Path(__file__)]
               if p.is_relative_to(ROOT)}
    present = {g for name, s in strata.items() if s['available'] for g in [name.split('|')[1]]}
    receipt = dict(schema='human-review-packet/0.1', plan='research/goal-engine-2026-10-04/goal-family-corpus-v1/PLAN.md#4',
                   seed=seed, languages=list(languages), quota_per_stratum=quota, target_items=quota * len(strata), items=len(chosen),
                   shortfall=sum(s['shortfall'] for s in strata.values()), strata=strata,
                   missing_groups=[g for g in GROUPS if g not in present],
                   missing_provenances=[p for p in PROVENANCES if not any(
                       s['available'] for name, s in strata.items() if name.endswith('|' + p))],
                   families=len({x['family_id'] for x in chosen}), sibling_frame_text='not present in current data',
                   sources=sources, packet_sha256=sha(out / 'packet.csv'), key_sha256=sha(out / 'key.json'),
                   reviewer='project owner (Lucas); not the corpus author (agents authored it)',
                   model_outputs_in_packet=False, split_in_packet=False, model_forwards=0, API_calls=0)
    (out / 'build-receipt.json').write_text(json.dumps(receipt, indent=1, sort_keys=True) + '\n')
    return receipt


def score(packet, key_path, probe=PROBE):
    key = json.loads(Path(key_path).read_text())['items']
    _, valid = candidates(probe)
    with open(packet, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f'Columns must be exactly {COLUMNS}')
        rows = list(reader)
    ids = [r['item_id'] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(key):
        raise ValueError('Packet must hold every key item exactly once')
    blank = [r['item_id'] for r in rows if not r['verdict'].strip()]
    if blank:
        raise ValueError(f'Packet not finished: {len(blank)}/{len(rows)} rows have no verdict '
                         f'(first: {blank[0]}). Fill verdict in {packet} per INSTRUCTIONS_PT.md.')
    strata = {}
    for r in rows:
        k, verdict = key[r['item_id']], r['verdict'].strip().lower()
        if text_sha(r['question']) != k['question_sha256'] or r['proposed_label'] != k['proposed_label']:
            raise ValueError(f"{r['item_id']}: question or proposed label was edited")
        if verdict not in VERDICTS:
            raise ValueError(f"{r['item_id']}: verdict must be one of {VERDICTS}, got {r['verdict']!r}")
        corrected = r['corrected_label'].strip()
        # ponytail: disagree without a correction still counts as non-agreement; reported as uncorrected
        if corrected and label_id(corrected) not in valid:
            raise ValueError(f"{r['item_id']}: unknown corrected_label {corrected!r}")
        s = strata.setdefault(k['stratum'], Counter())
        s[verdict] += 1
        s['uncorrected'] += verdict == 'disagree' and not corrected
        s['n'] += 1
    result = {name: dict(n=c['n'], **{v: c[v] for v in VERDICTS}, agreement=c['agree'] / c['n'])
              for name, c in sorted(strata.items())}
    n, agree = sum(c['n'] for c in strata.values()), sum(c['agree'] for c in strata.values())
    agreement = agree / n
    gate = agreement >= PASS_OVERALL and all(s['agreement'] >= PASS_STRATUM for s in result.values())
    complete = len(strata) == len(LANGUAGES) * len(GROUPS) * len(PROVENANCES)
    unclear = sum(c['unclear'] for c in strata.values())
    uncorrected = sum(c['uncorrected'] for c in strata.values())
    return dict(schema='human-review-score/0.1', n=n, agree=agree, agreement=agreement, unclear=unclear, uncorrected_disagreements=uncorrected,
                pass_rule=dict(overall=PASS_OVERALL, every_stratum=PASS_STRATUM), strata=result,
                gate_pass=gate, plan_complete=complete, adoption_ready=gate and complete,
                packet_sha256=sha(packet), key_sha256=sha(key_path),
                note='ambiguous and unclear count as non-agreement; unclear = reviewer could not understand the question; plan_complete is false while PLAN strata are missing')


PAGE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Revisão de rótulos</title>
<style>body{font:16px/1.5 system-ui;max-width:860px;margin:0 auto;padding:16px;background:#fafafa;color:#222}
.item{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:12px 0}
.done{border-left:6px solid #2a9d4a}.q{font-weight:600;font-size:17px}.def{color:#555;font-size:14px}
label{margin-right:14px;white-space:nowrap}select,input[type=text]{margin-top:6px;width:100%}
#bar{position:sticky;top:0;background:#fafafa;padding:8px 0;border-bottom:1px solid #ddd}
button{font-size:16px;padding:8px 16px}details{background:#fff;padding:8px 12px;border-radius:8px}</style>
</head><body><h1>Revisão de rótulos (60 perguntas)</h1>
<p>Para cada pergunta: ela pede exatamente o que a definição descreve? Clique numa opção.
Se discordar, escolha o rótulo certo. O progresso fica salvo neste navegador. No fim, clique
<b>Baixar resultado</b> e me avise.</p>
<details><summary><b>Glossário</b> (clique para abrir)</summary>__GLOSSARY__</details>
<div id="bar"><span id="count"></span> <button onclick="save()">Baixar resultado</button></div>
<div id="items"></div>
<script>
const ITEMS=__ITEMS__, LABELS=__LABELS__, KEY='review-v2-pt';
const V=[['agree','Concordo'],['disagree','Discordo'],['ambiguous','Ambígua'],['unclear','Não entendi']];
let st={};try{st=JSON.parse(localStorage.getItem(KEY))||{}}catch(e){}
function persist(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}render()}
function esc(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function render(){let n=0;document.getElementById('items').innerHTML=ITEMS.map((it,i)=>{
 const s=st[it.item_id]||{};if(s.verdict&&(s.verdict!=='disagree'||s.corrected))n++;
 return `<div class="item ${s.verdict?'done':''}"><div>${i+1}. <span class="q">${esc(it.question)}</span></div>
 <div>Rótulo proposto: <b>${esc(it.proposed_label)}</b></div><div class="def">${esc(it.registry_definition)}</div>
 <div>${V.map(([v,t])=>`<label><input type="radio" name="${it.item_id}" ${s.verdict===v?'checked':''}
 onchange="set('${it.item_id}','verdict','${v}')"> ${t}</label>`).join('')}</div>
 ${s.verdict==='disagree'?`<select onchange="set('${it.item_id}','corrected',this.value)"><option value="">Rótulo correto…</option>
 ${LABELS.map(l=>`<option ${s.corrected===l?'selected':''}>${l}</option>`).join('')}</select>`:''}
 <input type="text" placeholder="Nota (opcional)" value="${esc(s.note||'')}" onchange="set('${it.item_id}','note',this.value)">
 </div>`}).join('');document.getElementById('count').textContent=`${n}/${ITEMS.length} respondidas`}
function set(id,k,v){st[id]=Object.assign(st[id]||{},{[k]:v});if(k==='verdict'&&v!=='disagree')delete st[id].corrected;persist()}
function save(){const q=s=>'"'+String(s||'').replace(/"/g,'""')+'"';
 const lines=['item_id,verdict,corrected_label,note'].concat(ITEMS.map(it=>{const s=st[it.item_id]||{};
 return [it.item_id,s.verdict,s.corrected,s.note].map(q).join(',')}));
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\\n')],{type:'text/csv'}));
 a.download='review-result.csv';a.click()}
render();
</script></body></html>
"""


def md_inline(text):
    text = html.escape(text)
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text))


def page(packet, glossary_md, probe=PROBE):
    """Single self-contained HTML form over the packet; answers download as review-result.csv."""
    with open(packet, newline='', encoding='utf-8-sig') as f:
        items = [{k: r[k] for k in ('item_id', 'question', 'proposed_label', 'registry_definition')}
                 for r in csv.DictReader(f)]
    glossary = '<ul>' + ''.join(f'<li>{md_inline(line.strip()[2:])}</li>'
                                 for line in Path(glossary_md).read_text().split('## Glossário', 1)[1]
                                 .split('## Limites', 1)[0].splitlines() if line.strip().startswith('- ')) + '</ul>'
    out = Path(packet).with_name('revisao.html')
    out.write_text(PAGE.replace('__GLOSSARY__', glossary)
                   .replace('__ITEMS__', json.dumps(items, ensure_ascii=False).replace('</', '<\\/'))
                   .replace('__LABELS__', json.dumps(sorted(candidates(probe)[1]))))
    return out


def import_result(result_csv, packet):
    """Merge a downloaded review-result.csv into packet.csv (only verdict/corrected_label/note change)."""
    with open(result_csv, newline='', encoding='utf-8-sig') as f:
        answers = {r['item_id']: r for r in csv.DictReader(f)}
    with open(packet, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    if set(answers) != {r['item_id'] for r in rows}:
        raise ValueError('Result file does not match this packet')
    for r in rows:
        for col in ('verdict', 'corrected_label', 'note'):
            r[col] = answers[r['item_id']][col]
    with open(packet, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def review(packet, probe=PROBE, ask=input, say=print):
    """Interactive terminal review: one blank row at a time, saved after every answer (resumable)."""
    packet = Path(packet)
    with open(packet, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    labels = sorted(candidates(probe)[1])
    todo = [r for r in rows if not r['verdict'].strip()]
    say(f'{len(rows) - len(todo)}/{len(rows)} já revisadas. a=concordo d=discordo ?=ambíguo '
        'n=não entendi a pergunta s=pular q=sair')
    for i, r in enumerate(todo, 1):
        say(f"\n[{i}/{len(todo)}] {r['item_id']} ({r['language']})\nPergunta: {r['question']}\n"
            f"Rótulo proposto: {r['proposed_label']}\nDefinição: {r['registry_definition']}")
        answer = ask('Veredito [a/d/?/n/s/q]: ').strip().lower()
        if answer == 'q':
            break
        if answer not in ('a', 'd', '?', 'n'):
            continue
        r['verdict'] = {'a': 'agree', 'd': 'disagree', '?': 'ambiguous', 'n': 'unclear'}[answer]
        if answer == 'd':
            say('\n'.join(f'  {n}. {label}' for n, label in enumerate(labels, 1)))
            while not r['corrected_label']:
                pick = ask('Número do rótulo correto: ').strip()
                if pick.isdigit() and 1 <= int(pick) <= len(labels):
                    r['corrected_label'] = labels[int(pick) - 1]
        r['note'] = ask('Nota (opcional, Enter pula): ').strip() or r['note']
        with open(packet, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    left = sum(not r['verdict'].strip() for r in rows)
    say(f'\nFaltam {left}. ' + ('Rode: python3 -m research.review_packet score' if not left
                               else 'Rode review de novo para continuar.'))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build')
    b.add_argument('--out', default=OUT)
    b.add_argument('--seed', type=int, default=SEED)
    b.add_argument('--languages', nargs='+', default=['pt'])
    b.add_argument('--quota', type=int, default=30)
    b.add_argument('--force', action='store_true', help='overwrite a packet that already holds reviewer work')
    s = sub.add_parser('score')
    s.add_argument('--packet', default=OUT / 'packet.csv')
    s.add_argument('--key', default=OUT / 'key.json')
    s.add_argument('--result', default=OUT / 'score.json')
    r = sub.add_parser('review', help='interactive terminal review of blank rows')
    r.add_argument('--packet', default=OUT / 'packet.csv')
    h = sub.add_parser('html', help='write revisao.html: one page, click answers, download result')
    h.add_argument('--packet', default=OUT / 'packet.csv')
    i = sub.add_parser('import', help='merge a downloaded review-result.csv into the packet')
    i.add_argument('result')
    i.add_argument('--packet', default=OUT / 'packet.csv')
    args = parser.parse_args()
    if args.command == 'html':
        print(page(args.packet, Path(args.packet).with_name('INSTRUCTIONS_PT.md')))
    elif args.command == 'import':
        import_result(args.result, args.packet)
        print(f'Imported into {args.packet}; now run: python3 -m research.review_packet score')
    elif args.command == 'review':
        review(args.packet)
    elif args.command == 'build':
        print(json.dumps(build(Path(args.out), args.seed, force=args.force, languages=tuple(args.languages), quota=args.quota), indent=1, sort_keys=True))
    else:
        result = score(args.packet, args.key)
        Path(args.result).write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
        print(json.dumps({k: result[k] for k in ('n', 'agreement', 'unclear', 'gate_pass', 'plan_complete')}, indent=1))


if __name__ == '__main__':
    main()
