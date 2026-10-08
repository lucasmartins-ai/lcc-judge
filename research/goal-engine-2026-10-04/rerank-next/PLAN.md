# Next decision — compact ranking-pretrained cross-encoder

Status: both frozen upstream and one scope-checked input-view diagnostic completed and failed.
Raw-control final pooled AUC .6720 / view .6929, with no cuts or errors.
The metadata-preparation manifest remains a historical artifact record; inference
results are separate in ../reranker-known-control/ and ../measurement-projection-v1/.
The goal stays active. The semantic CPU study rejects its six adapted candidates;
it does not demonstrate that longer native context is the remaining bottleneck.

Candidate selected before this next comparison:
`cross-encoder/ms-marco-MiniLM-L6-v2`, revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a`. Native BertForSequenceClassification,
six layers,384 hidden units,512 position limit, Apache-2.0 as declared upstream.
Snapshot file hashes and the pinned model card are preserved; weights stay in
the external HF cache. No remote custom code or additional framework is needed
for the documented Transformers recipe.

The upstream model is trained for passage ranking, with raw logits for pairs;
this motivates testing its relation to the LCC objective before adapting another
masked-language encoder. It does not establish local latency, LCC preservation,
calibrated probability, P2 necessity or Portuguese-language support. Primary
sources: [model card](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2/blob/233902d25c440f23af6f7d6e94d2946bac0bee0a/README.md),
[official recipes](https://www.sbert.net/docs/cross_encoder/pretrained_models.html).

1. Completed: implement/test the exact pair recipe: eval mode/CPU/fp32, complete tokenizer
   input, raw single logit, explicit no-cut/refusal accounting. Freeze driver,
   model/config/tokenizer identities, identical input cohort and criteria before
   scoring. No automatic silent clipping to512 tokens.
2. Completed negatively: validation and the now-exposed semantic final cohort as a bounded matched
   diagnostic. Thresholds use validation only. Report pooled/paired AUC, recall,
   negative rejection, per-family errors and total cost. The old final cohort is
   exposed and cannot confirm an untouched transfer claim for this new model.
3. Completed negatively: compact-relation-v1 reserved eight new measurement pairs
   before six fixed full-MiniLM adaptations (BCE/joint ×3seeds ×3epochs). Old18
   families became development. Validation selectedBCE;finalpool.8279 and all
   seeds fail. A later fixed report control also fails. Further data need real
   tool-role contracts, fresh wording/contradictions/UNKNOWN and untouched families.
   Before training/model choice for adoption, reserve new concept families and
   ambiguity/counterevidence cases. Require each selected seed's pooled/paired
   AUC≥.90, recall≥.95, rejection≥.70 and zero unreported cuts/errors.
4. Only a useful candidate proceeds to a frozen semantic LCC outcome pilot with
   full input control, verified success≥.90, loss≤.02, removal≥.25, UNKNOWN
   preservation and complete cold/warm/RAM/API accounting. Measure dossier
   coverage via blocks; do not call 512 per-pair capacity a 32K neural window.
5. Quantization/batching waits for quality. No RoPE expansion, more epochs of
   the losing heads, or rejected replay-label admission now. Public release,
   default substitution and a manuscript claim still require their own gates.
