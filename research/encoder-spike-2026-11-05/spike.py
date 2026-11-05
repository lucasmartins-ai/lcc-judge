"""Cost spike for an LCC-only block encoder: measurement only, no training.

Reads block texts from ~/.lcc (private) and writes counts and timings only, to out/<mode>.json.
Criteria and definitions: RESULTS.md (agreed with the owner before the run).

  PY=~/lcc/.venv/bin/python
  $PY -I research/encoder-spike-2026-11-05/spike.py stats        # tokenizer only, picks the items
  $PY -I research/encoder-spike-2026-11-05/spike.py fp32         # then int8, int8-pruned
  zsh research/encoder-spike-2026-11-05/run_idle.sh                # spike 2: ONNX + PyTorch when idle
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import resource
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ITEMS = Path.home() / '.lcc/bench/next-action-v2/items'
TEXTS = Path.home() / '.lcc/bench/next-action-v1/texts'
PRIVATE = Path.home() / '.lcc/bench/encoder-spike-2026-11-05'
MODEL = Path.home() / (
    '.cache/huggingface/hub/models--ibm-granite--granite-embedding-97m-multilingual-r2/'
    'snapshots/835ad14087e140460703cf0fae09f97d469d65c2'
)
OUT = Path(__file__).with_name('out')
MAX_LEN = 2048
BATCH_TOKENS = 8192  # padded tokens per forward in a cold encode
LENGTHS = (54, 443, 1243, 2048)  # per-block latency points (p50, p90, p99, window)
SESSION_SIZES = (435, 1573, 9882)  # session-layer vectors: p50, p90, p99 blocks per item


def pct(xs, q):
    """Nearest-rank percentile."""
    s = sorted(xs)
    return s[max(0, math.ceil(q / 100 * len(s)) - 1)]


def last_turn(blocks):
    """Blocks after the newest user prompt: what a warm pass encodes besides the new prompt."""
    for k in range(len(blocks) - 1, -1, -1):
        if blocks[k]['role'] == 'user' and blocks[k]['kind'] == 'text':
            return blocks[k + 1 :]
    return blocks


def load():
    return [json.loads(p.read_text()) for p in sorted(ITEMS.glob('*.json'))]


def texts(store, _cache={}):  # noqa: B006 - ponytail: one store cached, callers group by store
    if store not in _cache:
        _cache.clear()
        _cache[store] = json.loads((TEXTS / f'{store}.json').read_text())
    return _cache[store]


def loadavg():
    return [round(x, 1) for x in os.getloadavg()]


def peak_rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20  # bytes on macOS


# --- stats: tokenizer only ------------------------------------------------------------------------
def stats():
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL)
    items = load()
    items.sort(key=lambda it: it['text_store'])
    seen, lens, ratio, missing = {}, [], [], 0
    vocab_fit, held_ids = set(), []
    # 80/20 split by store: is the vocabulary seen in 80% of sessions enough for the rest?
    held = {
        st for st in {it['text_store'] for it in items}
        if int(hashlib.sha256(st.encode()).hexdigest(), 16) % 5 == 0
    }
    for it in items:
        tx = texts(it['text_store'])
        for b in it['blocks']:
            key = (it['text_store'], b['id'])
            if key in seen:
                continue
            t = tx.get(b['id'])
            if t is None:
                missing += 1
                seen[key] = None
                continue
            ids = tok(t, add_special_tokens=False)['input_ids']
            seen[key] = len(ids)
            lens.append(len(ids))
            if b['tokens']:
                ratio.append(len(ids) / b['tokens'])
            if it['text_store'] in held:
                held_ids.append(ids)
            else:
                vocab_fit.update(ids)
    # OOV against the finished fit vocabulary (held and fit stores interleave in the loop).
    held_tokens = sum(map(len, held_ids))
    held_oov = sum(1 for ids in held_ids for i in ids if i not in vocab_fit)
    vocab_all = vocab_fit.union(*held_ids)
    for it in items:  # granite length per block, item-level aggregates
        st = it['text_store']
        it['_g'] = [seen.get((st, b['id'])) or 0 for b in it['blocks']]
        lt = last_turn(it['blocks'])
        it['_warm_tokens'] = sum(it['_g'][len(it['blocks']) - len(lt) :])
        it['_warm_blocks'] = len(lt)
    nb = [len(it['blocks']) for it in items]
    pick = {}
    # Amendment 1: cold items by Granite tokens, not block count (see RESULTS.md).
    for name, key, q in (
        ('cold_p50', lambda it: sum(it['_g']), 50),
        ('cold_p90', lambda it: sum(it['_g']), 90),
        ('cold_p50_by_blocks', lambda it: len(it['blocks']), 50),  # record only, not timed
        ('warm_p50', lambda it: it['_warm_tokens'], 50),
        ('warm_p90', lambda it: it['_warm_tokens'], 90),
    ):
        target = pct([key(it) for it in items], q)
        it = min(items, key=lambda it: (abs(key(it) - target), it['item_id']))
        pick[name] = {
            'item_id': it['item_id'],
            'blocks': len(it['blocks']),
            'granite_tokens': sum(it['_g']),
            'warm_blocks': it['_warm_blocks'],
            'warm_tokens': it['_warm_tokens'],
        }
    special = [tok.cls_token_id, tok.sep_token_id, tok.pad_token_id, tok.mask_token_id]
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    (PRIVATE / 'vocab.json').write_text(json.dumps(sorted(vocab_all | set(special))))
    out = {
        'items': len(items),
        'stores': len({it['text_store'] for it in items}),
        'unique_blocks': len(seen),
        'blocks_without_text': missing,
        'granite_tokens_per_block': {q: pct(lens, q) for q in (50, 90, 99, 100)},
        'blocks_over_2048': sum(1 for n in lens if n > MAX_LEN),
        'granite_over_item_tokens_ratio_p50': round(pct(ratio, 50), 3),
        'blocks_per_item': {q: pct(nb, q) for q in (50, 90, 99)},
        'granite_tokens_per_item': {q: pct([sum(it['_g']) for it in items], q) for q in (50, 90, 99)},
        'warm_blocks_per_item': {q: pct([it['_warm_blocks'] for it in items], q) for q in (50, 90, 99)},
        'warm_tokens_per_item': {q: pct([it['_warm_tokens'] for it in items], q) for q in (50, 90, 99)},
        'vocab_used_all': len(vocab_all),
        'vocab_fit_80pct_stores': len(vocab_fit),
        'held_20pct_stores': len(held),
        'held_oov_token_rate': round(held_oov / held_tokens, 5) if held_tokens else None,
        'picked': pick,
        'loadavg': loadavg(),
    }
    return out


# --- model modes ------------------------------------------------------------------------------------
def timed(fn, reps, warm=1):
    for _ in range(warm):
        fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return statistics.median(ts)


class RssPeak:
    """Peak current RSS per phase, sampled with ps every 0.2 s (ru_maxrss cannot be reset)."""

    def __init__(self):
        self.peak = 0.0
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        cmd = ['ps', '-o', 'rss=', '-p', str(os.getpid())]
        while True:
            kb = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip()
            self.peak = max(self.peak, int(kb or 0) / 1024)
            time.sleep(0.2)

    def take(self):
        peak, self.peak = self.peak, 0.0
        return round(peak, 1)


def batches(lengths, budget=BATCH_TOKENS):
    """Index batches in ascending length; each pads to at most ``budget`` tokens (or holds one)."""
    out, cur = [], []
    for j in sorted(range(len(lengths)), key=lengths.__getitem__):
        if cur and (len(cur) + 1) * lengths[j] > budget:  # lengths[j] is the batch's new max
            out.append(cur)
            cur = []
        cur.append(j)
    return out + [cur] if cur else out


def measure(out, sampler, load_peak, encode, ids_of, session, cls, sep, keep=None):
    """The same phases for every backend: block latency, cold and warm encodes, session layer."""
    out['loadavg_start'] = loadavg()
    rnd = random.Random(0)
    lat = {}
    for n in LENGTHS:
        body = [rnd.randrange(1000, 170000) for _ in range(n - 2)]
        if keep is not None:  # stay inside the pruned table's real rows
            body = [keep[i % len(keep)] for i in body]
        lst = [[cls, *body, sep]]
        lat[n] = round(1000 * timed(lambda lst=lst: encode(lst), reps=7 if n < 2048 else 5), 1)
    out['block_latency_ms'] = lat
    out['loadavg_after_latency'] = loadavg()
    rss = {'load': load_peak, 'latency': sampler.take()}

    picked = json.loads((OUT / 'stats.json').read_text())['picked']
    by_id = {p['item_id']: name for name, p in picked.items()}
    items = {it['item_id']: it for it in load() if it['item_id'] in by_id}
    for name in ('cold_p50', 'cold_p90', 'warm_p50', 'warm_p90'):
        it = items[picked[name]['item_id']]
        tx = texts(it['text_store'])
        blocks = it['blocks'] if name.startswith('cold') else last_turn(it['blocks'])
        lists = [ids_of(tx.get(b['id']) or '') for b in blocks]
        if name.startswith('warm'):
            lists.append(ids_of(it['goal']))  # the new prompt
        reps = 1 if name.startswith('cold') else 3
        sec = timed(lambda lists=lists: encode(lists), reps=reps, warm=0 if reps == 1 else 1)
        out[name] = {'blocks': len(lists), 'tokens': sum(map(len, lists)), 'encode_s': round(sec, 2)}
        out[f'loadavg_after_{name}'] = loadavg()
        rss[name] = sampler.take()

    out['session_layer_ms'] = {}
    for n in SESSION_SIZES:  # ascending, so the p99 stub's memory shows last and alone
        out['session_layer_ms'][n] = round(1000 * timed(lambda n=n: session(n), reps=5), 1)
        rss[f'session_{n}'] = sampler.take()
    out['rss_peak_by_phase_mb'] = rss
    s = out['session_layer_ms'][1573] / 1000
    out['warm_p90_total_s'] = round(out['warm_p90']['encode_s'] + s, 2)
    out['warm_p50_total_s'] = round(out['warm_p50']['encode_s'] + out['session_layer_ms'][435] / 1000, 2)
    out['peak_rss_mb'] = round(peak_rss_mb(), 1)
    return out


def run_model(mode, threads):
    sampler = RssPeak()
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(threads)
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModel.from_pretrained(MODEL, dtype=torch.float32, attn_implementation='sdpa').eval()
    remap = keep = None
    if mode == 'int8-pruned':
        keep = json.loads((PRIVATE / 'vocab.json').read_text())
        emb = model.embeddings.tok_embeddings
        new = torch.nn.Embedding(len(keep), emb.embedding_dim)
        new.weight.data = emb.weight.data[keep].clone()
        model.embeddings.tok_embeddings = new
        remap = torch.full((emb.num_embeddings,), keep.index(tok.mask_token_id), dtype=torch.long)
        remap[keep] = torch.arange(len(keep))  # ponytail: unseen ids -> [MASK] row
        del emb
    if mode in ('int8', 'int8-pruned'):
        torch.backends.quantized.engine = 'qnnpack'
        model = torch.ao.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
    with tempfile.NamedTemporaryFile(suffix='.pt') as f:
        torch.save(model.state_dict(), f.name)
        size_mb = os.path.getsize(f.name) / 2**20
    vocab = tok.vocab_size if remap is None else int(remap.max()) + 1
    load_peak = sampler.take()  # imports, load, convert, quantize

    @torch.inference_mode()
    def encode(id_lists):
        """CLS vectors for token-id lists, batched by ``batches``."""
        vecs = [None] * len(id_lists)
        for batch in batches([len(x) for x in id_lists]):
            longest = max(len(id_lists[j]) for j in batch)
            ids = torch.full((len(batch), longest), tok.pad_token_id, dtype=torch.long)
            mask = torch.zeros((len(batch), longest), dtype=torch.long)
            for r, j in enumerate(batch):
                ids[r, : len(id_lists[j])] = torch.tensor(id_lists[j])
                mask[r, : len(id_lists[j])] = 1
            if remap is not None:
                ids = remap[ids]
            h = model(input_ids=ids, attention_mask=mask).last_hidden_state[:, 0]
            for r, j in enumerate(batch):
                vecs[j] = h[r]
        return torch.stack(vecs)

    def ids_of(text):
        return tok(text, truncation=True, max_length=MAX_LEN)['input_ids']

    gen = torch.Generator().manual_seed(0)
    layer = torch.nn.TransformerEncoder(
        torch.nn.TransformerEncoderLayer(384, 6, 1536, dropout=0.0, batch_first=True),
        2,
        enable_nested_tensor=False,
    ).eval()

    @torch.inference_mode()
    def session(n):
        return layer(torch.randn(1, n + 1, 384, generator=gen))

    out = {'mode': mode, 'threads': threads, 'torch': torch.__version__,
           'model_file_mb': round(size_mb, 1), 'vocab_rows': vocab}
    return measure(out, sampler, load_peak, encode, ids_of, session,
                   tok.cls_token_id, tok.sep_token_id, keep)


# --- ONNX Runtime (spike 2): no torch, no transformers in this process ------------------------------
EMB = 'embeddings.tok_embeddings.weight'
ORT_FILES = {
    'ort-fp32': MODEL / 'onnx/model.onnx',
    'ort-int8': PRIVATE / 'onnx/int8.onnx',
    'ort-int8-pruned': PRIVATE / 'onnx/int8-pruned.onnx',
}
# Spike 2 amendment 1 (exploratory, added after a smoke run under load): same file as
# ort-int8-pruned, ORT memory arena off, 2,048-token batches, session stub chunked by 256 in place.
LOWMEM = 'ort-int8-pruned-lowmem'


def ort_build():
    """int8 and pruned-int8 files from IBM's export. Not timed: a product would ship them built."""
    import onnx
    from onnx import numpy_helper
    from onnxruntime.quantization import QuantType, quantize_dynamic

    def q(src, dst):
        quantize_dynamic(src, dst, weight_type=QuantType.QInt8, op_types_to_quantize=['MatMul', 'Gather'])

    (PRIVATE / 'onnx').mkdir(parents=True, exist_ok=True, mode=0o700)
    q(ORT_FILES['ort-fp32'], ORT_FILES['ort-int8'])
    m = onnx.load(ORT_FILES['ort-fp32'])
    init = next(i for i in m.graph.initializer if i.name == EMB)
    keep = json.loads((PRIVATE / 'vocab.json').read_text())
    init.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(init)[keep], EMB))
    pruned = PRIVATE / 'onnx/pruned-fp32.onnx'
    onnx.save(m, pruned)
    q(pruned, ORT_FILES['ort-int8-pruned'])
    return {name: round(path.stat().st_size / 2**20, 1) for name, path in ORT_FILES.items()}


