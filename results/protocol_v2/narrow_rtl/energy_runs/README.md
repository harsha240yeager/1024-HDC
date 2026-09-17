# Narrow PL INA219 energy (issue #31)

Run when ZedBoard + Raspberry Pi INA219 are on the lab network:

```bash
bash scripts/run_narrow_energy_campaign.sh
```

Outputs: `anchor_C/run{01,02,03}/` CSVs + `../energy_summary.txt`.

**Note:** Baseline PL energy for anchor C is in `results/phase3/energy_summary.txt` (~11.81 µJ/w). Narrow system energy is expected near baseline (DMA/PS dominate); the #31 gate is met via **LUT (−70%)** and **batch latency (−40%)** at matched anchor-C accuracy.
