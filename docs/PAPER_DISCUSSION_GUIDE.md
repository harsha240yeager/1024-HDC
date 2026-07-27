# Paper discussion guide — bit-position pruning for HDC on Zynq

Study aid for discussing the submitted manuscript with your advisor. Everything
here is checked against the paper (`Research-paper/conference_101719.tex`), the
RTL, and the committed result files. Where the code says something the paper
does not spell out, it is flagged **[not in the paper]** so you are never
surprised by your own system.

`docs/HDC_Research_End_to_End_Guide.md` is the older pre-results guide. It is
still good on module-level RTL detail but stale on results, level counts, and
project status. This document supersedes it for anything the paper claims.

**Suggested 30-minute structure:** 2 min pitch (§0) → 5 min system walkthrough
(§2, draw the dataflow) → 5 min protocol and why it is strict (§3) → 8 min the
finding and its honest framing (§5) → 5 min hardware evidence (§6) → 5 min
limitations and next steps (§7, §8.7). Lead with §5; that is the paper.

---

## 0. The opening

Memorize a version of this in your own words.

> We built a streaming 1024-bit hyperdimensional computing classifier for EMG
> gesture recognition on a Zynq-7020, verified it bit-exact against a Python
> golden model, and used it to ask a question the HDC pruning literature skips:
> when you keep exactly K of D hypervector bit positions, does *which* positions
> you keep change accuracy on real silicon? It does — informed masks beat
> equal-density random masks by 6.90 points at 128 of 1024 bits. But the
> interesting part is *why*. Only about 200 of the 1024 positions carry any
> information under our encoder, so the win comes from finding that active
> support, not from the cleverness of the ranking score. Six different ranking
> criteria produce interchangeable masks, and a random baseline restricted to the
> active support closes the gap to 1.1 points.

The one-line finding: **support, not score.** That is also the paper's subtitle.

The honest framing of the contribution: a *runtime-selectable, accuracy-
preserving bit-position selector on a fixed-width datapath*, plus the negative
result that it buys no area or energy — not an accelerator that exploits
compression.

---

## 1. HDC fundamentals you should be able to derive on a whiteboard

### 1.1 Why high dimension works

A hypervector is a random binary vector of dimension `D = 1024`. Two independent
random binary hypervectors agree on each bit with probability ½, so their Hamming
distance is `Binomial(D, ½)`: mean `D/2 = 512`, standard deviation
`√D/2 = 16`. Any two random vectors sit 512 ± 16 apart, so a vector that is
genuinely related to a stored one (say 300 away) is unmistakable. This is
*quasi-orthogonality*: in high dimension, random vectors are nearly always far
apart, which is what makes a nearest-prototype search robust to noise and bit
flips. Being able to state this with the numbers is the single most useful thing
in an HDC discussion.

### 1.2 The three operations, and our instantiation

| Operation | Generic role | Ours |
|---|---|---|
| **Bind** | combine role with filler, output dissimilar to both | bitwise XOR (`xor_permute_top.sv`) |
| **Permute** | make position/order matter | `permute_stage.sv`, mode 2 with parameter = feature index |
| **Bundle** | superpose many vectors into one, output similar to all | bitwise majority vote across 20 vectors, `CNT_W = 6` counters (`bundle_unit.sv`) |
| **Similarity** | compare | masked Hamming distance, five-class argmin (`popcount_am.sv`) |

Bind is its own inverse (XOR twice returns the original), which is why XOR-based
HDC is cheap: no multipliers, no DSPs, no BRAM in our design.

### 1.3 Why FPGA

The whole inference is XOR, popcount, majority, and compare — bitwise and
massively parallel, with no floating point and no multiply. That maps to LUTs far
better than to a CPU, which has to loop over 64-bit words. Our measured gap is
about 175× in latency against the same board's ARM core (§6.1).

### 1.4 Training is bundling, not gradient descent

There is no backpropagation anywhere. For each of the five gesture classes, you
encode every TRAIN window of that class and majority-bundle them into one 1024-
bit **prototype**. Five prototypes, 640 bytes total. Training happens offline in
Python; the FPGA only does inference, plus prototype and mask loading over
AXI4-Lite. If asked "where is the learning?", the answer is: in the bundling
step, and it is one pass over the training data.

---

## 2. Our pipeline, one window at a time

### 2.1 The dataset and what a "window" actually is