def np_session_layer(d=384, heads=6, ff=1536, layers=2, chunk=1024, inplace=False):
    """Stub session layer in numpy, float32 throughout: post-norm, ReLU, no biases, attention in
    chunks of query rows."""
    import numpy as np

    rng = np.random.default_rng(0)

    def w(rows, cols):
        return (rng.standard_normal((rows, cols)) / np.sqrt(rows)).astype(np.float32)

    stack = [(w(d, 3 * d), w(d, d), w(d, ff), w(ff, d)) for _ in range(layers)]

    def norm(x):
        return (x - x.mean(-1, keepdims=True)) / np.sqrt(x.var(-1, keepdims=True) + 1e-5)

    def run(x):
        n, dh = x.shape[0], d // heads
        for qkv, o, f1, f2 in stack:
            q, k, v = (x @ qkv).reshape(n, 3, heads, dh).transpose(1, 2, 0, 3)  # (heads, n, dh)
            att = np.empty((heads, n, dh), np.float32)
            for s in range(0, n, chunk):
                sc = q[:, s : s + chunk] @ k.transpose(0, 2, 1)
                if inplace:  # same math, one buffer per chunk
                    sc *= 1 / math.sqrt(dh)  # a Python float keeps float32 (NEP 50)
                    sc -= sc.max(-1, keepdims=True)
                    np.exp(sc, out=sc)
                    sc /= sc.sum(-1, keepdims=True)
                    att[:, s : s + chunk] = sc @ v
                else:
                    sc = sc / math.sqrt(dh)
                    sc = np.exp(sc - sc.max(-1, keepdims=True))
                    att[:, s : s + chunk] = (sc / sc.sum(-1, keepdims=True)) @ v
            x = norm(x + att.transpose(1, 0, 2).reshape(n, d) @ o)
            x = norm(x + np.maximum(x @ f1, 0) @ f2)
        return x

    return run


