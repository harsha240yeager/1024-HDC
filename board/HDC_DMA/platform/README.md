# Final_HDC Vitis platform (Phase 2)

Platform component for the Phase 2 ZedBoard design:

- **Hardware:** `design_1_wrapper.xsa` (AXI DMA + `hdc_stream_system_bd_wrapper`, HP0)
- **Domain:** `standalone_domain` on `ps7_cortexa9_0`
- **BSP drivers:** includes `xaxidma` (AXI DMA @ `0x40400000`), stream config @ `0x43C00000`

## Paths

| Artifact | Location |
|----------|----------|
| Platform descriptor | `export/Final_HDC/Final_HDC.xpfm` |
| XSA | `export/Final_HDC/hw/design_1_wrapper.xsa` |
| BSP | `ps7_cortexa9_0/standalone_domain/bsp/` |
| FSBL | `zynq_fsbl/fsbl.elf` |

## Application

Phase 2 DMA golden test: **`Final_HDC_dma_golden`**

Build everything (export XSA, BSP, app):

```bash
bash "/home/bsp-lab/Desktop/Final HDC/HDC_harsha/scripts/build_final_hdc.sh"
```

Program board and run (UART 115200):

```bash
bash "/home/bsp-lab/Desktop/Final HDC/HDC_harsha/run_final_hdc_dma.sh"
```

Expected UART output:

```
PASS: 200/200 stream golden cases
```

## Vitis IDE

Open workspace `/home/bsp-lab/Desktop/Final HDC/HDC_harsha` and import components:

- Platform: `Final_HDC`
- Application: `Final_HDC_dma_golden`