UCI EMG hand-gesture corpus (via Rahimi's GPLv3 HDC-EMG release), 4 channels, 5
gesture classes. Features are the **enveloped EMG amplitude**, not Hudgins
features. The envelope is quantized to an integer scale 0–21 (`EMG_MAXL = 21`,
which is the "21 levels" in the protocol table).

Two details you must know, because they are where a sharp question will land:

1. **A "window" is one time sample**, classified stride-1. That is why the S1–S5
   TEST split has 493,512 windows: it is per-sample classification, not
   segment-level gesture recognition.
2. **[not in the paper]** The encoder consumes a 4×5 grid of level indices
   (`n_channels = 4`, `n_features = 5`, 20 slots). The export path
   (`level21_to_grid` in `scripts/export_emg_board_vectors.py`) rescales each
   channel's 0–21 level onto the 16-entry value item memory and then **writes
   that same level into all five feature slots of that channel**. So the feature
   axis carries no additional information: per window there are only four
   distinct level values. Every Python experiment and the board export use this
   identical function, so nothing is inconsistent between platforms — but the
   deployed encoder is effectively a 4-record spatial encoder wearing a 20-bind
   coat.

Point 2 is not a defect to hide, and it explains a headline number: it is why the
encoder ablation shows 20 binds (72.89%) ≈ 4 binds (73.28%). Note that it does
*not* explain the small active support — measured support is nearly the same
with independent per-slot levels (§5.2), so do not conflate the two.

Note the two level counts and do not mix them up: **21** is the dataset envelope
quantization; **16** is the size of the value item memory the RTL indexes, hence
4-bit level codes and an 80-bit window (20 slots × 4 bits, sent as three 32-bit
AXI4-Stream beats).

### 2.2 Encode

For each of the 20 (channel `c`, feature `f`) slots, with level `v`:

```
pair[c,f] = channel_HV[c]  XOR  value_HV[v]  XOR  permute(feature_HV[f], mode=2, param=f)
query     = majority_vote( all 20 pair vectors )          # 1024 bits
```

The three item memories are ROMs generated from a seeded RNG (deployed seed 42).
`channel_HV` and `feature_HV` are uniform random. `value_HV` is a **continuous**
(level-correlated) table: adjacent levels differ in roughly `D/levels = 64` bits
so that similar amplitudes give similar hypervectors. That correlation is
deliberate and it is central to §5.2.

### 2.3 Classify

```
d_k = popcount( (query XOR prototype_k) AND mask )        k = 1..5
prediction = argmin_k d_k                                 ties → lowest index
```

The mask is a 1024-bit global register. A cleared bit is excluded from every
distance. Identical first-index-on-tie rule in RTL and Python — this was
checked, and it is why board and Python predictions match label for label.

### 2.4 What pruning means here

Pruning = clearing bits in that mask. Keep ratio ρ keeps `K = round(ρ·D)`
positions. keep = 0.125 → 128 of 1024 bits. Crucially, the mask is loaded over
AXI4-Lite at runtime, so changing the keep ratio needs **no resynthesis, no
bitstream reload, and no retraining** — that is the "RT" column in the prior-work
table, and no compared work has it.

Equally crucially, and stated plainly in the paper: `popcount_am` XORs the full
1024-bit words and *then* clears masked bits, so the synthesized datapath is
identical at every keep ratio. Pruning changes arithmetic, not hardware.

### 2.5 PS/PL split and interfaces

```
      ┌─────────────── PS (Cortex-A9, bare metal) ───────────────┐
      │ EMG windows staged in DDR                                │
      │ scatter-gather AXI DMA descriptor ring                    │
      │ prototypes + 1024-bit mask via AXI4-Lite (32-word stage)  │
      └────────────┬──────────────────────────┬──────────────────┘
                   │ AXI4-Stream (3 × 32-bit) │ AXI4-Lite
                   ▼                          ▼
      ┌──────────── PL (xc7z020, 100 MHz) ───────────────────────┐
      │ hdc_stream_wrapper → encoder_top (item_mem ROMs,          │
      │   xor_permute_top, bundle_unit) → popcount_am → argmin    │
      └───────────────────────────────────────────────────────────┘
                   │ AXI4-Stream out: class index + distance
```

- **AXI4-Lite** is the low-rate control/configuration path: single-word
  register reads and writes, used for prototypes, mask, and status. Simple,
  addressable, slow.
- **AXI4-Stream** is the high-rate data path: no addresses, just a valid/ready
  handshake carrying beats. Used for windows in and results out.
- **Scatter-gather DMA** lets one call move a whole batch described by a
  descriptor ring, so the PS is not involved per window.

Core compute latency is roughly 20 bind cycles plus a few for bundling and one
for the associative memory — order 25 clock cycles. Everything above 4.6 µs per
window is PS-side and DMA overhead, not the pipeline (§6.1).

---

## 3. Protocol HDC-2, and why the boring part matters

Be ready to defend the protocol before the results, because a methods-minded
advisor will start there.

The earlier protocol allowed train and test windows to come from the same
recording with overlap; with stride-1 sample classification, adjacent windows are
nearly identical, so that leaks. **HDC-2** fixes everything a priori:

| Item | Specification |
|---|---|
| Split | first 25% of each class per subject for TRAIN, remaining 75% for TEST |
| Overlap audit | index intersection must be exactly 0 (`audit_split_leakage.py`) |
| Silicon cohort | S1–S5, 493,512 TEST windows, 72.78% pooled export reference |
| Python cohorts | 5-subject cross-subject pilot; 36 subjects (S1–S18 → S19–S36) |
| Metrics | spatial mean (Python/ARM) vs pooled window (board) — never mixed |
| Bit-exact gate | every board label matches the golden model on a 200-vector batch |
| Board accuracy gate | \|board − export reference\| ≤ 0.5 pp over all TEST windows |
| Iso-density target | informed − random ≥ 5 pp at keep = 0.125 |
| Cross-subject target | \|local oracle − pooled\| ≤ 3 pp |

Two things to emphasize: **the thresholds were fixed before the results were
interpreted** (this is pre-registration, and it is why the +6.90 pp result is a
pass rather than a post-hoc story), and **two accuracy definitions exist**.
Spatial mean is the unweighted per-subject average; pooled is correct labels over
all windows. They differ by ~0.13 pp on S1–S5 (72.65% vs 72.78%) because
subjects contribute unequal window counts. Mixing them is a classic reviewer
catch, so the paper states which is which everywhere.

---

## 4. What you actually did, in order

Each stage has a gate; the gate is the reason the next stage is trustworthy.

1. **Python golden model** (`python_ref/hdc_ref.py`) — reference semantics for
   permute, bind, bundle, distance, and mask construction.
2. **RTL, bottom up** — item memory, binder, permute, bundler, popcount,
   associative memory, then AXI4-Lite and AXI4-Stream wrappers.
   *Gate:* nine co-simulation harnesses, each bit-for-bit against the golden
   model on directed and randomized stimuli.
3. **Bring-up on ZedBoard** in three phases (AXI4-Lite polling → DMA one
   transfer per window → scatter-gather batch).
   *Gate:* every predicted label matches the golden model on a 200-vector batch
   exercising both the single-window and DMA paths.
4. **Full-cohort replay** — all 493,512 HDC-2 TEST windows on hardware.
   *Gate:* board accuracy reproduces the frozen export reference within 0.5 pp.
   Achieved: Δ = 0.00 pp at 72.78%.
5. **Experiments** — design-space sweep (D, CNT_W, keep), three silicon anchors,
   iso-density ablation over 30 seeds, five extra ranking criteria, item-memory
   seed sensitivity, cross-subject transfer on 5 and then 36 subjects, ARM
   software baseline, INA219 energy campaign.
6. **Artifact** — `scripts/check_paper_numbers.py` re-derives all 66 numerical
   claims in the paper from committed files and fails if any drifts;
   `scripts/reproduce_paper.sh` reruns the Python pipeline in tiers.

If asked "how do you know the board is really running your algorithm?", the
answer is the two-level gate in steps 3 and 4: per-window label equality on a
200-vector batch, plus cohort accuracy equality on half a million windows.

---

## 5. The finding, and how to frame it

### 5.1 The three-number story

At keep = 0.125 (128 of 1024 bits), Python, S1–S5:

| Mask | Spatial mean | vs informed |
|---|---|---|
| Informed (Fisher) | 72.65% | — |
| Random over all 1024 positions (30 seeds) | 65.75% ± 3.20 | **−6.90 pp** |
| Random restricted to the active support | 71.45% | **−1.13 pp** |

Same kept-bit count in every row — that is what *iso-density* means, and it is
what the pruning literature usually fails to control. If you only compare
against random-over-everything, you would conclude the Fisher score is doing the
work. The third row shows most of the gap was simply the random baseline wasting
its budget on positions that never change.

Statistics, subject as the unit of analysis (n = 5): all five paired gaps
positive (+1.79 to +11.32 pp), subject-bootstrap 95% CI [+4.04, +9.76] excludes
zero, one-sided Wilcoxon p = 0.031 (the exact floor at n = 5), paired t-test
p = 0.0077. On hardware, one random-mask seed gives +10.33 pp (72.84% vs
62.51%) — a confirmation, not an independent estimate, because it is one seed.

### 5.2 Why the active support is so small — the mechanism

This is the question worth preparing hardest, because it *is* the paper.

**What is measured:** `active_bit_support` counts positions that are not constant
across a set of hypervectors. In `run_seed_sensitivity.py` it is applied to the
pooled TRAIN+TEST encoded queries of one subject. Result: **168–239 per subject,
mean 203–210 across item-memory seeds {1, 7, 21, 42}**. Note it is a
sample-dependent count — it can only grow as you include more windows — which is
why the ranking run (subsampled TEST) reports 208.8 while the full split reports
209.8.

**Where the ceiling comes from.** The value item memory is built by interpolating
between two random endpoints `v_min` and `v_max`: level ℓ copies a randomly
chosen subset of the ≈512 positions where the endpoints differ, sized
`ℓ·(D/levels)/(levels−1)`. Any position outside the union of those sampled
subsets is identical at every level, so no input can ever change it. Channel and
permuted-feature hypervectors enter as input-independent XOR *constants*, and XOR
with a constant cannot make a fixed position vary. So the encoder's structural
ceiling is exactly the value table's varying set.

**[not in the paper] Measured, for the deployed configuration** (D = 1024, 16
levels, seed 42). The ceiling takes four lines to reproduce, which is handy if he
wants to see it rather than hear it:

```python
from hdc_ref import HDCConfig, ItemMemory, active_bit_support
cfg = HDCConfig(D=1024, seed=42)
print(active_bit_support(ItemMemory(cfg).value))   # 327
```

| Quantity | Positions |
|---|---|
| Value-table varying set — the structural ceiling | **327** of 1024 |
| Bundled queries, uniform random envelope samples | 326 |
| Bundled queries, independent per-slot levels | 316 |
| Bundled queries, real pooled data (the paper's figure) | 203–210 |

Two conclusions to carry into the meeting. First, the ceiling is the value
table, not the bundling: the query support (326) is essentially the table's
support (327), so the paper's phrase about "20-way majority bundling collapsing
weakly contested bits" is directionally right but not the operative cause. The
subsets are re-drawn independently per level rather than being nested, which is
what lifts the union to ~327 instead of the ~64 that the paper's "~D/n_levels
flips" phrasing suggests. Second, the gap from 327 down to ~209 is **data
coverage**: real EMG envelopes do not exercise every level combination, so a
subject's windows light up only about two-thirds of the reachable positions.

Everything else in the paper follows from a support of a few hundred: keep = 0.5
is lossless because 512 kept bits comfortably covers ~209 live ones; six
unrelated criteria tie because any of them prefers live positions over frozen
ones; and uniform random selection fails because at 128 bits it expects only
~26 live positions.

A nested (thermometer) value table would be a cleaner design and would make the
support smaller and more predictable. Getting a *denser* support needs a
different encoder — Stage-B records — which is exactly the falsification test in
§5.5.

### 5.3 Ranking baselines — the result that reframed the paper

Six criteria at keep = 0.125: Fisher, per-bit variance, mutual information with
the label, class-mean separation, prototype disagreement, per-bit entropy.
Variance and entropy turn out to be the *same* ranking (for a binary position
with mean p, both are monotone in how far p sits from ½), so there are five
distinct criteria. Those
five select visibly different masks — mean Jaccard against the Fisher mask spans
0.18–0.95 — yet all six predict identically on *every* test window of every
subject, giving 72.58% throughout. Even a mask sharing only 11% of its positions
with Fisher's produces the same labels.

That is why the paper is titled "support, not score" and why the original
Fisher-centric framing was dropped. Do not oversell the criterion; the honest
claim is iso-density support identification.

### 5.4 Cross-subject transfer

A pooled mask from S1–S3 evaluated on held-out S4–S5 at keep = 0.125 gives
66.64% against a 67.66% local oracle: a +1.02 pp gap, inside the pre-specified
3 pp bound. Because five subjects at one keep ratio is weak, the same bound was
stressed on all 36 subjects with an 18/18 split across a 32–256-bit grid. Pooled
masks are lossless for keep ≥ 64 (0.00 pp gap against a 59.87% unpruned
baseline). The bound only bites at keep = 32, below the support size, where
pooled *beats* the local oracle by 2.59 pp — consistent with pooling acting as a
regularizer when per-subject scores come from few TRAIN windows. Absolute
accuracies differ between cohorts because the 36-subject path uses different
preprocessing, so only within-cohort gaps are compared.

### 5.5 What would falsify the claim

Worth volunteering, because it shows you know what the experiment does not prove:
run the same ablation under a **dense-support encoder** (the Stage-B binding
records, ~90% accuracy). If informed and support-restricted random still tie
there, bit-position discriminability genuinely does not matter and the
contribution shrinks to a hardware/protocol one. If they separate, criterion
quality does matter and the current null is an artifact of this encoder. The
paper names this as the open question.

---

## 6. Hardware evidence

### 6.1 Latency — and the anomaly to explain

| Phase | Interface | Per-window |
|---|---|---|
| 1 | AXI4-Lite polling | 3 µs |
| 2 | AXI DMA, one transfer per window (10,000-window run, 74.7 ms) | 7.5 µs |
| 3 | AXI DMA scatter-gather batch (926 µs / 200 windows) | 4.6 µs |

The obvious question: why is the 10,000-window run *slower* per window than the
200-window batch? Because the phases differ in **how a window is submitted**,
not in batch size. Phase 2 issues one DMA transfer per window and pays setup
every time; Phase 3 amortizes one scatter-gather descriptor ring across the
batch. Related: a *lone* window on the scatter-gather path costs 58 µs, because
allocating and flushing a descriptor ring dominates. So the honest system claim
is 4.6 µs/window at batch, 3 µs single-window over AXI4-Lite, and 58 µs if you
misuse the batch path for one window.

### 6.2 Area and timing

Post-route on xc7z020 for the DMA path: 35,206 LUTs (66.2%), 27,639 FFs, zero
DSP, zero BRAM. **Slice occupancy is the binding constraint at 96.3%**, which is
why D = 2048 does not fit — not LUT count. Runs at the 100 MHz PS clock;
out-of-context synthesis of the D = 1024 core closes that period with +0.78 ns
worst setup and +0.26 ns worst hold slack, zero failing endpoints, i.e. roughly
108 MHz achievable.

### 6.3 Energy — know this cold, it is the softest part of the paper

Measurement: whole-board 12 V input at the ZedBoard J21 shunt (10 mΩ) with a TI
INA219, 128-sample averaging, ~100 Hz effective rate, scaled by a one-time idle
multimeter calibration.

The problem: the PL batch takes 0.93 ms, which is **under a tenth of one INA219
sample**. Across nine PL runs the apparent elevation above idle averaged 50 mW
with a 90 mW standard deviation, went negative in three runs, and was
statistically indistinguishable from zero (p = 0.13, n = 9). So the active
increment is simply not resolvable for the PL.

What is therefore reported, for every µJ/window figure in the paper:

```
E = P_idle × t_batch          e = E / N
```

an **idle-calibrated lower bound** on whole-board energy that excludes the
unresolved active increment. The exclusion is small and conservative: the point
estimate would add 2.0% to the PL figure and 5.3% to ARM (whose 164 ms batch is
long enough to resolve an increment — 111 ± 61 µJ/window, 2199 inclusive).

Results: PL 11.98 ± 0.07 µJ/window, ARM 2088 ± 6 µJ/window, n = 3 runs each.
The ~174× energy ratio and the ~176× latency ratio are **the same measurement in
different units** (both platforms are idle-dominated; the ratio differs only by
the 0.99 idle-power ratio). The paper says this explicitly and never presents
the energy ratio as independent evidence. If he asks whether you measured energy
efficiency: no, you measured a latency ratio and a board power level, and you
labelled it accordingly.

### 6.4 Positioning against prior FPGA HDC

| Work | Device / task | Area | Efficiency | Runtime keep change |
|---|---|---|---|---|
| Schmuck 2019 | Virtex US, EMG 5-class | 18.3k CLB | 4.7 M win/s | no |
| SparseHD 2019 | Kintex-7, ISOLET | not reported | 48.5× energy vs GPU | no |
| Antonio 2022 | gate-level, digits | +6–18% | 14–66% energy (simulated) | no |
| This work | xc7z020, EMG 5-class | 35.2k LUT (66.2%) | 11.98 µJ/w (l.b.), 216k win/s (sys.) | **yes** |

The rows are heterogeneous — different families, datasets, CLB vs LUT,
simulated vs measured, core vs system throughput — and the caption says so.
Two defensible statements: among these works, ours is the only entry reporting an
absolute whole-board energy figure against a same-board software baseline, and
the only one whose kept-bit count changes without resynthesis or retraining.
Schmuck leads on raw throughput, but that is a *core* number while ours is
*system-level*, dominated by PS-side DMA batching rather than the PL pipeline.
Say that before he does.

---

## 7. Limitations — state these first, do not be caught by them

1. **No hardware benefit from pruning.** Keep ratio cuts enabled Hamming bits
   1024 → 128 with no accuracy loss, but LUT count, latency, and board joules do
   not move. Architectural first (full-width XOR before masking, so the
   synthesized datapath is identical), measurement-limited second (a
   mask-dependent saving could only appear in a dynamic increment below the
   ~2% resolution floor). The paper claims no mask energy effect *in either
   direction*. This is the main acceptance risk.
2. **Single-seed silicon.** The +10.33 pp board figure uses random-mask seed 0
   only; further seeds need JTAG mask reprogramming. It is a confirmation of a
   Python effect, not an independently powered silicon estimate.
3. **Five subjects for the statistical claim.** n = 5 is the unit of inference,
   which puts the Wilcoxon at its exact floor (p = 0.031).
4. **The 36-subject grid is Python-only**, and its preprocessing differs from the
   board cohort, so absolute accuracies are not comparable across cohorts.
5. **Absolute accuracy is ~73%, not ~90%.** That is the deployed RTL encoder, not
   the Stage-B BSC reference. The ablation attributes the ~17 pp gap to item
   memory and bind structure, not to the protocol, the seed, the level count, or
   a DMA/classification bug. It is orthogonal to the bit-selection question, but
   it does mean the study runs on a weak encoder.
6. **Energy is whole-board and idle-calibrated**, a lower bound. Isolating the PL
   rail needs a board modification.

---

## 8. Anticipated questions, with answers

### 8.1 Fundamentals

**Why 1024 dimensions?** Device constraint plus sufficiency. D = 2048 does not
fit xc7z020 (slice occupancy already 96.3% at 1024), and accuracy at D = 1024
with CNT_W ≥ 4 is flat in the sweep, so more dimensions were not buying
anything on this encoder.

**Why binary rather than bipolar/integer HDC?** Binary makes bind an XOR and
similarity a popcount, so no DSPs and no BRAM are needed. The paper's MAP
bipolar parity anchor exists in the reference config for comparison only.

**Why 6-bit bundling counters?** 20 vectors need a count to 20, so 5 bits would
suffice; CNT_W = 6 leaves margin and the sweep shows accuracy is flat for
CNT_W ≥ 4.

**What happens on a distance tie?** Lowest class index wins, in both RTL and
Python. This was checked explicitly, and it is why predictions match label for
label rather than only on average.

### 8.2 Encoder and accuracy

**Why only ~73% when the reference implementation gets ~90%?** Different
encoder. Stage-B BSC bundles four-channel bind *records* and reaches 89–91%
under the same protocol; the deployed RTL encoder uses the channel–feature–value
grid and reaches 72.89%. The Path-B ablation isolates it: item memory and bind
structure account for ~17 pp, while protocol, seed, and level count account for
~1 pp. Not a bug, an encoder design choice — and the bit-selection question is
orthogonal to it.

**What are your five "features"?** Be straight about this. The grid has five
feature slots per channel, but the export path replicates each channel's single
enveloped level across all five, so per window there are only four distinct
values. That is why 20 binds (72.89%) and 4 binds (73.28%) perform the same in
the ablation. Real per-feature content — Hudgins features, or several time
samples per window — is the obvious next encoder step and would also give the
dense support that §5.5 needs.

**Then why keep 20 binds in the RTL?** It costs nothing in accuracy, it exercises
the full permute-and-bundle datapath that a richer encoder would need, and the
deployed configuration was frozen for bit-exactness before the redundancy was
characterized. Changing it now would invalidate the frozen export reference.

**Is 21 or 16 your level count?** Both, at different stages: the envelope is
quantized 0–21, then rescaled onto a 16-entry value item memory, giving 4-bit
level codes and an 80-bit window. Worth a clarifying half-sentence in the paper.

**Why not just use a small neural network?** On accuracy alone an MLP wins: the
Python MLP in Figure 2 reaches 93.0%, which is why it is drawn as a
context-only ceiling and excluded from every claim. The HDC case is not peak
accuracy but the cost profile: one-pass training by bundling, five 1024-bit
prototypes as the entire model (640 bytes), no multipliers, no DSPs, no BRAM,
and robustness to bit errors from quasi-orthogonality. The MLP has not been
deployed on the board, so any comparison would be Python-versus-silicon and the
paper does not make one.

### 8.3 The main claim and statistics

**Isn't your contribution just "don't select frozen bits"?** That is close to
the honest reading, and the paper says so: it is iso-density *support
identification*, not evidence that Fisher beats other criteria. What is new is
demonstrating it on a verified silicon datapath with a fixed kept-bit count,
which the pruning literature does not control, and quantifying how much of an
apparent "informed selection" win is really support discovery (5.8 of the 6.9
points).

**Why exactly ~209 positions? Where does that number come from?** Two factors,
and it is worth separating them (§5.2). The structural ceiling is the value item
memory: only 327 of 1024 positions can ever change under any input for the
deployed seed, because the continuous table only ever modifies positions inside
the sampled difference set between its two random endpoints. Everything else is
an input-independent XOR constant. The remaining drop from 327 to ~209 is data
coverage — real envelopes do not exercise every level combination. Also flag that
the metric is sample-dependent: it can only grow with the number of windows
included, which is why the paper quotes 208.8 on a TEST subsample and 209.8 on
the full split.

**Why is n = 5 enough?** It is not, for a strong claim, which is why the paper
reports the subject-level bootstrap CI, the Wilcoxon at its exact floor, and the
paired t-test together, and labels the silicon run confirmatory. The 36-subject
grid exists precisely because the 5-subject pilot is weak evidence.

**Why 30 seeds for the random baseline?** To characterize the random mask
distribution (65.75% ± 3.20), so the informed result is compared against a
distribution rather than one lucky or unlucky draw.

**Could the mask be overfitting to test data?** No. Fisher scores are computed on
TRAIN queries only, with a documented zero-index-overlap audit between splits.

### 8.4 Hardware and implementation

**What is your maximum frequency?** 100 MHz deployed, ~108 MHz from OOC
synthesis of the D = 1024 core (+0.78 ns worst setup slack, zero failing
endpoints). Not pushed further because the PS clock is 100 MHz and the bottleneck
is DMA, not the PL.

**Where does the 4.6 µs actually go?** Almost entirely PS-side and DMA. Core
compute is order 25 cycles ≈ 250 ns at 100 MHz. See §6.1 for the three
submission modes.

**Why is scatter-gather slower for a single window (58 µs)?** Descriptor ring
allocation and cache flush dominate; there is nothing to amortize.

**Can you clock-gate the masked lanes to get real savings?** Not in this design,
and that is the acknowledged next step. `popcount_am` XORs full 1024-bit words
before applying the mask, so nothing is idle to gate. Getting a real benefit
needs either clock-gated popcount lanes or a physically narrower compare tree,
plus PL-rail sensing to measure it.

**Why 66% LUT utilization for such a simple datapath?** 1024-bit wide XOR,
majority, and five parallel popcount trees, plus the DMA and AXI infrastructure.
Slices, not LUTs, are the real limit at 96.3%.

### 8.5 Energy

**Is 11.98 µJ/window measured?** It is an idle-calibrated lower bound: measured
idle board power times measured batch duration, divided by window count. The
active increment is excluded because a 0.93 ms burst is unresolvable at the
INA219's ~100 Hz rate (50 ± 90 mW apparent, p = 0.13, n = 9). Every energy
number in the paper is this quantity, and it is labelled that way in the
abstract, tables, captions, and figure axis.

**Then is the 175× energy advantage real?** It is real under that definition,
but it is not independent evidence: both platforms are idle-dominated, so the
energy ratio is the latency ratio scaled by the 0.99 idle-power ratio. One
measurement, two units. The paper never presents them as separate results.

**Is the ARM baseline fair?** Cortex-A9 with hard-float at `-O2`, same board,
same protocol, same windows, 72.65% spatial mean versus 72.78% pooled on PL, so
accuracy agrees within 0.13 pp. It is not NEON-hand-optimized, and a NEON
popcount implementation would narrow the gap — worth conceding as future work.

**Why not just measure the PL rail?** It needs a board modification to break out
the PL supply. Listed as future work alongside multi-seed silicon.

### 8.6 Novelty and positioning

**What is genuinely new?** Three things, in the order the paper claims them: a
bit-exactly verified streaming HDC accelerator with full-cohort silicon replay
(493,512 windows, Δ = 0.00 pp); a controlled iso-density study of bit-position
selection on that silicon, with the mechanism identified rather than just the
effect; and a runtime-programmable mask that changes the kept-bit count with no
resynthesis or retraining, which no compared work offers.

**How does this differ from SparseHD or dimension pruning?** Those change
sparsity level or retrain, so a reported gain can come from the sparsity level
itself rather than from *which* positions were kept. Fixing K and comparing
informed against random at equal density is what isolates the position question.

**Why does this belong at a design-automation venue?** It is a silicon-verified
study with a reproducible protocol and a machine-checked artifact, and its main
practical message is a negative one useful to hardware designers: logical bit
masking does not buy area or energy on a fixed-width datapath, so if you want
savings you must narrow or gate the datapath.

### 8.7 Next steps to propose

Have these ready, ordered by cost:

1. **Dense-support encoder** (Stage-B records or real per-feature content) and
   rerun the iso-density ablation — this is the scientifically decisive one and
   it is pure Python.
2. **Multi-seed silicon** (random-mask seeds 1–9 via JTAG mask reprogramming) to
   turn the +10.33 pp point into a distribution.
3. **Clock-gated popcount lanes or a narrow 128-bit configuration** to convert
   the mask into a measurable area/energy win.
4. **PL-rail sensing** at burst timescales, so energy stops being a lower bound.
5. **NEON-optimized ARM baseline** to make the software comparison airtight.

---

## 9. Numbers cheat sheet

| Quantity | Value |
|---|---|
| Dimension / counter width / item-memory seed | 1024 / 6 / 42 |
| Channels, features, levels, binds | 4, 5, 16-entry value table (envelope 0–21), 20 |
| Classes / subjects (silicon) | 5 / S1–S5 |
| TEST windows (silicon cohort) | 493,512 |
| Export reference accuracy | 72.78% pooled (Δ = 0.00 pp on board) |
| Spatial mean, RTL encoder | 72.65% |
| Active support (pooled queries, real data) | 203–210 of 1024 positions |
| Structural ceiling (value-table varying set, seed 42) | 327 of 1024 |
| Iso-density gap, keep = 0.125 | +6.90 pp, 95% CI [+4.04, +9.76] |
| Random over all positions / support-restricted | 64.55% (−8.04) / 71.45% (−1.13) |
| Silicon iso-density gap (seed 0) | +10.33 pp (72.84% vs 62.51%) |
| Anchors A/B/C accuracy | 72.78% / 72.78% / 72.84% |
| Anchors A/B/C energy (l.b.) | 11.98 / 11.90 / 11.81 µJ/window |
| PL latency / ARM latency | 4.6 µs / 818 µs per window |
| PL energy / ARM energy (l.b.) | 11.98 ± 0.07 / 2088 ± 6 µJ/window |
| Speedup / energy ratio | ~176× / ~174× (same measurement) |
| LUT / FF / slice / DSP / BRAM | 35,206 (66.2%) / 27,639 / 96.3% / 0 / 0 |
| Clock / OOC Fmax | 100 MHz / ~108 MHz |
| Cross-subject pilot gap | +1.02 pp (bound ≤ 3 pp) |
| 36-subject grid | 0.00 pp for keep ≥ 64; −2.59 pp at keep = 32 |
| Machine-checked claims | 66 |

---

## 10. Traps — do not say these

| Do not say | Say instead |
|---|---|
| "Fisher selection is better than other criteria" | "All six criteria tie; the win is support identification" |
| "We measured energy savings from pruning" | "Board joules do not move with the mask; we claim no effect either way" |
| "We measured inference energy" | "Idle-calibrated lower bound on whole-board energy" |
| "175× faster and 175× more efficient" | "175× faster, and the energy ratio is that same measurement" |
| "Bit-exact on all 493,512 windows" | "Bit-exact per window on the 200-vector batch and in co-simulation; cohort accuracy matches the reference on the full replay" |
| "Silicon proves the +10.33 pp effect" | "One silicon seed confirms it; the 30-seed Python interval is the effect size" |
| "Our pruning reduces hardware cost" | "Runtime-selectable bit-position compression on a fixed-width datapath" |

---

## 11. Bring these questions to him

1. Is the "support, not score" negative framing strong enough to carry a paper,
   or should the dense-support encoder experiment land *before* submission?
2. The absent area/energy benefit is the main acceptance risk. Attempt the
   clock-gated or narrow-datapath variant now, or defend the negative result?
3. Is the five-subject, one-seed silicon evidence base acceptable, or is
   multi-seed JTAG reprogramming a submission blocker?
4. The deployed encoder's redundant feature axis limits absolute accuracy to
   ~73%. Freeze it for this paper and fix it in the journal version, or re-export
   and re-verify now?
5. Venue and timing: is the current target still the right one given the above?
