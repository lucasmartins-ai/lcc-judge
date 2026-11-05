"""Cost spike for an LCC-only block encoder: measurement only, no training.

Reads block texts from ~/.lcc (private) and writes counts and timings only, to out/<mode>.json.
Criteria and definitions: RESULTS.md (agreed with the owner before the run).

  PY=~/lcc/.venv/bin/python
  $PY -I research/encoder-spike-2026-11-05/spike.py stats        # tokenizer only, picks the items
  $PY -I research/encoder-spike-2026-11-05/spike.py fp32         # then int8, int8-pruned
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
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


def run_model(mode, threads):
    sampler = RssPeak()
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(threads)
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModel.from_pretrained(MODEL, dtype=torch.float32, attn_implementation='sdpa').eval()
    remap = None
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
    load_peak = sampler.take()  # load, convert, quantize: transient a pre-built file would skip

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

    out = {'mode': mode, 'threads': threads, 'torch': torch.__version__, 'model_file_mb': round(size_mb, 1)}
    out['loadavg_start'] = loadavg()
    cls, sep = tok.cls_token_id, tok.sep_token_id
    gen = torch.Generator().manual_seed(0)
    lat = {}
    for n in LENGTHS:
        body = torch.randint(1000, 170000, (n - 2,), generator=gen).tolist()
        if remap is not None:  # stay inside the pruned table's real rows
            keep = json.loads((PRIVATE / 'vocab.json').read_text())
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

    layer = torch.nn.TransformerEncoder(
        torch.nn.TransformerEncoderLayer(384, 6, 1536, dropout=0.0, batch_first=True),
        2,
        enable_nested_tensor=False,
    ).eval()

    @torch.inference_mode()
    def session(n):
        return layer(torch.randn(1, n + 1, 384, generator=gen))

    out['session_layer_ms'] = {}
    for n in SESSION_SIZES:  # ascending, so the p99 stub's memory shows last and alone
        out['session_layer_ms'][n] = round(1000 * timed(lambda n=n: session(n), reps=5), 1)
        rss[f'session_{n}'] = sampler.take()
    out['rss_peak_by_phase_mb'] = rss
    s = out['session_layer_ms'][1573] / 1000
    out['warm_p90_total_s'] = round(out['warm_p90']['encode_s'] + s, 2)
    out['warm_p50_total_s'] = round(out['warm_p50']['encode_s'] + out['session_layer_ms'][435] / 1000, 2)
    out['vocab_rows'] = vocab
    out['peak_rss_mb'] = round(peak_rss_mb(), 1)
    return out


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
    ap.add_argument('mode', choices=['stats', 'fp32', 'int8', 'int8-pruned'])
    ap.add_argument('--threads', type=int, default=4)
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    res = stats() if a.mode == 'stats' else run_model(a.mode, a.threads)
    name = 'stats' if a.mode == 'stats' else f'{a.mode}-t{a.threads}'
    (OUT / f'{name}.json').write_text(json.dumps(res, indent=1) + '\n')
    json.dump(res, sys.stdout, indent=1)
