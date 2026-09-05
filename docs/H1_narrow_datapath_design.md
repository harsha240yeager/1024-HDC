# H1 — Narrow / gated masked-Hamming datapath: micro-architecture design

**Issue:** [#28](https://github.com/harsha240yeager/1024-HDC/issues/28) (P0, Paper 1) · **Feeds:** #29 (implement+synth), #30 (co-sim), #31 (board eval), #32 (Pareto figure)
**Status:** design complete → #29
**Baseline RTL:** `rtl/popcount_am.sv`, `rtl/pruning_mask.sv` @ `D=1024`, `WORDS=16`, `BITS_PER_WORD=64`, `N_CLASS=8`

> **Selected design: Option E — baked bit-permutation + narrow AM (§5.2).** Hardwire the Fisher-selected
> bit positions into the AM operand routing so the AM is physically 128 bits (2 words) instead of 1024
> (16 words). A synthesis-time permutation is pure wiring (0 LUT), and popcount is invariant to bit
> relabeling, so this is **bit-exact** to the baseline: −85% classify cycles and −45% core flip-flops
> at **provably zero** accuracy cost.
>
> Options A (word-skip), B (clock-gating), C1 (runtime skip) and D (runtime gather) were rejected on
> measurement; C2 (word-blocked mask) was rejected after failing its accuracy gate by −2.31 pp. Those
> negative results are §3 and §5 and are worth reporting.

---

## 1. The objection we have to answer

The paper currently reports pruning that reduces *arithmetic* but not *hardware*: at keep=0.125 we
throw away 87.5% of the bit positions and measure **no** LUT, latency, or energy improvement. A DATE
reviewer will read that as "the mask is free in software and useless in silicon."

The cause is structural, and it is visible in three lines of the baseline:

```140:143:rtl/popcount_am.sv
                S_XOR: begin
                    xor_w <= (query_r[w_idx * BITS_PER_WORD +: BITS_PER_WORD] ^
                              proto[k_idx][w_idx * BITS_PER_WORD +: BITS_PER_WORD]) &
                             mask_in[w_idx * BITS_PER_WORD +: BITS_PER_WORD];
```

The mask is applied **after** a full-width XOR, as a data operand. `mask_in` is a runtime-loadable
register, so synthesis cannot constant-fold anything: all 16 words are always fetched, always XORed,
always popcounted. The datapath is fixed-width by construction and the keep ratio is invisible to it.

Fixing this is what #28 designs.

## 2. Baseline cost model

The classify FSM is `S_XOR → S_ACC` per word, then one `S_CMP` per prototype:

| Quantity | Expression | @ D=1024, N_CLASS=8 |
|---|---|---|
| Classify cycles | `N_CLASS * (2*WORDS + 1)` | **264** |
| Encoder cycles | `N_PAIRS + ~3` | 23 |
| Core cycles/window | encode + classify | **287** (2.87 µs @ 100 MHz) |
| Measured board | DMA batch, `results/phase3/board_batch_bench.txt` | 4.63 µs/window |

Two things follow. First, **the AM owns 92% of core latency** (264 of 287 cycles) — it is the right
block to attack. Second, board latency carries ~1.8 µs of DMA/PS overhead that no RTL change will
remove, so any core speedup is diluted roughly 0.62× end-to-end. #31 must report both numbers.

Area is dominated by state and the operand muxes, not the arithmetic:

| Structure | Cost | Share of core FF (17,784 @ D=1024) |
|---|---|---|
| `proto[0:N_CLASS-1]` | `N_CLASS × D` = 8,192 FF | 46% |
| `query_r` | 1,024 FF | 6% |
| proto read mux | 64 lanes × (`N_CLASS*WORDS`=128):1 | large LUT term |
| query read mux | 64 lanes × 16:1 | moderate LUT term |
| XOR + popcount tree | ~64 + ~40 LUT | negligible |

The popcount tree — the thing "narrow compare" instinctively targets — is a rounding error. **The
win has to come from storage and muxes, or from cycles.** That reframes the whole problem.

## 3. Measured mask geometry (the finding that picks the design)

Whether any word-granular optimisation can work depends entirely on whether whole 64-bit words go
dead. Measured with `scripts/analyze_mask_word_occupancy.py` → `results/narrow_rtl/mask_word_occupancy.json`:

| Mask | keep | Kept bits | **Dead words / 16** | Live bits/word |
|---|---|---|---|---|
| Value-table active support | — | 327 | **0** | — |
| Random iso-density (seeds 0–9) | 0.125 | 128 | **0.0** (max 0) | 8.0 |
| Random iso-density (seeds 0–9) | 0.25 | 256 | **0.0** (max 0) | 16.0 |
| Fisher-ranked | 0.125 | 128 | **0** | min 2, max 13 |
| Fisher-ranked | 0.25 | 256 | **0** | min 7, max 25 |

**Not one word is ever fully dead, at any keep ratio, for any mask family.** This is not bad luck —
the item memory is random, so kept bits are uniformly scattered by construction (P(a 64-bit word is
empty at keep=0.125) ≈ 0.875⁶⁴ ≈ 2×10⁻⁴). Every naive skip-the-dead-word scheme therefore saves
exactly 0%, and the finding is robust rather than seed-specific.

The mask has to be made *structurally* sparse. It will not become so on its own.

## 4. Options considered

### Option A — word-skip on the existing scattered mask · **rejected**
Precompute a 16-bit `word_live` vector at mask-load time; skip `S_XOR/S_ACC` for empty words.
Cost: ~16 FF and a priority encoder. Saving, from §3: **0 cycles, 0 LUT, at every keep ratio.**
Cheap and useless. Worth exactly one sentence in the paper as the measured refutation of the
obvious approach.

### Option B — lane clock/operand gating (issue text "Option B") · **rejected as headline**
Gate `xor_w` flop enables and the popcount tree per masked-off lane.
The `& mask_in` already pins masked lanes to constant 0, so the adder tree downstream sees no
toggling today — most of the theoretical switching saving is **already being captured** by the
baseline. The residual is the 64 `xor_w` flops and the proto mux. Against a ~2.5 W board draw
dominated by static power and the PS, this lands well inside measurement noise, which is consistent
with the flat energy we already measure. Keep it as a near-free add-on inside the chosen design; do
not build a claim on it.

### Option D — runtime gather/compaction network · **rejected**
Compact 1024 scattered bits down to 128 with a **runtime-configurable** permutation so the mask stays
free-choice. Requires 128 lanes × 1024:1 muxing; that is tens of thousands of LUTs on a part where
the full core is 28,600. The compaction network would cost more than the datapath it compacts.

> The word "configurable" is carrying all the cost here. Drop it and the same idea becomes free —
> that is Option E (§5.2), and overlooking the distinction is what made the first pass of this
> document select Option C.

### Option C — word-blocked mask + genuinely narrow datapath · **rejected (see §5)**
Constrain mask selection to whole-word granularity: choose the best `KEEP_WORDS` of 16 words rather
than the best `K` of 1024 bits. Word skipping then works by construction, and — in the
synthesis-time variant — storage and muxes shrink proportionally.

Two variants, both worth building because they occupy different Pareto points:

- **C1 (runtime-programmable).** Keep full 1024-bit `proto`/`query_r`; `pruning_mask` exports a
  16-entry live-word list; the FSM iterates only live words. Wins **cycles and dynamic energy**, no
  area win, mask still reprogrammable over AXI without a rebuild.
- **C2 (synthesis-time narrow).** `KEEP_WORDS` becomes a parameter and the selected word indices a
  parameter array; `proto`, `query_r`, and both muxes are physically `KEEP_WORDS*64` bits wide.
  Wins **area, cycles, and energy**; mask is frozen at synthesis.

## 5. What the word-blocked constraint costs in accuracy — **MEASURED: it fails**

Run: `run_hook_a_sweep.py --mask-granularity word`, D=1024, cnt_w=6, 5 subjects, HDC-2, TRAIN-derived
Fisher scores, all windows (`results/narrow_rtl/word_blocked_hdc2/`, 3,787 s). Compared against the
free-choice arm on the same statistic:

| keep | Words | Free-choice | **Word-blocked** | Δ | ±0.5 pp gate |
|---|---|---|---|---|---|
| 1.0 | 16 | 72.65% | 72.65% | +0.00 pp | PASS (sanity) |
| 0.5 | 8 | 72.65% | 71.73% | −0.92 pp | **FAIL** |
| 0.25 | 4 | 72.65% | 70.34% | −2.31 pp | **FAIL** |
| 0.125 | 2 | 72.65% | 66.14% | −6.51 pp | **FAIL** |

**Word-blocking fails the accuracy gate at every useful keep ratio**, and the design proxy in §5.1
below was badly optimistic (it predicted 0.00 pp at keep=0.25; the truth is −2.31 pp). The gate did
its job: this would have been discovered after the RTL was written.

The proxy failed for the reason flagged when it was built — test-derived Fisher scores let
free-choice exploit per-bit leakage, and word-granular selection cannot. That inflated free-choice
and made the *gap* look small. The lesson for #29/#31: no mask-selection decision gets made on the
cached-cohort proxy again.

This also kills **C1**: runtime word-skipping needs dead words, and §3 measured zero. So C1 saves
nothing and C2 costs too much accuracy. **Both variants of Option C are dead** — see §5.6 for what
replaces them.

### 5.1 Superseded design proxy (kept for the record)

Earlier estimate from `scripts/eval_word_blocked_mask.py` (40k windows, cached-cohort Fisher scores,
unpruned reference 74.28%) — **do not cite; superseded by the table above**:

| keep | Free-choice | Word-blocked | Δ |
|---|---|---|---|
| 0.125 | 77.68% | 73.16% | −4.53 pp |
| 0.25 | 74.28% | 74.28% | 0.00 pp |
| 0.5 | 74.28% | 72.32% | −1.96 pp |

Note free-choice at keep=0.125 (77.68%) exceeding its own unpruned reference (74.28%) — the leakage
tell that should have discounted this table harder at the time.

### 5.2 Option E — **baked bit-permutation + narrow AM · SELECTED**

Option D was rejected for needing a *runtime-configurable* gather (128 lanes × 1024:1 muxes). But the
mask does not need to be runtime-configurable. If `SEL[]` — the list of Fisher-selected positions —
is a **synthesis-time constant**, the gather is not a mux at all. It is a fixed reordering of wires
between the encoder output flops and the AM input flops, which costs **zero LUTs**; on an FPGA a
constant permutation is pure routing.

That reframing is the whole design:

```
narrow_query[i]    = enc_query[SEL[i]]          // fixed wiring, 0 LUT
narrow_proto[k][i] = proto[k][SEL[i]]           // applied offline by software
dist[k]            = popcount(narrow_query ^ narrow_proto[k])   // no mask register
```

**This is bit-exact to the baseline**, because

`Σᵢ (q[SEL[i]] ^ p[SEL[i]]) = Σ_{j∈SEL} (q[j] ^ p[j]) = popcount((q ^ p) & mask)`

— popcount is invariant to relabeling of bit positions, and argmin tie-breaking is by class index and
so unaffected. Verified numerically on real cohort data by
`scripts/verify_narrow_gather_equivalence.py` → `results/narrow_rtl/narrow_gather_equivalence.json`:
**0 distance-vector mismatches and 0 prediction mismatches over 20,000 windows at keep ∈ {0.125,
0.25, 0.5}.**

The consequence is that **there is no accuracy gate left to clear.** Option E keeps the *free-choice*
Fisher mask, so it inherits the free-choice accuracy exactly — and §5.5 shows that number is flat at
72.65% all the way down to keep=0.125. Option E at K=128 bits is a **2-word AM** with the accuracy of
the full 16-word design.

| | C2 (word-blocked) | **E (baked permutation)** |
|---|---|---|
| Mask freedom | word granularity only | **free choice (any 128 positions)** |
| Accuracy @ keep=0.125 | 66.14% (−6.51 pp) | **72.65% (−0.00 pp, bit-exact)** |
| Accuracy @ keep=0.25 | 70.34% (−2.31 pp) | **72.65% (−0.00 pp, bit-exact)** |
| Gather cost | none needed | 0 LUT (fixed wiring) |
| Mask reprogrammable | no (synthesis) | no (synthesis) |
| AM mask register | required | **not required** |

E strictly dominates C2: same synthesis-time restriction, but zero accuracy loss instead of −2.31 pp,
and it can go all the way to 2 words where C2 could not. It also *removes* hardware — with `SEL`
baked in, the AM needs no `mask_in` port and no 128-bit mask compare, so `pruning_mask` drops out of
the narrow build entirely.

**Cost of the restriction.** The mask is frozen at synthesis, so changing the keep ratio or retraining
the mask needs a rebuild. This is ordinary compile-time specialisation for an FPGA accelerator, and it
is the honest framing: we are not claiming a runtime-reconfigurable sparse engine. Nothing in the
option space delivers runtime reconfigurability *and* a hardware win — A, B, and C1 all measured to
zero saving, and D costs more than it saves. That negative result is itself worth one paragraph in
the paper.

### 5.3 The comparator that decides whether this is publishable

A baked narrow AM datapath invites the obvious reviewer objection: *"that is just a smaller D with
extra steps."* It has to be answered with the iso-width baseline, not the D=1024 baseline. Pooled HDC-2
accuracy from `results/protocol_v2/hook_a/sweep_results.json` (`cnt_w=6`, 5 subjects, free-choice
Fisher masks):

| D | keep=1.0 | keep=0.5 | keep=0.25 | keep=0.125 |
|---|---|---|---|---|
| 256 | 69.82% | 69.82% | 69.82% | 69.26% |
| 512 | 72.72% | 72.72% | 72.72% | 72.72% |
| **1024** | **72.78%** | 72.78% | **72.78%** | 72.78% |
| 2048 | 76.45% | 76.45% | 76.45% | 76.45% |

Free-choice Fisher at D=1024 is **completely flat** across the keep axis — 72.65% spatial-mean
(72.78% pooled) at keep=1.0, 0.5, 0.25 *and* 0.125. There is no accuracy price for pruning at all in
the free-choice regime, and Option E inherits that number bit-exactly (§5.2). So the operating point
is the most aggressive one:

**Option E at K=128 bits (2-word AM) → 72.65% / 72.78%, versus D=256 encode-and-classify → 69.82%.**
That is **+2.83 pp at half the AM width**, or read the other way, the same accuracy as the full
16-word design with 1/8 of the AM.

Paper 1 gets two claims that stand on their own:

1. **vs D=1024 baseline — iso-accuracy efficiency.** Bit-exact identical predictions with a 2-word
   instead of 16-word AM: −85% classify cycles and a proportional cut in AM storage, at **zero**
   accuracy cost. Not "within noise" — provably identical.
2. **vs D=256 baseline — iso-width accuracy.** +2.83 pp at half the AM width, for the cost of a
   wider encoder.

Claim 1 is the headline; claim 2 is what stops the "just use a smaller D" rebuttal. Both must appear
in the #32 Pareto figure, which therefore needs **three** curves: D-sweep, keep-sweep at D=1024, and
the narrow-RTL points.

> **No accuracy gate remains.** The word-blocked gate (§5) was needed because C2 changed the mask;
> Option E does not change the mask, so §5.2's bit-exactness proof replaces the gate. What #29 must
> verify is *implementation* equivalence in RTL, not accuracy — see §8.

## 6. Micro-architecture spec (Option E)

### 6.1 `sel_table` — the baked gather

A generated package holds the selected positions as synthesis-time constants:

```systemverilog
package hdc_sel_pkg;
    localparam int K_BITS = 128;                 // kept bits (= keep_ratio * D)
    localparam int K_WORDS = 2;                  // ceil(K_BITS / 64)
    localparam int SEL [0:K_BITS-1] = '{ 3, 17, 42, /* ... */ };  // from Fisher mask
endpackage
```

Generated by a new `scripts/gen_sel_table.py` from the same `.npy`/`.mem` mask artefact the Python
pipeline already produces, so RTL and golden model cannot drift.

`pruning_mask` is **not instantiated** in the narrow build. There is no runtime mask, so no mask
register file, no `mask_in` port, and no AND-with-mask term. The block is retained unchanged for the
baseline build.

### 6.2 Gather wiring in `hdc_core_top`

```systemverilog
logic [K_BITS-1:0] enc_query_narrow;
for (genvar i = 0; i < K_BITS; i++)
    assign enc_query_narrow[i] = enc_query[hdc_sel_pkg::SEL[i]];
```

A constant-indexed assign per bit: no logic, just routing between the encoder output flops and the AM
input flops. Prototypes arrive already gathered — software applies `SEL` when it packs them, exactly
as it already applies the mask offline today, so **no host-side work is added**.

The unused 896 encoder output bits become dangling. Vivado will then prune any encoder logic that
feeds only those bits — most usefully the bundle-stage majority counters, which are `D × CNT_W` flops.
Whether that prunes cleanly is an empirical question for #29 and is the main upside surprise to look
for; it is **not** claimed here.

### 6.3 `popcount_am_narrow`

```systemverilog
module popcount_am_narrow #(
    parameter int K_BITS        = 128,
    parameter int BITS_PER_WORD = 64,
    parameter int K_WORDS       = (K_BITS + BITS_PER_WORD - 1) / BITS_PER_WORD,
    parameter int N_CLASS       = 8,
    parameter int DIST_W        = $clog2(K_BITS + 1)
) ( /* baseline ports, minus mask_in, with D -> K_BITS */ );
```

Changes from the baseline, all of them simplifications:

- `proto[k]` and `query_r` are `K_BITS` wide, not `D`.
- `S_XOR` drops the `& mask_in` term entirely.
- `LAST_WORD` becomes `K_WORDS-1`; `DIST_W` narrows from 11 to 8 bits at `K_BITS=128`.
- Tail handling when `K_BITS % 64 != 0`: zero-pad the final word. Zero bits contribute 0 to popcount,
  so this is safe; `K_BITS ∈ {128, 256, 512}` are exact multiples anyway.

Argmin semantics are untouched (first index wins on ties), and by §5.2 the distances are identical to
the baseline's masked distances. The golden model needs **no new mask mode** — `hdc_ref` already
produces the free-choice Fisher mask, and `scripts/verify_narrow_gather_equivalence.py` is the
reference for the gathered form.

### 6.4 Projected results

Cycles are exact; area is an estimate pending the per-module utilisation report in #29.

| Config | K bits | AM words | Classify cycles | Core cycles | Core latency | Accuracy (HDC-2) |
|---|---|---|---|---|---|---|
| Baseline | 1024 | 16 | 264 | 287 | 2.87 µs | 72.65% |
| E keep=0.5 | 512 | 8 | 136 | 159 | 1.59 µs | 72.65% (bit-exact) |
| E keep=0.25 | 256 | 4 | 72 | 95 | 0.95 µs | 72.65% (bit-exact) |
| **E keep=0.125** | **128** | **2** | **40** | **63** | **0.63 µs** | **72.65% (bit-exact)** |

AM storage at `K_BITS=128`: `proto` falls from `N_CLASS×1024` = 8,192 FF to `N_CLASS×128` = 1,024 FF,
and `query_r` from 1,024 to 128 FF — **−8,064 FF, 45% of the 17,784-FF core**, before any encoder
pruning. The proto mux shrinks from `N_CLASS*WORDS`=128:1 to 16:1 per lane. The encoder's fixed share
still caps the core-level percentage, so #29 must report **per-module** utilisation.

End-to-end at keep=0.125: 4.63 µs → ~2.4 µs/window (~1.9×), after the ~1.8 µs DMA/PS floor.

## 7. Gate criteria (from the split plan)

> ≥10% LUT reduction **or** measurable µJ/latency improvement at keep=0.125 vs baseline RTL.

Option E clears this at keep=0.125 on both axes: −85% classify cycles and −45% core FF, with the LUT
number pending synthesis. The ±0.5 pp accuracy gate is met **by construction** (bit-exact, §5.2)
rather than by measurement, so keep=0.125 — the config C2 could not reach — is the config we take to
the board.

## 8. Verification plan (#30)

| Harness | Why it must re-run | Pass criterion |
|---|---|---|
| `tb_am_cosim` | new module under test | 500 cases bit-exact vs gathered `hdc_ref` |
| `tb_core_cosim` | gather wiring through `hdc_core_top` | 500 cases, at D ∈ {256, 512, 1024, 2048} |
| `tb_core_axi_cosim` | proto load path via AXI-Lite (mask path removed) | 200 cases |
| `tb_stream_cosim` | DMA path, pre-gathered protos | 200 cases |
| `tb_pruning_mask_cosim` | unchanged module, baseline build only | 64 cases, must still pass |

Two-stage discipline:

1. **Identity pass.** Build with `K_BITS=1024` and `SEL[i] = i`. Every harness must be bit-identical
   to the current baseline logs. This proves the gather plumbing is behaviour-preserving and isolates
   a wiring bug from a narrowing bug.
2. **Narrow pass.** `K_BITS ∈ {512, 256, 128}` with the real Fisher `SEL`, cross-checked against
   `scripts/verify_narrow_gather_equivalence.py` on the same vectors — the RTL distances must equal
   the golden *masked full-width* distances, not merely the golden narrow ones. That is the property
   the paper claim rests on.

New golden-side work is small: `scripts/gen_sel_table.py` to emit `hdc_sel_pkg` from the mask
artefact, plus pre-gathered prototype `.mem` vectors. `blocked_mask_from_scores` in `hdc_ref` is no
longer on the critical path but is kept — it produced the §5 negative result.

## 9. Task breakdown for #29

1. `scripts/gen_sel_table.py` → `rtl/hdc_sel_pkg.sv` from the Fisher mask artefact; check the emitted
   `SEL` against the `.mem` mask in CI.
2. Add `rtl/popcount_am_narrow.sv` (no `mask_in`, `K_BITS`-wide storage).
3. Gather wiring + `K_BITS` plumbing in `hdc_core_top`; keep the baseline path selectable.
4. **Identity pass:** `K_BITS=1024`, `SEL[i]=i`, bit-identical to baseline on all harnesses.
5. **Narrow pass:** co-sim at `K_BITS ∈ {512, 256, 128}` against masked full-width golden distances.
6. OOC synthesis per `K_BITS`, **with `report_utilization -hierarchical`**. Explicitly check whether
   the bundle-stage counters pruned (§6.2).
7. Update `results/dsweep/`-style summary under `results/narrow_rtl/`.

No accuracy re-run is required — that is the point of Option E.

## 10. Risks

| Risk | Mitigation |
|---|---|
| 1024-wire fixed permutation causes routing congestion or hurts WNS | only 128 of 1024 bits are actually routed to the AM; the rest are dangling. If WNS regresses, add a pipeline stage on the gathered query — it is off the critical accumulate loop |
| `SEL` in RTL drifts from the Python mask | generate `hdc_sel_pkg` from the same artefact and assert equality in CI (task 1) |
| Encoder bundle counters do not prune, capping core-level LUT saving | report per-module AM utilisation as the primary number, core total as secondary |
| Board latency win swamped by DMA overhead | report core-only cycles (from co-sim) alongside end-to-end board µs in #31 |
| Reviewer objects that Option E freezes the mask at synthesis | own it as compile-time specialisation, and report the measured negative result: nothing in the option space (A, B, C1, D) delivers runtime reconfigurability *and* a hardware win. §3 and §5 are the evidence |
