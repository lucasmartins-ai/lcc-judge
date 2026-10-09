"""Owner confirmation of the genuine-request taxonomy (taxonomy-v1). Data lives in ~/.lcc only, never in the repo."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import random

DATA = Path.home() / '.lcc/request-log/taxonomy-v1'
SEED = 20261009
PER_CATEGORY = 4
CONFIDENCE_ORDER = {'low': 0, 'medium': 1, 'high': 2}
VERDICTS = ('right', 'wrong', 'unsure')


def load(data=DATA, version='v1'):
    tax = json.loads((data / ('taxonomy.json' if version == 'v1' else f'taxonomy-{version}.json')).read_text())
    goals = {r['id']: r for f in sorted(data.glob('chunk-*.jsonl')) for r in map(json.loads, f.open())}
    pattern = 'labels-[0-9]*.jsonl' if version == 'v1' else f'labels-{version}-*.jsonl'
    labels = {r['id']: r for f in sorted(data.glob(pattern)) for r in map(json.loads, f.open())}
    return tax, goals, labels


def pick(labels, seed=SEED, per_category=PER_CATEGORY, only=None, exclude=()):
    """Per label: lowest confidence first, ties broken by a seeded shuffle; then shuffle the whole page.
    only: keep a single confidence level; exclude: ids already reviewed."""
    rng, by_label = random.Random(seed), {}
    for item in sorted(labels.values(), key=lambda x: x['id']):
        if item['id'] in exclude or (only and item['confidence'] != only):
            continue
        by_label.setdefault(item['label'], []).append(item)
    chosen = []
    for label in sorted(by_label):
        pool = rng.sample(by_label[label], len(by_label[label]))
        chosen += sorted(pool, key=lambda x: CONFIDENCE_ORDER.get(x['confidence'], 0))[:per_category]
    rng.shuffle(chosen)
    return chosen


def page(data=DATA, seed=SEED, version='v1', per_category=PER_CATEGORY, only=None, exclude=()):
    tax, goals, labels = load(data, version)
    cats = [dict(id=c['id'], name=c['name_pt'], definition=c['definition_pt']) for c in tax['categories']]
    cats.append(dict(id='UNKNOWN', name='Não dá para saber',
                     definition='Curto ou vago demais para saber de que contexto o agente precisa.'))
    names = {c['id']: c for c in cats}
    items = [dict(id=x['id'], goal=goals[x['id']]['goal'][:600], label=x['label']) for x in pick(labels, seed, per_category, only, exclude)]
    glossary = ''.join(f"<li><b>{html.escape(c['name'])}</b>: {html.escape(c['definition'])}</li>" for c in cats)
    body = PAGE.replace('__GLOSSARY__', glossary).replace('__N__', str(len(items)))
    body = body.replace('__ITEMS__', json.dumps(items, ensure_ascii=False).replace('</', '<\\/'))
    body = body.replace('taxonomy-v1-review', f'taxonomy-{version}-review').replace('__CATS__', json.dumps(names, ensure_ascii=False).replace('</', '<\\/'))
    out = data / ('confirmar.html' if version == 'v1' else f'confirmar-{version}.html')
    out.write_text(body)
    return out


def score(result_csv, data=DATA, version='v1'):
    _, _, labels = load(data, version)
    with open(result_csv, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    per, fixes = {}, Counter()
    for r in rows:
        if r['verdict'] not in VERDICTS or r['id'] not in labels:
            raise ValueError(f"bad row {r['id']!r}: verdict {r['verdict']!r}")
        proposed = labels[r['id']]['label']
        per.setdefault(proposed, Counter())[r['verdict']] += 1
        if r['verdict'] == 'wrong' and r['corrected']:
            fixes[f"{proposed} -> {r['corrected']}"] += 1
    judged = sum(c['right'] + c['wrong'] for c in per.values())
    right = sum(c['right'] for c in per.values())
    return dict(schema='request-taxonomy-review/0.1', n=len(rows), judged=judged, right=right,
                agreement=right / judged if judged else None,
                unsure=sum(c['unsure'] for c in per.values()),
                per_category={k: dict(v) for k, v in sorted(per.items())}, corrections=dict(fixes.most_common()))


PAGE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Confirmar categorias</title>
<style>body{font:16px/1.5 system-ui;max-width:860px;margin:0 auto;padding:16px;background:#fafafa;color:#222}
.item{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:12px 0}
.done{border-left:6px solid #2a9d4a}.goal{white-space:pre-wrap;background:#f3f3f3;padding:8px;border-radius:6px}
.def{color:#555;font-size:14px}label{margin-right:14px;white-space:nowrap}select{margin-top:6px;width:100%}
#bar{position:sticky;top:0;background:#fafafa;padding:8px 0;border-bottom:1px solid #ddd}
button{font-size:16px;padding:8px 16px}details{background:#fff;padding:8px 12px;border-radius:8px}
@media (prefers-color-scheme:dark){body,#bar{background:#161616;color:#eee}.item,details{background:#222;border-color:#333}
.goal{background:#2b2b2b}.def{color:#aaa}}</style></head><body>
<h1>Seus pedidos: a categoria está certa?</h1>
<p>São __N__ pedidos seus (com dados sensíveis trocados por &lt;MARCADORES&gt;). Para cada um, veja a categoria
proposta e marque <b>Certo</b>, <b>Errado</b> (e escolha a certa) ou <b>Não sei</b>. Pense: "quando eu escrevi isso,
era esse tipo de pedido?". O progresso fica salvo no navegador. No fim, clique <b>Baixar resultado</b>.</p>
<details><summary><b>As categorias</b> (clique para abrir)</summary><ul>__GLOSSARY__</ul></details>
<div id="bar"><span id="count"></span> <button onclick="save()">Baixar resultado</button></div>
<div id="items"></div>
<script>
const ITEMS=__ITEMS__, CATS=__CATS__, KEY='taxonomy-v1-review';
const V=[['right','Certo'],['wrong','Errado'],['unsure','Não sei']];
let st={};try{st=JSON.parse(localStorage.getItem(KEY))||{}}catch(e){}
function persist(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}render()}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function render(){let n=0;document.getElementById('items').innerHTML=ITEMS.map((it,i)=>{
 const s=st[it.id]||{},c=CATS[it.label];if(s.verdict&&(s.verdict!=='wrong'||s.corrected))n++;
 return `<div class="item ${s.verdict?'done':''}"><div>${i+1}.</div><div class="goal">${esc(it.goal)}</div>
 <div>Categoria proposta: <b>${esc(c.name)}</b></div><div class="def">${esc(c.definition)}</div>
 <div>${V.map(([v,t])=>`<label><input type="radio" name="${it.id}" ${s.verdict===v?'checked':''}
 onchange="set('${it.id}','verdict','${v}')"> ${t}</label>`).join('')}</div>
 ${s.verdict==='wrong'?`<select onchange="set('${it.id}','corrected',this.value)"><option value="">Categoria certa…</option>
 ${Object.values(CATS).filter(x=>x.id!==it.label).map(x=>`<option value="${x.id}" ${s.corrected===x.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select>`:''}
 </div>`}).join('');document.getElementById('count').textContent=`${n}/${ITEMS.length} respondidos`}
function set(id,k,v){st[id]=Object.assign(st[id]||{},{[k]:v});if(k==='verdict'&&v!=='wrong')delete st[id].corrected;persist()}
function save(){const q=s=>'"'+String(s||'').replace(/"/g,'""')+'"';
 const lines=['id,verdict,corrected'].concat(ITEMS.map(it=>{const s=st[it.id]||{};return [it.id,s.verdict,s.corrected].map(q).join(',')}));
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\\n')],{type:'text/csv'}));
 a.download='taxonomy-review-result.csv';a.click()}
render();
</script></body></html>
"""


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('page')
    p.add_argument('--version', default='v1')
    p.add_argument('--per-category', type=int, default=PER_CATEGORY)
    p.add_argument('--only', choices=sorted(CONFIDENCE_ORDER), help='keep one labeler confidence level')
    p.add_argument('--exclude-reviewed', action='store_true', help='skip ids in owner-judgments.json')
    s = sub.add_parser('score')
    s.add_argument('result')
    s.add_argument('--version', default='v1')
    args = parser.parse_args()
    if args.command == 'page':
        reviewed = json.loads((DATA / 'owner-judgments.json').read_text()) if args.exclude_reviewed else []
        print(page(version=args.version, per_category=args.per_category, only=args.only,
                   exclude={r['id'] for r in reviewed}))
    else:
        result = score(args.result, version=args.version)
        (DATA / ('review-score.json' if args.version == 'v1' else f'review-score-{args.version}.json')).write_text(json.dumps(result, indent=1, ensure_ascii=False) + '\n')
        print(json.dumps({k: result[k] for k in ('n', 'judged', 'right', 'agreement', 'unsure')}, indent=1))


if __name__ == '__main__':
    main()
