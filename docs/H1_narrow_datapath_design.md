# H1 — Narrow / gated masked-Hamming datapath: micro-architecture design

**Issue:** [#28](https://github.com/harsha240yeager/1024-HDC/issues/28) (P0, Paper 1) · **Feeds:** #29 (implement+synth), #30 (co-sim), #31 (board eval), #32 (Pareto figure)
**Status:** design complete, awaiting sign-off → #29
**Baseline RTL:** `rtl/popcount_am.sv`, `rtl/pruning_mask.sv` @ `D=1024`, `WORDS=16`, `BITS_PER_WORD=64`, `N_CLASS=8`

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
Compact 1024 scattered bits down to 128 with a configurable permutation so the mask stays
free-choice. Requires 128 lanes × 1024:1 muxing; that is tens of thousands of LUTs on a part where
the full core is 28,600. The compaction network would cost more than the datapath it compacts.

### Option C — **word-blocked mask + genuinely narrow datapath · SELECTED**
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

## 5. What the word-blocked constraint costs in accuracy

Measured with `scripts/eval_word_blocked_mask.py` → `results/narrow_rtl/word_blocked_mask_eval.json`
(40k windows, cached cohort, unpruned reference 74.28%):

| keep | Words kept | Cycle reduction | Free-choice | **Word-blocked** | Δ blocked−free | Random iso-density |
|---|---|---|---|---|---|---|
| 0.125 | 2/16 | −88% | 77.68% | **73.16%** | −4.53 pp | 66.61% |
| 0.25 | 4/16 | −75% | 74.28% | **74.28%** | **0.00 pp** | 68.62% |
| 0.5 | 8/16 | −50% | 74.28% | **72.32%** | −1.96 pp | 70.58% |

**keep=0.25 is the operating point**: word-blocking is free (0.00 pp vs free-choice, and identical to
unpruned) while removing 75% of AM cycles.

Two caveats, both stated so #29/#31 inherit them rather than rediscover them:

1. These scores come from the cached cohort, so *every* arm is optimistic — that is why free-choice
   at keep=0.125 (77.68%) exceeds unpruned. The comparison is valid because the bias is shared, and
   the blocked−free gap is if anything **overstated**: free-choice can exploit per-bit leakage that
   word-granular selection cannot. Paper numbers must come from the TRAIN-Fisher path under #29/#31.
2. keep=0.25 landing exactly on the unpruned accuracy is plausible (the value-table active support is
   only 327 bits, so 256 well-chosen bits can preserve the argmin ordering) but it needs confirming
   on the strict protocol before it goes in a table.

## 5.5 The comparator that decides whether this is publishable

A baked 256-bit AM datapath invites the obvious reviewer objection: *"that is just D=256 with extra
steps."* It has to be answered with the iso-width baseline, not the D=1024 baseline. Pooled HDC-2
accuracy from `results/protocol_v2/hook_a/sweep_results.json` (`cnt_w=6`, 5 subjects, free-choice
Fisher masks):

| D | keep=1.0 | keep=0.5 | keep=0.25 | keep=0.125 |
|---|---|---|---|---|
| 256 | 69.82% | 69.82% | 69.82% | 69.26% |
| 512 | 72.72% | 72.72% | 72.72% | 72.72% |
| **1024** | **72.78%** | 72.78% | **72.78%** | 72.78% |
| 2048 | 76.45% | 76.45% | 76.45% | 76.45% |

Read the diagonal: **encode at D=1024 and classify on 256 selected bits → 72.78%, whereas encoding
*and* classifying at D=256 → 69.82%.** Same AM datapath width, **+2.96 pp** for the pruned design.
The 1024-d encoding carries information that a 256-d encoding never captures, and Fisher selection
keeps the part of it that matters.

That gives Paper 1 two claims that stand on their own:

1. **vs D=1024 baseline — iso-accuracy efficiency.** 72.78% at both keep=1.0 and keep=0.25, so
   −73% AM cycles and (est.) −37% LUT come at **zero** accuracy cost.
2. **vs D=256 baseline — iso-width accuracy.** +2.96 pp at the same AM width, for the cost of a
   wider encoder.

Claim 1 is the headline; claim 2 is what stops the "just use a smaller D" rebuttal. Both must appear
in the #32 Pareto figure, which therefore needs **three** curves: D-sweep, keep-sweep at D=1024, and
the narrow-RTL points.

> **Gate on this before writing RTL.** The table above uses *free-choice* Fisher masks. C2 needs
> *word-blocked* masks, and the 0.00 pp word-blocking cost in §5 comes from the leaky design proxy.
> Re-run the word-blocked arm at keep=0.25 under HDC-2 with TRAIN-derived Fisher scores; it must land
> at 72.78% ± 0.5 pp. If it does not, fall back to C1 (free-choice mask preserved, latency/energy
> claim only). This is one Python run and it is the cheapest possible way to de-risk the RTL work.

## 6. Micro-architecture spec

### 6.1 `pruning_mask` — add a live-word interface (shared by C1 and C2)

New outputs alongside the existing `mask_out`:

```systemverilog
output logic [N_WORDS-1:0]              word_live,   // OR-reduce per word
output logic [WORD_IDX_W-1:0]           live_seq [0:N_WORDS-1],  // compacted indices
output logic [$clog2(N_WORDS+1)-1:0]    n_live                   // popcount(word_live)
```

`word_live[g] = |regs[g]`, combinational off the existing register file. `live_seq`/`n_live` are
recomputed on any mask write — a 16-entry compaction, one small always_comb block. Existing ports and
the all-ones reset default are untouched, so `hdc_core_top` and both wrappers keep working unchanged
(unpruned ⇒ `n_live=16` ⇒ baseline behaviour, bit-identical).

### 6.2 `popcount_am_narrow` — new module, baseline left in place

Parameterised so one source covers both variants:

```systemverilog
module popcount_am_narrow #(
    parameter int WORDS         = 16,
    parameter int BITS_PER_WORD = 64,
    parameter int N_CLASS       = 8,
    parameter int KEEP_WORDS    = 16,      // C2: < WORDS ⇒ physically narrow
    parameter bit RUNTIME_SKIP  = 1'b1     // C1: iterate live_seq at runtime
) ( /* baseline ports + word_live/live_seq/n_live */ );
```

FSM changes, minimal and local:

- `S_XOR` indexes `live_seq[w_ptr]` instead of `w_idx`; `w_ptr` counts `0 .. n_live-1`.
- `S_ACC` terminates on `w_ptr == n_live-1` rather than `LAST_WORD`.
- `DIST_W` narrows to `$clog2(KEEP_WORDS*BITS_PER_WORD + 1)` under C2.
- Storage under C2: `proto[k]` and `query_r` are `KEEP_WORDS*BITS_PER_WORD` wide. The host loads
  **pre-compacted** prototypes (software already applies the mask offline — no hardware gather), and
  the encoder output is sliced to the selected words on the way in.
- Under C1 (`KEEP_WORDS == WORDS`) the widths collapse to the baseline and only iteration changes.

Argmin semantics are untouched: `dist[k] = popcount((query ^ proto[k]) & mask)` over live words only,
first-index-wins on ties. This is exactly `hdc_ref.HDCEngine.classify` restricted to a word-blocked
mask, so the golden model needs **no** change — only a word-blocked mask generator.

### 6.3 Projected results

Cycles are exact; area is an estimate pending the per-module utilisation report in #29.

| Config | Words | Classify cycles | Core cycles | Core latency | Est. core FF | Est. ΔFF |
|---|---|---|---|---|---|---|
| Baseline | 16 | 264 | 287 | 2.87 µs | 17,784 | — |
| C1/C2 keep=0.5 | 8 | 136 | 159 | 1.59 µs | ~13,300 | −25% |
| **C2 keep=0.25** | 4 | **72** | **95** | **0.95 µs** | **~10,900** | **−39%** |
| C2 keep=0.125 | 2 | 40 | 63 | 0.63 µs | ~9,700 | −45% |

FF estimate: `proto` (`N_CLASS×D`) and `query_r` scale with `KEEP_WORDS`; the encoder does not shrink
(it still produces 1024 bits). LUT saving should track the proto mux, which shrinks from 128:1 to
`N_CLASS*KEEP_WORDS`:1 per lane — 4× at keep=0.25 — but the encoder's fixed LUT share caps the
core-level number, which is why #29 must produce a **per-module** report, not just a core total.

End-to-end at keep=0.25: 4.63 µs → ~2.7 µs/window (~1.7×), after the ~1.8 µs DMA/PS floor.

## 7. Gate criteria (from the split plan)

> ≥10% LUT reduction **or** measurable µJ/latency improvement at keep=0.125 vs baseline RTL.

C2 clears this on the latency axis with margin (−73% classify cycles at keep=0.25, −85% at 0.125) and
should clear the LUT axis too. Accuracy gate: anchor within ±0.5 pp — **C2 at keep=0.125 does not
meet this** (−4.53 pp in the design proxy), so **keep=0.25 is the config we take to the board**, with
keep=0.125 reported as the aggressive Pareto endpoint.

## 8. Verification plan (#30)

| Harness | Why it must re-run | Pass criterion |
|---|---|---|
| `tb_pruning_mask_cosim` | new `word_live`/`live_seq`/`n_live` outputs | 64 cases, incl. all-ones and single-word masks |
| `tb_am_cosim` | new module under test | 500 cases bit-exact vs `hdc_ref` |
| `tb_core_cosim` | integration through `hdc_core_top` | 500 cases, at D ∈ {256, 512, 1024, 2048} |
| `tb_core_axi_cosim` | mask load path via AXI-Lite | 200 cases |
| `tb_stream_cosim` | DMA path, pre-compacted protos | 200 cases |

Regression discipline: **run every harness against `KEEP_WORDS=16, RUNTIME_SKIP=0` first** and require
bit-identical results to the current baseline logs. That proves the refactor is behaviour-preserving
before any narrowing is evaluated, and isolates a genuine narrowing bug from a refactor bug.

New golden-side work: a word-blocked mask generator in `hdc_ref` (the
`blocked_mask_from_scores` in `scripts/eval_word_blocked_mask.py` promoted into the library) plus
regenerated `.mem` vectors for the word-blocked configs.

## 9. Task breakdown for #29

0. **Gate first (§5.5):** word-blocked keep=0.25 under HDC-2 with TRAIN-Fisher scores must hit
   72.78% ± 0.5 pp. Do not start RTL until this passes; if it fails, switch to C1.
1. Extend `pruning_mask` with `word_live`/`live_seq`/`n_live`; update `tb_pruning_mask_cosim`.
2. Promote `blocked_mask_from_scores` into `hdc_ref`; regenerate co-sim vectors and `.mem` files.
3. Add `rtl/popcount_am_narrow.sv` (both variants, one parameterised source).
4. Equivalence pass: `KEEP_WORDS=16, RUNTIME_SKIP=0` bit-identical to baseline on all five harnesses.
5. Narrowing pass: co-sim at `KEEP_WORDS ∈ {2, 4, 8}`.
6. OOC synthesis per `KEEP_WORDS`, **with per-module utilisation** (`report_utilization -hierarchical`).
7. Update `results/dsweep/`-style summary under `results/narrow_rtl/`.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Word-blocked accuracy fails the ±0.5 pp gate on the strict protocol | keep=0.25 has 0.00 pp headroom in the proxy and the proxy is biased *against* blocking; if it still fails, fall back to C1 (latency/energy claim only, free-choice mask preserved) |
| LUT saving diluted by the fixed encoder share | report per-module AM utilisation as the primary number, core total as secondary |
| Board latency win swamped by DMA overhead | report core-only cycles (from co-sim) alongside end-to-end board µs in #31 |
| Reviewer objects that C2 freezes the mask at synthesis | ship C1 as the runtime-programmable point on the same Pareto curve; the two variants answer "flexible" and "efficient" separately |
