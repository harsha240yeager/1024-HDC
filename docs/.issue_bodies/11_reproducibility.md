## Priority: P3 (after Phases 1–5) — DONE

Reproducibility artifact released: [`docs/REPRODUCIBILITY.md`](https://github.com/harsha240yeager/1024-HDC/blob/main/docs/REPRODUCIBILITY.md)

## Delivered

- [x] Protocol HDC-2 split code + configs + full seed table (`REPRODUCIBILITY.md`)
- [x] Fisher mask generation (`hdc_ref.py`, `export_fisher_pooled.py`)
- [x] Exported prototypes + test vectors (frozen HDC-2 export reference, 493,512 windows)
- [x] RTL commit hash `aa65999`, Vivado 2024.2, `vivado_pack/`, `scripts/dsweep_synth.tcl`
- [x] ARM reference + flags: `-mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g`
- [x] Board replay logs + raw INA219 CSVs (`results/phase3/energy_runs/`)
- [x] `scripts/reproduce_paper.sh` — tiers `smoke` (~30 min) / `core` (~21 h) / `full` (~3 days),
      measured runtimes, dataset-aware skips, writes to `results/repro/` so committed
      artifacts are never overwritten
- [x] `scripts/check_paper_numbers.py` — re-derives **all 49 published numbers** from the
      committed artifacts; standard library only, no dataset needed; exits non-zero on drift
- [x] Paper §IV-D reproducibility statement with repository URL and license

## Claim check

```
49/49 claims verified
```

Covers accuracies, iso-density gaps, the subject-bootstrap CI, Wilcoxon and
paired-t p-values, energies and ratios, window counts, Jaccard overlaps, the
cross-subject grid, encoder ablation rows, and the active-support range.

## Inconsistencies the checker caught

- Anchor C board accuracy printed as 72.85 % in Table III; the artifact shows
  **72.84 %** board / 72.85 % export reference. Paper corrected.
- Active support quoted as ~202–209 in the discussion and ~203–210 in the
  methods. The difference is TEST subsampling (15k windows/subject) in two
  ablations; the paper now quotes the full-split range **203–210** throughout.

## Portability fixes found while testing

- `scripts/run_hdc2_gate.sh` hard-coded `python3`, which resolves to a
  non-functional alias stub on Windows. Both it and the new scripts now probe
  interpreters by executing them.
- `scripts/audit_split_leakage.py` wrote OS-native config paths, so reruns on
  Windows produced spurious diffs. It now writes POSIX paths, and a rerun
  reproduces `split_audit.json` byte for byte.
- `scripts/run_twist2_36_v2_keep_grid.sh` gained `--out-root` so the 36-subject
  grid can rerun without overwriting committed results.
