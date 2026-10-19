"""POST HOC (not pre-registered) stress checks for when2, written after seeing when2-results.json.

1. P5 regrowth proxy: the agent rebuilds context right after a handoff -> run P5 / P1+P5 with H = 50k and 100k.
2. Paired differences between combinations that the frozen script only compares to P1.
Aggregates only. Same data rules as when2.py.

    PYTHONPATH=.../lcc-main/src:$PWD ~/LCC/.venv/bin/python -m research.when2_posthoc
"""
import json
from pathlib import Path

import numpy as np

from research import when2 as w2
from research import when_to_compact as w


def main(root=str(Path.home() / '.claude' / 'projects'), out=w2.OUT):
    traces = [w.annotate(t) for t in w.load(root)]
    ends = w2.end_ok(traces)
    main_ = [t for t in traces if not t['subagent'] and any(not r['dup'] for r in t['requests'])]
    idx = w2._idx(len(main_))

    def sav(name, **kw):
        return [w2.simulate2(t, w2.POLICIES[name], ends, **kw)['saving'] for t in main_]

    def summ(xs):
        return dict(mean=float(np.mean(xs)), ci95=w2.ci(idx, xs))

    doc = dict(schema='when-to-compact/part2-posthoc', note='POST HOC, not pre-registered', sessions=len(main_),
               regrowth={}, paired={})
    for h in (50000, 100000):
        for name in ('P5', 'P1+P5'):
            doc['regrowth'][f'{name}_H{h // 1000}k'] = summ(sav(name, h=h))
            doc['regrowth'][f'{name}_H{h // 1000}k_native'] = summ(sav(name, h=h, gen='native'))
    base = {n: sav(n) for n in ('P1+P5', 'P1+P4_K1+P5', 'P5', 'P4_K1')}
    doc['paired']['P1+P4_K1+P5 - P1+P5'] = summ([a - b for a, b in zip(base['P1+P4_K1+P5'], base['P1+P5'])])
    doc['paired']['P1+P5 - P5'] = summ([a - b for a, b in zip(base['P1+P5'], base['P5'])])
    (Path(out) / 'when2-posthoc.json').write_text(json.dumps(doc, indent=1) + '\n')
    print(json.dumps(doc, indent=1))


if __name__ == '__main__':
    main()
