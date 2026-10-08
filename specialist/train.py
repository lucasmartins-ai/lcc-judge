"""EXP-02 training: necessity decision head on ModernBERT.

Usage:
    /Users/Master/LCC/.venv/bin/python -m specialist.train --device mps --epochs 3

Protocol (docs/04 §5, R2): OOD gate is evaluated every epoch and printed BEFORE
any in-domain number; the checkpoint stores temperature fitted on val only.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from dataclasses import dataclass

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .model import SpecialistHead
from .numerical import finite_update
from .training_state import data_digest, restore_resume, save_resume

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "..", "data", "exp02e")
OUT_DIR = os.path.join(HERE, "..", "models", "exp02-specialist-head")


class JsonlDataset(Dataset):
    def __init__(self, path: str):
        with open(path) as f:
            self.items = [json.loads(line) for line in f if line.strip()]

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> dict:
        return self.items[i]


def collate(batch: list[dict]) -> tuple[list[str], list[str], list[int]]:
    return (
        [b["objective"] for b in batch],
        [b["text"] for b in batch],
        [b["label"] for b in batch],
    )


def auc(logits: list[float], labels: list[int]) -> float:
    pos = [l for l, y in zip(logits, labels) if y == 1]
    neg = [l for l, y in zip(logits, labels) if y == 0]
    if not pos or not neg:
        return 0.5
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def make_stratified_loader(dataset: JsonlDataset, batch_size: int, limit_batches: int | None = None,
                           seed: int = 0) -> DataLoader:
    """Create a DataLoader that samples evenly across all domains in the dataset."""
    from collections import defaultdict
    by_domain = defaultdict(list)
    for idx, it in enumerate(dataset.items):
        by_domain[it["domain"]].append(idx)

    selected_indices = []
    if limit_batches is None:
        # Full evaluation: interleave domains so batches are balanced
        domains = sorted(by_domain.keys())
        max_len = max(len(v) for v in by_domain.values())
        for i in range(max_len):
            for d in domains:
                if i < len(by_domain[d]):
                    selected_indices.append(by_domain[d][i])
    else:
        max_items = limit_batches * batch_size
        domains = sorted(by_domain.keys())
        per_domain = max(1, max_items // len(domains))
        rng = random.Random(seed)
        for d in domains:
            domain_indices = list(by_domain[d])
            rng.shuffle(domain_indices)
            selected_indices.extend(domain_indices[:per_domain])
        # shuffle the combined subset so domains are interleaved in batches
        rng.shuffle(selected_indices)

    from torch.utils.data import Subset
    subset = Subset(dataset, selected_indices)
    return DataLoader(subset, batch_size=batch_size, shuffle=False, collate_fn=collate)


@torch.no_grad()
def evaluate(model: SpecialistHead, loader: DataLoader, device: str, max_len: int) -> float:
    model.eval()
    logits, labels = [], []
    for objectives, texts, y in loader:
        enc = model.encode(objectives, texts, max_len=max_len)
        enc = {k: v.to(device) for k, v in enc.items()}
        logits.extend(model(enc).float().cpu().tolist())
        labels.extend(y)
    return auc(logits, labels)


@torch.no_grad()
def fit_temperature(model: SpecialistHead, loader: DataLoader, device: str, max_len: int) -> float:
    model.eval()
    logits, labels = [], []
    for objectives, texts, y in loader:
        enc = model.encode(objectives, texts, max_len=max_len)
        enc = {k: v.to(device) for k, v in enc.items()}
        logits.extend(model(enc).float().cpu().tolist())
        labels.extend(y)
    best_t, best_nll = 1.0, float("inf")
    t = 0.25
    while t <= 4.0001:
        nll = 0.0
        for l, y in zip(logits, labels):
            p = 1.0 / (1.0 + pow(2.718281828, -l / t))
            nll -= (y * __import__("math").log(max(p, 1e-9)) + (1 - y) * __import__("math").log(max(1 - p, 1e-9)))
        if nll < best_nll:
            best_nll, best_t = nll, t
        t += 0.05
    return round(best_t, 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=1024)
    ap.add_argument("--lr-head", type=float, default=1e-3)
    ap.add_argument("--lr-encoder", type=float, default=2e-5)
    ap.add_argument("--unfreeze-last-n", type=int, default=0)
    ap.add_argument("--pooling", default="mean",
                    choices=("mean", "attn", "line-max", "line-attn"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument('--model-id', default='answerdotai/ModernBERT-base')
    ap.add_argument('--revision', default=None)
    ap.add_argument('--offline', action='store_true')
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--resume", action="store_true", help="continue from weights.pt in --out")
    ap.add_argument("--data-dir", default=DATA_DIR)
    ap.add_argument("--eval-limit", type=int, default=30,
                    help="batches per split per epoch (full eval runs at the end)")
    ap.add_argument("--no-final-eval", action="store_true",
                    help="skip the end-of-run full OOD/val AUC (temperature is still "
                         "fitted on val and the checkpoint still written) — lets an "
                         "interrupted multi-epoch run resume without paying ~2.6k "
                         "forwards every invocation")
    args = ap.parse_args()
    if args.epochs < 1:
        ap.error('--epochs must be positive')
    if args.resume and not os.path.isfile(os.path.join(args.out,'resume.pt')):
        ap.error('Missing resume state: historical weights cannot restore optimizer/RNG; use a new output directory')
    if not args.resume and os.path.isfile(os.path.join(args.out,'weights.pt')):
        ap.error('Output already has weights; use --resume or a new output directory')

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    train_ds = JsonlDataset(os.path.join(args.data_dir, "train.jsonl"))
    val_ds = JsonlDataset(os.path.join(args.data_dir, "val.jsonl"))
    ood_ds = JsonlDataset(os.path.join(args.data_dir, "ood.jsonl"))
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, collate_fn=collate)
    ood_loader = DataLoader(ood_ds, batch_size=args.batch_size, collate_fn=collate)

    dataset_digest = data_digest(args.data_dir)
    model = SpecialistHead(model_id=args.model_id, revision=args.revision,
                           local_files_only=args.offline, unfreeze_last_n=args.unfreeze_last_n,
                           pooling=args.pooling).to(args.device)
    os.makedirs(args.out, exist_ok=True)
    params = [p for p in model.parameters() if p.requires_grad]
    enc_params = [p for p in model.encoder.parameters() if p.requires_grad]
    # everything trainable outside the encoder (head + pooling scorers, incl.
    # the EXP-02c line scorer) trains at the head learning rate
    head_params = [p for n, p in model.named_parameters()
                   if p.requires_grad and not n.startswith("encoder.")]
    groups = [{"params": head_params, "lr": args.lr_head}]
    if enc_params:
        groups.append({"params": enc_params, "lr": args.lr_encoder})
    opt = torch.optim.AdamW(groups, weight_decay=0.01)
    loss_fn = nn.BCEWithLogitsLoss()

    history = []
    start_epoch = 1
    if args.resume:
        restored = restore_resume(os.path.join(args.out,'resume.pt'), model, opt,
                                  args=vars(args), data_digest=dataset_digest,total_epochs=args.epochs)
        history = restored['history']
        start_epoch = restored['epoch'] + 1
        print(json.dumps(dict(resumed_epoch=restored['epoch'],rng_restored=True)),flush=True)

    for epoch in range(start_epoch, args.epochs + 1):
        model.train()
        t0, total, n = time.perf_counter(), 0.0, 0
        for objectives, texts, y in train_loader:
            enc = model.encode(objectives, texts, max_len=args.max_len)
            enc = {k: v.to(args.device) for k, v in enc.items()}
            labels = torch.tensor(y, dtype=torch.float32, device=args.device)
            loss = loss_fn(model(enc), labels)
            finite_update(loss, model, opt)
            total += float(loss) * len(y)
            n += len(y)
        ood_eval_loader = make_stratified_loader(ood_ds, args.batch_size, limit_batches=args.eval_limit, seed=args.seed + epoch)
        val_eval_loader = make_stratified_loader(val_ds, args.batch_size, limit_batches=args.eval_limit, seed=args.seed + epoch)
        ood_auc = evaluate(model, ood_eval_loader, args.device, args.max_len)
        val_auc = evaluate(model, val_eval_loader, args.device, args.max_len)
        row = {
            "epoch": epoch,
            "train_loss": round(total / max(n, 1), 4),
            "auc_ood": round(ood_auc, 4),   # gate first — never quote in-domain first (R2)
            "auc_val": round(val_auc, 4),
            "seconds": round(time.perf_counter() - t0, 1),
            "params_trained_m": round(sum(p.numel() for p in params) / 1e6, 2),
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        save_resume(os.path.join(args.out,'resume.pt'),model,opt,epoch=epoch,history=history,
                    args=vars(args),data_digest=dataset_digest)
        # per-epoch checkpoint & state saving
        sd = model.state_dict()
        trainable_names = [n for n, p in model.named_parameters() if p.requires_grad]
        torch.save({n: sd[n] for n in trainable_names}, os.path.join(args.out, "weights.pt"))
        torch.save(opt.state_dict(), os.path.join(args.out, "optimizer.pt"))
        meta_path = os.path.join(args.out, "training_meta.json")
        with open(meta_path, "w") as f:
            json.dump({"history": history, "args": vars(args), "current_epoch": epoch}, f, indent=2)

    val_temp_loader = make_stratified_loader(val_ds, args.batch_size, limit_batches=None)
    model.temperature = fit_temperature(model, val_temp_loader, args.device, args.max_len)

    ood_full_loader = make_stratified_loader(ood_ds, args.batch_size, limit_batches=None)
    val_full_loader = make_stratified_loader(val_ds, args.batch_size, limit_batches=None)
    final = {"skipped_final_eval": True} if args.no_final_eval else {
        "auc_ood_full": round(evaluate(model, ood_full_loader, args.device, args.max_len), 4),
        "auc_val_full": round(evaluate(model, val_full_loader, args.device, args.max_len), 4),
    }
    print(json.dumps(final), flush=True)
    sd = model.state_dict()
    trainable_names = [n for n, p in model.named_parameters() if p.requires_grad]
    save_sd = {n: sd[n] for n in trainable_names}
    torch.save(save_sd, os.path.join(args.out, "weights.pt"))
    torch.save(opt.state_dict(), os.path.join(args.out, "optimizer.pt"))
    config = {
        "model_id": model.model_id,
        "revision": model.revision,
        "dataset_digest": dataset_digest,
        "max_len": args.max_len,
        "temperature": model.temperature,
        "unfreeze_last_n": args.unfreeze_last_n,
        "pooling": args.pooling,
        "seed": args.seed,
        "data_manifest": json.load(open(os.path.join(args.data_dir, "manifest.json"))),
    }
    with open(os.path.join(args.out, "config.json"), "w") as f:
        json.dump(config, f, indent=2)
    meta_path = os.path.join(args.out, "training_meta.json")
    with open(meta_path, "w") as f:
        json.dump({"history": history, "args": vars(args), "current_epoch": history[-1]['epoch'], "final": final}, f, indent=2)
    print(json.dumps({"saved": args.out, "temperature": model.temperature}, indent=2))


if __name__ == "__main__":
    main()
