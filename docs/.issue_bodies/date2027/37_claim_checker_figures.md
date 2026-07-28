## Priority: P1 · Both · **Required before DATE submit**

Extend claim checker, regenerate figures, reproducibility docs.

## Goal

Every new number in the manuscript is machine-checked from committed artifacts.

## Requirements

- [ ] Add claims to `scripts/check_paper_numbers.py` for:
  - Stage-B iso-density gaps
  - Silicon seed mean ± std
  - Narrow RTL LUT/energy/latency
  - Active support mechanism (327 / 209)
- [ ] Regenerate `results/figures/*` and copy to `Research-paper/figures/`
- [ ] Update `docs/REPRODUCIBILITY.md` claim count
- [ ] Run `scripts/reproduce_paper.sh` tier relevant to new results
- [ ] `python scripts/check_paper_numbers.py` → 0 failures

## Done when

- [ ] CI/local gate passes; JSON log committed under `results/repro/`

## Blocked by

- #36 manuscript draft numbers frozen
