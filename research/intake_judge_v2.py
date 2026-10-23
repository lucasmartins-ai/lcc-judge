"""Intake judge v2 inference (protocol: research/goal-engine-2026-10-04/intake-judge-v2/PROTOCOL.md).

One feature vector per (prompt, previous agent turn), in index ranges:
  [0, P)            prompt: v1 features (hashed char 2-5-grams + word 1-2-grams), L2-normalised
  [P, P + Q)        previous turn: same featuriser, own hash range, L2-normalised on its own   (family B, H)
  [P + Q, + 129)    dense: 64-d mean static embedding of the prompt, 64-d of the previous turn,
                    has-previous-turn flag                                                       (family E, H)
Families: A = prompt only, B = prompt + previous turn, E = dense only, H = B + dense.
A/B are stdlib only; E/H need numpy and `tokenizers` plus the shrunk embedding file.
"""
from __future__ import annotations

import base64
import json
import math
import struct

from research.intake_judge import features as v1_features

P = 1 << 15
Q = 1 << 14
DENSE = 129
WIDTH = P + Q + DENSE
FAMILIES = ('A', 'B', 'E', 'H')


class Embedder:
    """Shrunk static embeddings: kept token id -> 64-d float16 row (PCA of potion-multilingual-128M)."""

    def __init__(self, tokenizer_path, emb_path):
        import numpy as np
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(str(tokenizer_path))
        d = np.load(emb_path)
        self.index = {int(t): n for n, t in enumerate(d['ids'])}
        self.rows = d['rows'].astype(np.float32)

    def embed(self, text):
        import numpy as np
        if not text:
            return np.zeros(64, dtype=np.float32)
        ids = [self.index[t] for t in self.tok.encode(text, add_special_tokens=False).ids if t in self.index]
        if not ids:
            return np.zeros(64, dtype=np.float32)
        v = self.rows[ids].mean(0)
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v


def vector(prompt, prev, family, embedder=None):
    """{index: value} for one request."""
    out = {}
    if family in ('A', 'B', 'H'):
        out.update(v1_features(prompt, 'char+word'))
    if family in ('B', 'H') and prev:
        block = {P + idx % Q for idx in v1_features(prev, 'char+word')}  # own index range, binary
        v = 1 / math.sqrt(len(block))
        out.update(dict.fromkeys(block, v))
    if family in ('E', 'H'):
        base = P + Q
        for d, v in enumerate(embedder.embed(prompt)):
            out[base + d] = float(v)
        for d, v in enumerate(embedder.embed(prev or '')):
            out[base + 64 + d] = float(v)
        out[base + 128] = 1.0 if prev else 0.0
    return out


class Judge:
    def __init__(self, data, embedder=None):
        self.labels, self.family, self.bias = data['labels'], data['family'], data['bias']
        k = len(self.labels)
        rows = data['rows']
        flat = struct.unpack(f'<{len(rows) * k}e', base64.b64decode(data['weights_f16']))
        self.w = {r: flat[n * k:(n + 1) * k] for n, r in enumerate(rows)}  # only rows the family uses
        self.embedder = embedder

    @classmethod
    def load(cls, path, embedder=None):
        with open(path, encoding='utf-8') as fh:
            return cls(json.load(fh), embedder)

    def proba(self, prompt, prev=None):
        z = list(self.bias)
        for idx, v in vector(prompt, prev, self.family, self.embedder).items():
            w = self.w.get(idx)
            if w is not None:
                for c in range(len(z)):
                    z[c] += w[c] * v
        m = max(z)
        e = [math.exp(x - m) for x in z]
        s = sum(e)
        return [x / s for x in e]

    def predict(self, prompt, prev=None):
        p = self.proba(prompt, prev)
        i = max(range(len(p)), key=p.__getitem__)
        return self.labels[i], p[i]


def family_rows(family):
    rows = []
    if family in ('A', 'B', 'H'):
        rows += range(P)
    if family in ('B', 'H'):
        rows += range(P, P + Q)
    if family in ('E', 'H'):
        rows += range(P + Q, WIDTH)
    return rows


def export(path, labels, family, W, b, meta=None):
    """W: [WIDTH][k]; stores only the family's rows as base64 float16."""
    import numpy as np
    rows = family_rows(family)
    w = np.asarray(W, dtype='<f2')[rows]
    d = {'format': 'lcc-intake-judge/2', 'labels': list(labels), 'family': family, 'rows': rows,
         'bias': [round(float(x), 6) for x in b], 'weights_f16': base64.b64encode(w.tobytes()).decode(),
         'meta': meta or {}}
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(d, fh)


def bench(model_path, texts_path, tokenizer_path=None, emb_path=None):
    """Fresh-process cost: load once, predict each (prompt, prev); -> latencies, load ms, peak RSS MB."""
    import resource
    import sys
    import time
    t0 = time.perf_counter()
    emb = Embedder(tokenizer_path, emb_path) if emb_path else None
    j = Judge.load(model_path, emb)
    load_ms = (time.perf_counter() - t0) * 1000
    with open(texts_path, encoding='utf-8') as fh:
        items = json.load(fh)
    lat = []
    for prompt, prev in items:
        t0 = time.perf_counter()
        j.predict(prompt, prev)
        lat.append((time.perf_counter() - t0) * 1000)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mb = rss / (1 << 20) if sys.platform == 'darwin' else rss / 1024
    return {'latency_ms': lat, 'load_ms': load_ms, 'peak_rss_mb': rss_mb}


if __name__ == '__main__':
    import sys
    print(json.dumps(bench(*sys.argv[1:])))
