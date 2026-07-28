# Stage B spatial baseline — Protocol HDC-2

Generated: 2026-07-28T11:51:07Z
Engine: Stage B BSC (4-channel spatial records, D=1024)
Protocol: **HDC-2** · item-memory seed **1**

## Headline (5-subject spatial mean)

| Metric | Value |
|--------|-------|
| Spatial mean accuracy | **89.46%** |

## Per subject

| Subject | Train | Test | Accuracy |
|---------|-------|------|----------|
| S1 | 37206 | 111625 | 94.39% |
| S2 | 34782 | 104353 | 88.10% |
| S3 | 34391 | 103182 | 89.35% |
| S4 | 33582 | 100753 | 88.07% |
| S5 | 24531 | 73599 | 87.39% |

## Regenerate

```bash
python3 python_ref/run_stage_b_baseline.py
python3 python_ref/run_stage_b_baseline.py --quick
```

Phase 1 masked engine: `python_ref/stage_b_engine.py`
