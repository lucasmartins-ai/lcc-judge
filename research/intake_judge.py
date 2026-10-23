"""Intake judge v1 inference: request category of one owner prompt, pure Python (stdlib only).

Features: hashed word 1-2-grams and char 2-5-grams (word-boundary padded), binary, L2-normalised.
Model: multinomial logistic regression, weights stored as base64 float16 so LCC can vendor one JSON file.

    j = Judge.load(path); j.predict(text) -> (category, probability)
"""
from __future__ import annotations

import base64
import json
import math
import re
import struct
import unicodedata
import zlib

BUCKETS = 1 << 15
_WORD = re.compile(r'\w+')


def features(text: str, kinds: str = 'char+word') -> dict[int, float]:
    """{bucket: value}; kinds is 'char' or 'char+word'."""
    t = unicodedata.normalize('NFKC', text or '').lower()
    words = _WORD.findall(t)
    grams = set()
    for w in words:
        p = f' {w} '
        for n in range(2, 6):
            grams.update('c' + p[i:i + n] for i in range(len(p) - n + 1))
    if kinds == 'char+word':
        grams.update('w' + w for w in words)
        grams.update('b' + a + ' ' + b for a, b in zip(words, words[1:]))
    if not grams:
        grams = {'<empty>'}
    buckets = {zlib.crc32(g.encode()) % BUCKETS for g in grams}
    v = 1 / math.sqrt(len(buckets))
    return dict.fromkeys(buckets, v)


class Judge:
    def __init__(self, labels, kinds, weights, bias):
        self.labels, self.kinds, self.w, self.b = labels, kinds, weights, bias

    @classmethod
    def load(cls, path):
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
        k = len(d['labels'])
        raw = base64.b64decode(d['weights_f16'])
        flat = struct.unpack(f'<{BUCKETS * k}e', raw)  # row-major [bucket][class]
        return cls(d['labels'], d['kinds'], flat, d['bias'])

    def proba(self, text: str) -> list[float]:
        k = len(self.labels)
        z = list(self.b)
        for idx, v in features(text, self.kinds).items():
            base = idx * k
            for c in range(k):
                z[c] += self.w[base + c] * v
        m = max(z)
        e = [math.exp(x - m) for x in z]
        s = sum(e)
        return [x / s for x in e]

    def predict(self, text: str) -> tuple[str, float]:
        p = self.proba(text)
        i = max(range(len(p)), key=p.__getitem__)
        return self.labels[i], p[i]


def bench(model_path, texts_path):
    """Fresh-process cost: load once, predict each text; -> latency ms list, load ms, peak RSS MB."""
    import resource
    import sys
    import time
    t0 = time.perf_counter()
    j = Judge.load(model_path)
    load_ms = (time.perf_counter() - t0) * 1000
    with open(texts_path, encoding='utf-8') as fh:
        texts = json.load(fh)
    lat = []
    for t in texts:
        t0 = time.perf_counter()
        j.predict(t)
        lat.append((time.perf_counter() - t0) * 1000)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mb = rss / (1 << 20) if sys.platform == 'darwin' else rss / 1024  # bytes on macOS, KiB on Linux
    return {'latency_ms': lat, 'load_ms': load_ms, 'peak_rss_mb': rss_mb}


def export(path, labels, kinds, weights, bias, meta=None):
    """weights: [BUCKETS][len(labels)] array-like (numpy ok); writes the vendorable JSON."""
    import numpy as np
    w = np.asarray(weights, dtype='<f2')
    assert w.shape == (BUCKETS, len(labels))
    d = {'format': 'lcc-intake-judge/1', 'labels': list(labels), 'kinds': kinds, 'buckets': BUCKETS,
         'bias': [round(float(x), 6) for x in bias],
         'weights_f16': base64.b64encode(w.tobytes()).decode(), 'meta': meta or {}}
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(d, fh)


if __name__ == '__main__':
    import sys
    print(json.dumps(bench(sys.argv[1], sys.argv[2])))
