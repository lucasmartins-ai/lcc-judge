"""Objective-aligned detect supervision experiment (Step 5 of Audit).

Compares:
1. Standard single-head baseline (BCE on pooled binary label)
2. Joint detect+judge supervision (2-head: P(relevant) and P(incident))
   - y_detect = 1 for pos & neg_decoy (in-domain); 0 for neg_unrelated
   - y_judge = 1 for pos; 0 for neg_decoy (masked on neg_unrelated)
   - score = sigmoid(logit_detect) * sigmoid(logit_judge)

Evaluates on probe suite at depth 0 and 512:
Success criteria:
- D pooled >= 0.70 in 0/512
- Paired bootstrap CI of gain in D strictly > 0
- Loss in J <= 0.02
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from bakeoff.probes import CASES, make_block
from specialist.model import SpecialistHead


class MultiTaskSpecialistHead(SpecialistHead):
    """ModernBERT backbone with joint Judge and Detect heads sharing line-attn representations."""

    def __init__(
        self,
        model_id: str = "answerdotai/ModernBERT-base",
        head_hidden: int = 256,
        dropout: float = 0.1,
        freeze_encoder: bool = True,
        unfreeze_last_n: int = 0,
        pooling: str = "line-attn",
    ) -> None:
        super().__init__(
            model_id=model_id,
            head_hidden=head_hidden,
            dropout=dropout,
            freeze_encoder=freeze_encoder,
            unfreeze_last_n=unfreeze_last_n,
            pooling=pooling,
        )
        hidden = self.encoder.config.hidden_size
        self.head_judge = nn.Sequential(
            nn.Linear(hidden, head_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(head_hidden, 1),
        )
        self.head_detect = nn.Sequential(
            nn.Linear(hidden, head_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(head_hidden, 1),
        )

    def forward(self, enc: dict) -> tuple[torch.Tensor, torch.Tensor]:
        line_ids = enc.get("line_ids")
        core = {k: v for k, v in enc.items() if k != "line_ids"} if line_ids is not None else enc
        hidden = self.encoder(**core).last_hidden_state
        assert self.use_lines and line_ids is not None, "line pooling needs line_ids"

        B, T = line_ids.shape
        valid = line_ids >= 0
        if not bool(valid.any()):
            return hidden.new_zeros(B), hidden.new_zeros(B)
        n_lines = (valid.long() * (line_ids + 1)).max(1).values.clamp(min=1)
        L = int(n_lines.max())
        flat = line_ids.clamp(min=0) + torch.arange(B, device=hidden.device).unsqueeze(1) * L
        flat_v = flat[valid]

        sums = hidden.new_zeros((B * L, hidden.shape[-1]))
        sums.scatter_add_(0, flat_v.unsqueeze(-1).expand(-1, hidden.shape[-1]), hidden[valid])
        counts = hidden.new_zeros((B * L,))
        counts.scatter_add_(0, flat_v, valid.float()[valid])
        line_reps = sums / counts.clamp(min=1).unsqueeze(-1)
        line_scores = self.line_score(line_reps).squeeze(-1).view(B, L)
        pad = torch.arange(L, device=hidden.device).unsqueeze(0) >= n_lines.unsqueeze(1)
        line_scores = line_scores.masked_fill(pad, -1e4)
        weights = line_scores.softmax(-1).unsqueeze(-1)
        pooled = (line_reps.view(B, L, -1) * weights).sum(1)  # [B, H]

        logit_judge = self.head_judge(pooled).squeeze(-1)
        logit_detect = self.head_detect(pooled).squeeze(-1)
        return logit_judge, logit_detect


class LabeledJsonlDataset(Dataset):
    def __init__(self, path: str) -> None:
        self.items = [json.loads(line) for line in open(path) if line.strip()]

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> dict:
        return self.items[i]


def collate_multitask(batch: list[dict]) -> tuple[list[str], list[str], torch.Tensor, torch.Tensor, torch.Tensor]:
    objectives = [b["objective"] for b in batch]
    texts = [b["text"] for b in batch]
    y_judge = [1.0 if b["kind"] == "pos" else 0.0 for b in batch]
    mask_judge = [0.0 if b["kind"] == "neg_unrelated" else 1.0 for b in batch]
    y_detect = [0.0 if b["kind"] == "neg_unrelated" else 1.0 for b in batch]
    return (
        objectives,
        texts,
        torch.tensor(y_judge, dtype=torch.float32),
        torch.tensor(y_detect, dtype=torch.float32),
        torch.tensor(mask_judge, dtype=torch.float32),
    )


def train_joint_model(data_dir: str = "data/exp02e", epochs: int = 3, device: str = "mps",
                      batch_size: int = 8, out_dir: str = "models/exp05-joint-detect") -> str:
    os.makedirs(out_dir, exist_ok=True)
    train_ds = LabeledJsonlDataset(os.path.join(data_dir, "train.jsonl"))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_multitask)

    model = MultiTaskSpecialistHead(pooling="line-attn").to(device)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-3, weight_decay=0.01)
    bce = nn.BCEWithLogitsLoss()

    print(f"Training Joint Detect+Judge Model for {epochs} epochs on {device}...")
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss, n = 0.0, 0
        t0 = time.perf_counter()
        for objs, txts, y_j, y_d, m_j in train_loader:
            enc = model.encode(objs, txts, max_len=1024)
            enc = {k: v.to(device) for k, v in enc.items()}
            y_j = y_j.to(device)
            y_d = y_d.to(device)
            m_j = m_j.to(device)

            logit_j, logit_d = model(enc)
            loss_d = bce(logit_d, y_d)
            loss_j_all = nn.functional.binary_cross_entropy_with_logits(logit_j, y_j, reduction="none")
            loss_j = (loss_j_all * m_j).sum() / m_j.sum().clamp(min=1.0)
            loss = loss_j + loss_d

            opt.zero_grad()
            loss.backward()
            opt.step()

            total_loss += float(loss.detach()) * len(objs)
            n += len(objs)
        dt = time.perf_counter() - t0
        print(f"Epoch {epoch}/{epochs} | loss={total_loss/n:.4f} ({dt:.1f}s)")

    weights_path = os.path.join(out_dir, "weights.pt")
    torch.save(model.state_dict(), weights_path)
    return out_dir


@torch.no_grad()
def score_probes(model: MultiTaskSpecialistHead, depths: list[int] = [0, 512], device: str = "mps") -> dict[str, Any]:
    model.eval()

    records = []
    for case in CASES:
        for d in depths:
            b_fact = make_block(case, d, "fact")
            b_decoy = make_block(case, d, "noise_decoy")
            b_unrel = make_block(case, d, "noise_unrelated")

            enc_fact = {k: v.to(device) for k, v in model.encode([case.objective], [b_fact["text"]], max_len=1024).items()}
            enc_decoy = {k: v.to(device) for k, v in model.encode([case.objective], [b_decoy["text"]], max_len=1024).items()}
            enc_unrel = {k: v.to(device) for k, v in model.encode([case.objective], [b_unrel["text"]], max_len=1024).items()}

            out_f_j, out_f_d = model(enc_fact)
            out_dec_j, out_dec_d = model(enc_decoy)
            out_unr_j, out_unr_d = model(enc_unrel)

            p_judge_f = float(torch.sigmoid(out_f_j[0]))
            p_detect_f = float(torch.sigmoid(out_f_d[0]))
            p_joint_f = p_judge_f * p_detect_f

            p_judge_dec = float(torch.sigmoid(out_dec_j[0]))
            p_detect_dec = float(torch.sigmoid(out_dec_d[0]))
            p_joint_dec = p_judge_dec * p_detect_dec

            p_judge_unr = float(torch.sigmoid(out_unr_j[0]))
            p_detect_unr = float(torch.sigmoid(out_unr_d[0]))
            p_joint_unr = p_judge_unr * p_detect_unr

            records.append({
                "case_id": case.case_id,
                "depth": d,
                "f_joint": p_joint_f,
                "f_judge": p_judge_f,
                "dec_joint": p_joint_dec,
                "dec_judge": p_judge_dec,
                "unr_joint": p_joint_unr,
                "unr_judge": p_judge_unr,
            })
    return {"records": records}


def compute_auc(pos: list[float], neg: list[float]) -> float:
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    total = len(pos) * len(neg)
    return (wins + 0.5 * ties) / total if total else 0.5


def evaluate_pilot(records: list[dict], depths: list[int] = [0, 512]) -> dict[str, Any]:
    res = {}
    for d in depths:
        d_recs = [r for r in records if r["depth"] == d]
        f_joint = [r["f_joint"] for r in d_recs]
        dec_joint = [r["dec_joint"] for r in d_recs]
        unr_joint = [r["unr_joint"] for r in d_recs]

        f_judge_only = [r["f_judge"] for r in d_recs]
        dec_judge_only = [r["dec_judge"] for r in d_recs]
        unr_judge_only = [r["unr_judge"] for r in d_recs]

        j_joint = compute_auc(f_joint, dec_joint)
        d_joint = compute_auc(f_joint, unr_joint)

        j_judge_only = compute_auc(f_judge_only, dec_judge_only)
        d_judge_only = compute_auc(f_judge_only, unr_judge_only)

        # Bootstrap 95% CI on gain in D
        rng = np.random.default_rng(42)
        n = len(d_recs)
        boot_d_gains = []
        for _ in range(1000):
            idx = rng.choice(n, size=n, replace=True)
            b_f_joint = [f_joint[i] for i in idx]
            b_unr_joint = [unr_joint[i] for i in idx]
            b_f_judge = [f_judge_only[i] for i in idx]
            b_unr_judge = [unr_judge_only[i] for i in idx]
            gain = compute_auc(b_f_joint, b_unr_joint) - compute_auc(b_f_judge, b_unr_judge)
            boot_d_gains.append(gain)

        ci_low = float(np.percentile(boot_d_gains, 2.5))
        ci_high = float(np.percentile(boot_d_gains, 97.5))

        res[f"depth_{d}"] = {
            "judge_only": {"J": round(j_judge_only, 4), "D": round(d_judge_only, 4)},
            "joint_supervision": {"J": round(j_joint, 4), "D": round(d_joint, 4)},
            "delta_J": round(j_joint - j_judge_only, 4),
            "delta_D": round(d_joint - d_judge_only, 4),
            "delta_D_95ci": [round(ci_low, 4), round(ci_high, 4)],
            "d_passes_070": d_joint >= 0.70,
            "ci_strictly_positive": ci_low > 0.0,
            "j_loss_under_002": (j_judge_only - j_joint) <= 0.02,
        }
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
    ap.add_argument("--out", default="research/detect-supervision-results.json")
    args = ap.parse_args()

    model_dir = train_joint_model(epochs=args.epochs, device=args.device)
    model = MultiTaskSpecialistHead(pooling="line-attn").to(args.device)
    model.load_state_dict(torch.load(os.path.join(model_dir, "weights.pt"), map_location=args.device))

    scores = score_probes(model, depths=[0, 512], device=args.device)
    eval_res = evaluate_pilot(scores["records"], depths=[0, 512])

    print("\n--- OBJECTIVE-ALIGNED DETECT SUPERVISION RESULTS ---")
    print(json.dumps(eval_res, indent=2))
    with open(args.out, "w") as f:
        json.dump(eval_res, f, indent=2)


if __name__ == "__main__":
    main()