def run_ort(mode, threads):
    for var in ('VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        os.environ[var] = str(threads)  # numpy's BLAS, read at import
    sampler = RssPeak()
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    tok = Tokenizer.from_file(str(MODEL / 'tokenizer.json'))
    tok.enable_truncation(MAX_LEN)
    pad, cls, sep, mask_id = (tok.token_to_id(t) for t in ('<|endoftext|>', '<|startoftext|>', '<|return|>', '[MASK]'))
    assert (pad, cls, sep) == (179935, 179934, 179938), (pad, cls, sep)
    so = ort.SessionOptions()
    so.intra_op_num_threads, so.inter_op_num_threads = threads, 1
    lowmem = mode == LOWMEM
    file = ORT_FILES['ort-int8-pruned' if lowmem else mode]
    so.enable_cpu_mem_arena = not lowmem
    budget = 2048 if lowmem else BATCH_TOKENS
    sess = ort.InferenceSession(str(file), so, providers=['CPUExecutionProvider'])
    remap = keep = None
    if mode.startswith('ort-int8-pruned'):
        keep = json.loads((PRIVATE / 'vocab.json').read_text())
        remap = np.full(180000, keep.index(mask_id), dtype=np.int64)  # ponytail: unseen -> [MASK]
        remap[keep] = np.arange(len(keep))
    load_peak = sampler.take()  # imports, session load

    def encode(id_lists):
        vecs = np.empty((len(id_lists), 384), np.float32)
        for batch in batches([len(x) for x in id_lists], budget):
            longest = max(len(id_lists[j]) for j in batch)
            ids = np.full((len(batch), longest), pad, dtype=np.int64)
            att = np.zeros((len(batch), longest), dtype=np.int64)
            for r, j in enumerate(batch):
                ids[r, : len(id_lists[j])] = id_lists[j]
                att[r, : len(id_lists[j])] = 1
            if remap is not None:
                ids = remap[ids]
            h = sess.run(['last_hidden_state'], {'input_ids': ids, 'attention_mask': att})[0]
            vecs[batch] = h[:, 0]
        return vecs

    def ids_of(text):
        return tok.encode(text).ids

    layer = np_session_layer(chunk=256, inplace=True) if lowmem else np_session_layer()
    rng = np.random.default_rng(0)

    def session(n):
        return layer(rng.standard_normal((n + 1, 384), dtype=np.float32))

    out = {'mode': mode, 'threads': threads, 'onnxruntime': ort.__version__,
           'model_file_mb': round(file.stat().st_size / 2**20, 1), 'batch_tokens': budget,
           'vocab_rows': 180000 if keep is None else len(keep)}
    return measure(out, sampler, load_peak, encode, ids_of, session, cls, sep, keep)


def _check():
    assert pct([3, 1, 2, 4], 50) == 2 and pct([3, 1, 2, 4], 100) == 4
    b = [{'role': 'user', 'kind': 'text'}, {'role': 'assistant', 'kind': 'text'},
         {'role': 'user', 'kind': 'text'}, {'role': 'user', 'kind': 'tool_result'}]
    assert last_turn(b) == b[3:] and last_turn(b[1:2]) == b[1:2]
    lens = [2, 2, 2, 2048, 2048, 2048, 2048, 2048, 5000]
    got = batches(lens, 8192)
    assert sorted(j for bt in got for j in bt) == list(range(len(lens)))
    assert all(len(bt) == 1 or len(bt) * max(lens[j] for j in bt) <= 8192 for bt in got), got


if __name__ == '__main__':
    _check()
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['stats', 'fp32', 'int8', 'int8-pruned', 'ort-build', *ORT_FILES, LOWMEM])
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--tag', default='', help='suffix for the output file, e.g. idle')
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if a.mode == 'stats':
        res, name = stats(), 'stats'
    elif a.mode == 'ort-build':
        res, name = ort_build(), 'ort-build'
    else:
        run = run_ort if a.mode.startswith('ort-') else run_model
        res = run(a.mode, a.threads)
        name = f'{a.mode}-t{a.threads}' + (f'-{a.tag}' if a.tag else '')
    (OUT / f'{name}.json').write_text(json.dumps(res, indent=1) + '\n')
    json.dump(res, sys.stdout, indent=1)
