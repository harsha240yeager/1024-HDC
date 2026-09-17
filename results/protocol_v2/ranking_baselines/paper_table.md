# Table — ranking baselines @ 128 bits (Issue #9, Sec. V-D)

**Protocol:** HDC-2 · **Engine:** hdc_ref (RTL-matched encoder) · **D=1024**, **keep=0.125**  
**Subjects:** S1–S5 · **Item memory seed:** 42

| Method | 128-bit acc (spatial mean) | Δ vs Fisher (pp) | Mask Jaccard vs Fisher | Ranking cost | Retrain? |
|--------|----------------------------|------------------|------------------------|--------------|----------|
| Fisher | 72.58% | 0.00 | 1.00 | low | no |
| Variance | 72.58% | 0.00 | 0.81 | low | no |
| Mutual information | 72.58% | 0.00 | 0.95 | medium | no |
| Class-mean separation | 72.58% | 0.00 | 0.91 | low | no |
| Prototype disagreement | 72.58% | 0.00 | 0.18 | low | no |
| Per-bit entropy | 72.58% | 0.00 | 0.81 | low | no |
| Random (active support) | 71.45% | −1.13 | 0.45 | low | no |
| Random (full 1024) | 64.55% | −8.04 | 0.07 | low | no |

**Interpretation:** With ~209 active bits and keep=128, Hook A is flat — informed rankers tie on accuracy but differ in **which** bits they keep (Jaccard). The discriminative claim is **Fisher/informed vs random**, not Fisher-unique. For **dense Stage-B** support where criteria separate, see Issue #22 (`twist1_stage_b/ranking_baselines_README.md`).

Regenerate: `bash scripts/run_issue9_ranking_baselines.sh`
