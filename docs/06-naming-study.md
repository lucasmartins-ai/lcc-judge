# 06 — Naming Study (v0)

Status: Sprint 0 — **decision deferred by the founder (2026-10-02):** the name is not
chosen until training gives the model its real dimension; this study stays open as a
living shortlist. Working title in code/datasets: `specialist` (neutral placeholder).
The provisional name `LCC-Judge` is retired as too narrow: the model grows from
KEEP/TRIM/DROP into necessity, sufficiency, risk and inference-allocation estimation.
The freeze protocol (§5) runs only at repo creation / model naming time.

Naming rules applied:
- LookADev family logic: `LookA + conceito`, preserving the Lucas → LookA phonetics.
- Must work as: open-source project, model family (`X-Tiny/Base/Large`), library, paper.
- Short, natural spoken aloud in PT-BR and EN, no childish wordplay.
- Must NOT limit the product to "relevance", "compression" or "judge".
- Must survive the evolution toward MSI decision estimation.

## 1. Candidate pool (48)

### Family A — LookA + instrument/decision concepts (the "-scope" school)

| # | Candidate | One-line rationale | Disposition |
|---|---|---|---|
| A1 | **LookaScope** | instrument you look through; scope = what a task needs; telescope=long context, microscope=block granularity | **FINALIST** |
| A2 | **LookaGauge** | gauges how much context/intelligence a task needs | **FINALIST** |
| A3 | **LookaLens** | focuses on what matters | FINALIST (collision: camera-lens social brand) |
| A4 | LookaJudge | old provisional logic | REJECT — too narrow (prompt §2) |
| A5 | LookaAssess | assesses task needs | SHORTLIST — double-s clumsy |
| A6 | LookaSense | "sense" of what matters | SHORTLIST — vague |
| A7 | LookaAcuity | mental acuity | SHORTLIST — Acuity brands exist (scheduling/industrial) |
| A8 | LookaMeter | measures needs | weak — "-meter" reads as telemetry |
| A9 | LookaBearing | navigational bearing + "has a bearing on" | SHORTLIST |
| A10 | LookaSage | the wise one | weak — PT pronunciation awkward |
| A11 | LookaCortex | brain region | REJECT — Cortex name saturation |
| A12 | LookaPilot | steers | weak — autopilot connotation |
| A13 | LookaHelm | steering | REJECT — Kubernetes Helm collision (MAJOR) |
| A14 | LookaTriage | triage | REJECT — collides with own cognitive-triage work |
| A15 | LookaWeigh | weigh evidence | REJECT — sounds like "look away" |
| A16 | LookaSieve | filters | weak — "sieve" hard in PT |
| A17 | LookaTally | counts/measures | weak |
| A18 | LookaSteward | manages resources | SHORTLIST — good metaphor, longer |
| A19 | LookaQuota | allocates budget | weak — narrow to budgets |
| A20 | LookaBudget | budget | REJECT — too narrow |
| A21 | LookaRoute | routing | REJECT — narrows to routing |
| A22 | LookaVerdict | judge again | REJECT — same as A4 |
| A23 | LookaSignal | signal detection | weak |
| A24 | LookaFaro | PT: flair/instinct | REJECT — EN meaning lost |
| A25 | LookaCalib | calibration | REJECT — narrow, ugly |

### Family B — sufficiency/measurement concepts (no forced LookA)

| # | Candidate | Rationale | Disposition |
|---|---|---|---|
| B1 | **Suffice** | "minimum sufficient" is the MSI thesis itself | **FINALIST** |
| B2 | **Modicum** | "a modicum of intelligence": the small but sufficient amount | **FINALIST** |
| B3 | Satis | Latin "enough"; pharmacy `q.s.` = quantum satis | REJECT — composer/satis collision (MAJOR) |
| B4 | QuantumSatis | the exact professional term | REJECT — long, Quantum- prefix noise |
| B5 | Tantum | Latin "as much as needed" | weak — opaque |
| B6 | Basta | PT/IT "enough!" | REJECT — EN connotation risk |
| B7 | Iota | the minimal amount | REJECT — "tiny" semantics, no sufficiency |

### Family C — nautical/navigation metaphors

| # | Candidate | Rationale | Disposition |
|---|---|---|---|
| C1 | Ballast | what must be carried | SHORTLIST — negative "dead weight" connotation |
| C2 | Bearing | position + pertinence | SHORTLIST (dupe of A9 concept) |
| C3 | Fathom | depth measure + understand | REJECT — Fathom Analytics/notetaker (MAJOR) |
| C4 | Rudder | steering | REJECT — Rudder automation platform |
| C5 | Quartermaster | decides provisions | REJECT — long |
| C6 | Provisioner | provisions a journey | REJECT — generic infra term |
| C7 | Sounding | measures depth | REJECT — EN overload |
| C8 | Trim | nautical sail-trim; LCC decision word | REJECT — generic, own term |

### Family D — cognition/neuro

