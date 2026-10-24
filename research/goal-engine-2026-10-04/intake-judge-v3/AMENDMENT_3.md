# Intake judge v3, amendment 3 (2026-10-24): drop the owner-dev macro-F1 guard, found after the dev run

Written after the dev table of all 6 configs was seen (`FREEZE-prefix.json`), before either held-out gold was
drawn. The owner chose this on 2026-10-24, knowing it comes after seeing dev numbers.

## What the dev run showed (MEDIDO, dev against teacher labels)

- Data (ii), owner plus public Claude Code: WildChat-dev macro-F1 0.124–0.132, public-dev 0.129–0.137.
- Data (iii), adding WildChat: WildChat-dev 0.358–0.365, public-dev 0.366–0.372, public Claude Code-dev
  0.556 (vs 0.473). Owner-dev 0.472–0.479 (vs 0.477–0.487 for ii).
- Every (iii) config failed the guard "owner-dev macro-F1 at least 0.480". The best one failed by 0.0009.
- Under the rule as written the pick was (ii) C=3, the config that generalises worst.

## Change

- The guard "owner-dev macro-F1 at least 0.480" is removed. Acceptance 1 of the final test already protects
  the owner's use: v3 minus shipped on the owner gold, CI lower bound above −0.03.
- Nothing else changes: the B budget, the guard "accuracy on the 116 v1 gold items at least 0.509", the
  score, the tie rule and the threshold rule.
- Applying the unchanged rest of the rule picks **(iii) C=3**: score 0.4195, owner-dev 0.4735, public-dev
  0.3655, v1-gold 0.5431. (iii) C=10 has a higher score (0.4253), but it fails the v1-gold guard (0.500), and
  that guard stays.

## Disclosed risk

This changes the pick after its dev score was known, toward the config that does best on public data. The
two held-outs are untouched and decide: v3 ships only if it is non-inferior on the owner gold, superior on
the external `final` gold, and also superior on the external `blind` view (amendment 2).
