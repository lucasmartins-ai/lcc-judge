# Semantic relation cycle — tool measurement relevance

The literal observation workflow completed: 36/36 local-selected outcomes in the
six exposed tasks at 8K/32K, with every declared observation and ambiguity kept.
This does not validate a general neural selector. The next target is a relation
between a natural-language objective and a tool report's measurement description.
Entity/time scope is supplied or preserved separately, rather than asking the
neural head to relearn exact identifier equality.

Default workload assumption: agent tool outputs (logs/tests/configuration), as
suggested by LCC's role. This can be changed by the user without rewriting old
studies. No production or P2 training labels are taken from rejected replay.

## Data and controls

- Twelve authored concept-pair families for training/validation, six reserved new
  concept pairs for final evaluation. Paired near concepts include elapsed versus
  CPU time, skipped versus failed checks and branch versus statement coverage.
- Queries and report descriptions use separate paraphrases. Both sides of each
  concept pair are queried, so the same report must change label with the goal.
  Numbers/levels/format are balanced across labels; no ground-truth markers, row
  IDs or semantic slot annotations enter model input.
- P1 means directly reporting the requested measurement, including an ordinary
  value. It does not mean anomaly, root cause, necessity or sufficiency. Labels
  follow the declared authored concepts; not externally reviewed semantic truth.
- Freeze all source/data/criteria before training. Audit content hashes, complete
  HF pair lengths and families. Final inference follows validation selection.
- Compare frozen and last-two adaptation of the same clean parent, three matched
  seeds, three epochs, batch eight. No increased RoPE/window. Report all arms.
- Lexical, pinned Laya, official BGE and parent controls use identical complete
  inputs. Cut/error rows cannot pass a same-population gate.

## Decision criteria

Each seed of the validation-selected arm must achieve strict pooled and paired
P1 AUC ≥.90, positive recall ≥.95 and negative rejection ≥.70 at validation-only
thresholds; zero omitted/cut/error rows. Family-bootstrap intervals are descriptive
because there are only six authored final families. No deployment admission from
synthetic scores alone. A passing candidate next needs a frozen LCC outcome pilot
on this semantic operation and whole-path cost, before quantization or adoption.

If the candidate loses to a simple control or fails transfer, keep defaults/shadow
unchanged, preserve the failure and identify the actual error before further
training. The useful replacement goal remains active.