| # | Candidate | Rationale | Disposition |
|---|---|---|---|
| D1 | Thalamus | brain's admission gate (filters what reaches the cortex) | SHORTLIST — excellent semantics; PT "tálamo" mismatch |
| D2 | Nous | Greek: intellect | REJECT — Nous Research (MAJOR) |
| D3 | Phronesis | practical wisdom: knowing what's needed | SHORTLIST — heavy, academic |
| D4 | Metis | cunning intelligence | REJECT — Metis bootcamp (MAJOR) |
| D5 | Kairos | the right moment | weak |
| D6 | Synapse | relay | REJECT — saturated |
| D7 | Cortex | — | REJECT — saturated |

### Family E — PT/phonetic plays (Lucas register)

| # | Candidate | Rationale | Disposition |
|---|---|---|---|
| E1 | Tino | PT: good judgment ("ter tino") | SHORTLIST — EN loses meaning; name-like |
| E2 | Siso | PT: sound judgment | REJECT — "siso"=wisdom tooth; SISO acronym |
| E3 | Sagaz | PT: sagacious | weak — brand ambiguity |
| E4 | Decisor | PT/EN: the decision-maker | SHORTLIST — plain |
| E5 | Vero | truth | REJECT — Vero social app |

### Family F — misc instruments/roles

| # | Candidate | Rationale | Disposition |
|---|---|---|---|
| F1 | Arbiter | decides | weak — judge-adjacent |
| F2 | Steward | (standalone form of A18) | weak — generic |
| F3 | Sentinel | watches | REJECT — security-tool saturation |
| F4 | Beacon | guides | REJECT — saturated |
| F5 | Fulcrum | pivot point | weak — Fulcrum app exists |
| F6 | Primer | prepares | REJECT — book/ammo connotation |
| F7 | Preface | — | REJECT |

## 2. Scoring (0–10 per criterion; finalists + shortlist only)

Criteria: MEM memorability · PT pronunciation · EN pronunciation · TC technical
credibility · BF brand fit · SF semantic fit · FE future extensibility · GH GitHub ·
PK package name · PP paper usage.

| Candidate | MEM | PT | EN | TC | BF | SF | FE | GH | PK | PP | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **LookaScope** | 9 | 8 | 9 | 8 | 10 | 9 | 9 | 10 | 10 | 9 | **91** |
| **LookaGauge** | 8 | 6 | 8 | 9 | 10 | 9 | 9 | 10 | 10 | 8 | **87** |
| **Suffice** | 8 | 7 | 9 | 8 | 4 | 10 | 7 | 6 | 5 | 9 | **73** |
| **Modicum** | 8 | 7 | 8 | 8 | 3 | 8 | 7 | 8 | 8 | 8 | **73** |
| **LookaLens** | 8 | 8 | 9 | 7 | 10 | 6 | 6 | 8 | 8 | 8 | **78** |
| LookaAcuity | 7 | 5 | 8 | 8 | 9 | 8 | 8 | 8 | 8 | 7 | 76 |
| LookaBearing | 7 | 6 | 8 | 8 | 9 | 8 | 8 | 8 | 8 | 7 | 77 |
| LookaSteward | 7 | 6 | 9 | 8 | 9 | 8 | 8 | 8 | 7 | 6 | 76 |
| Thalamus | 7 | 5 | 6 | 10 | 2 | 9 | 8 | 7 | 7 | 9 | 70 |
| Phronesis | 6 | 4 | 6 | 9 | 2 | 8 | 8 | 7 | 6 | 9 | 65 |
| Tino | 8 | 9 | 7 | 6 | 6 | 7 | 6 | 6 | 6 | 5 | 66 |
| Decisor | 7 | 8 | 7 | 7 | 3 | 8 | 7 | 7 | 7 | 7 | 68 |
| LookaSense | 8 | 7 | 8 | 6 | 10 | 6 | 6 | 8 | 8 | 6 | 73 |
| Ballast | 7 | 6 | 8 | 8 | 3 | 7 | 7 | 7 | 7 | 7 | 67 |
| LookaAssess | 7 | 6 | 8 | 8 | 9 | 8 | 8 | 8 | 8 | 6 | 76 |

## 3. Shortlist of 10 (post-scoring)

1. LookaScope (91)
2. LookaGauge (87)
3. LookaLens (78)
4. LookaBearing (77)
5. LookaAcuity (76)
6. LookaSteward (76)
7. LookaAssess (76)
8. Suffice (73)
9. Modicum (73)
10. Thalamus (70)

## 4. Final shortlist of 5 — profiles + collision research

Collision methodology: Google/web search (2026-10-02) over GitHub, Hugging Face, PyPI,
npm, papers/arXiv, AI model names and products. Classification: CLEAR / MINOR COLLISION
/ MAJOR COLLISION / REJECT. No legal trademark claims are made; trademark clearance
requires proper legal research before commercial use.

### 4.1 LookaScope — **recommended**

- **Meaning**: an instrument you *look through* to see what a task actually needs;
  "scope" = the boundary of what is required (context scope, task scope).
