# DATE 2027 submission checklist (issue #38)

Use this gate before uploading to the DATE portal. Manuscript source lives in
[`Research-paper`](https://github.com/harsha240yeager/Research-paper);
experiments and claim checks live in [`1024-HDC`](https://github.com/harsha240yeager/1024-HDC).

## CFP compliance (verify against current DATE 2027 call)

- [ ] Page limit: **6 pages** IEEE conference format (references excluded per CFP).
- [ ] **Double-blind:** no `\author` block in `conference_101719.tex` (title only).
- [ ] PDF metadata: no author names in document properties (inspect with `pdfinfo`).
- [ ] Anonymous PDF filename (e.g. `DATE2027_HDC_pruning_anon.pdf`).
- [ ] No public GitHub URL or lab hostname in the PDF body.
- [ ] AI disclosure: footnote-style statement only if CFP permits during review (see manuscript closing).

## Artifact / reproducibility

- [ ] `bash scripts/reproduce_paper.sh --verify-only` → **0 failures** in 1024-HDC.
- [ ] Committed log: `results/repro/claim_check.json` matches manuscript numbers.
- [ ] Optional review zip: `python3 scripts/make_anon_artifact.py --zip` (scrubbed snapshot; **not** the public repo).
- [ ] Private GitHub repos stay private; share artifact only via conference upload if required.

## Manuscript integration (#36)

- [ ] Stage-B, silicon 10-seed, narrow RTL, ranking 72.65%, native D, Antonio compact in text/tables.
- [ ] Figures present under `Research-paper/figures/` (run `bash scripts/sync_figures_to_research_paper.sh` from 1024-HDC).
- [ ] `pdflatex conference_101719.tex` (×2) + bib compiles without errors.

## Figures (#37)

- [ ] `python3 python_ref/plot_results.py --paper` in 1024-HDC.
- [ ] `bash scripts/plot_issue32_pareto.sh` for narrow Pareto.
- [ ] Sync PDFs to Research-paper (script above).

## Human gates (cannot be automated)

- [ ] Advisor/professor read-through.
- [ ] Mock review discussion (see `docs/PAPER_DISCUSSION_GUIDE.md` §8).
- [ ] Save submission confirmation email/screenshot.

## After acceptance (camera-ready)

- [ ] Restore `\author` block from git history in Research-paper.
- [ ] De-anonymize artifact if policy allows.