- **Pronunciation**: PT "luka-skóupi" · EN "LOOK-uh-skope" — natural both sides.
- **LookADev connection**: perfect — `LookA` prefix intact; Lucas phonetics preserved.
- **Technical meaning**: models the -scope instrument family (telescope = long context,
  microscope = block granularity, periscope = looking ahead at risk). Tier names
  `LookaScope-Tiny / -Base / -Large` read like real instruments.
- **Future extensibility**: covers context necessity today, sufficiency/risk/allocation
  tomorrow — "scoping" a task is exactly MSI's question. Not tied to relevance or drops.
- **Weaknesses**: "-scope" may suggest visualization-only at first glance; must brand
  it as an *instrument of judgment*, not a viewer. "Scope" is also a common project word
  (scope creep), but never as `LookaScope`.
- **Collision**: `lookascope` / `LookAScope` — **zero results** on Google, GitHub,
  Hugging Face, PyPI, npm, papers. **CLEAR** (pending final registry checks at freeze).

### 4.2 LookaGauge

- **Meaning**: gauge = to measure/estimate; the model gauges how much context,
  reasoning and verification a task needs.
- **Pronunciation**: PT "luka-gáuge" (the "au" is fine; the j-sound is the only bump) ·
  EN "LOOK-uh-gayj".
- **LookADev connection**: perfect prefix fit.
- **Technical meaning**: estimation instrument — closest to the verb set
  ESTIMATE/RANK/ALLOCATE. Calibration story writes itself ("a gauge must be calibrated").
- **Future extensibility**: MSI estimation horizon fits ("gauging requirements").
- **Weaknesses**: "gauge" spelling is error-prone (gague/gage); PT pronunciation less
  smooth than LookaScope; gauge implies measurement but not *decision*.
- **Collision**: zero results across search. **CLEAR** (pending registry checks).

### 4.3 Suffice

- **Meaning**: "that suffices" — the MSI thesis in one word: minimum *sufficient* context.
- **Pronunciation**: PT "sufáisi" (ok) · EN "suh-FYSS".
- **LookADev connection**: none — loses the family phonetics (falls back to family by
  convention, like LCC/Jev/Laya).
- **Technical meaning**: strongest possible tie to the principal metric
  ("minimum resource usage at matched outcome quality").
- **Future extensibility**: good for context sufficiency, weaker for risk/routing heads —
  the name says "enough context", not "allocate inference".
- **Weaknesses**: generic English verb; package names (`suffice` on PyPI/npm) likely
  occupied by unrelated projects; brand-fit loss is real.
- **Collision**: no AI product/model named Suffice found. Generic-word usage only.
  **MINOR COLLISION** (generic word; expect package-registry squatters).

### 4.4 Modicum

- **Meaning**: "a small but sufficient amount" — "a modicum of intelligence".
- **Pronunciation**: PT "módi-kam" · EN "MOD-ih-kum" — both easy.
- **LookADev connection**: none (family-by-convention option).
- **Technical meaning**: charming fit for a small specialist ("a modicum of judgment
  beats a surplus of generalism" — usable paper framing).
- **Future extensibility**: moderate — emphasizes smallness; MSI allocation semantics
  are second-hand.
- **Weaknesses**: the "small amount" connotation could cap perceived ambition; nothing
  in the word says decisions, context or inference.
- **Collision**: "Modicum AI"/"Modicum model" zero results; bare word used by minor
  brands. **MINOR COLLISION** on the bare word.

### 4.5 LookaLens

- **Meaning**: lens = focus; focusing on the evidence that matters.
- **Pronunciation**: PT "luka-lêns" · EN "LOOK-uh-lenz".
- **LookADev connection**: perfect prefix fit.
- **Technical meaning**: focus/selection metaphor; weaker for allocation/estimation.
- **Future extensibility**: weakest of the five — "lens" suggests view/analysis, not
  decisions about how much intelligence a task needs.
- **Weaknesses**: semantic ceiling; multiple AI products use "Lens" (Google Lens,
  etc.), so it rides a crowded word.
- **Collision**: `#lookalens` — established Thai camera-lens influencer brand across
  TikTok/Instagram/Facebook. Different domain (photography), no AI/software presence.
  **MINOR COLLISION**.

## 5. Verdict (recommendation, not decision)

1. **LookaScope** — best total: family fit, both-language naturalness, extensibility
   past "relevance/compression", clean collision profile, `LookaScope-Tiny/Base/Large`
   naming works, paper-ready.
2. **LookaGauge** — equally clean collisions and arguably tighter semantic fit to
   "estimation"; loses points on PT pronunciation and spelling friction.
3. **Suffice / Modicum** — premium concepts if the family prefix is ever dropped;
   both carry generic-word friction.
4. **LookaLens** — fallback; clear collision issues aside, semantics cap its future.

Decision is deferred to the founder. Freeze protocol before committing the name:
registry checks (GitHub org/repo, PyPI, npm, Hugging Face model+dataset+org), arXiv
title search, and — if commercial use is planned — proper trademark legal research.
