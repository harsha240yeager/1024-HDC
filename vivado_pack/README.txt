1024HDC — Vivado bring-up package
=================================

Unpack this folder anywhere on the VDI (e.g. C:\projects\1024HDC_vivado).
Keep the directory layout intact — RTL default $readmemh paths expect
  python_ref/vectors/cosim_core/*.mem

CONTENTS
--------
  rtl/                          SystemVerilog sources (add all to Vivado)
  python_ref/vectors/cosim_core/  Item-memory ROM init + golden hex for PS test
  sw/                           Bare-metal driver example (Vitis)
  docs/                         Quick register map reference

PHASE A — AXI-Lite bring-up (start here)
----------------------------------------
1. Vivado: New project for your board (Zynq-7020, e.g. xc7z020clg400-1).
2. Add all files under rtl/ as design sources.
3. Block design:
     Zynq7 PS  +  AXI Interconnect  +  proc_sys_reset
     Connect PS M_AXI_GP0 -> interconnect -> hdc_core_axi_lite_bd_wrapper (AXI slave)
     IMPORTANT: use hdc_core_axi_lite_bd_wrapper.sv in Block Design, NOT hdc_core_axi_lite.sv
     (the wrapper adds Vivado bus-interface metadata; bare core shows "incompatible").
     FCLK_CLK0 (100 MHz) -> s_axi_aclk; proc_sys_reset -> s_axi_aresetn
4. Address Editor: assign hdc_core_axi_lite at 0x43C0_0000 (64 KB).
5. Set top to block-design wrapper; Generate Bitstream.

   IMPORTANT: When adding hdc_core_axi_lite, Vivado elaborates from the
   project directory. Open Vivado with this folder as the project root, OR
   add python_ref/vectors/cosim_core as a source directory so .mem paths resolve.

6. Export hardware (.xsa) -> Vitis bare-metal app from sw/hdc_core_axi_example.c
   Base address: 0x43C00000 (must match Address Editor).

PHASE B — Streaming (after AXI-Lite golden test passes)
-------------------------------------------------------
Add rtl/hdc_stream_wrapper.sv + AXI DMA in block design (see research plan).

GOLDEN ON-BOARD TEST
--------------------
Use hex files in python_ref/vectors/cosim_core/:
  core_proto.hex, core_mask.hex, core_levels.hex, core_expect.hex
Load protos/mask via STAGING + LOAD_PROTO/LOAD_MASK; run inference per
core_levels.hex; compare to core_expect.hex (same flow as ModelSim co-sim).

REGISTER MAP (byte offsets from 0x43C00000)
--------------------------------------------
  0x000  CTRL     W  bit0 START, bit1 LOAD_PROTO, bit2 LOAD_MASK, bit3 CLR_DONE
  0x004  STATUS   R  bit0 BUSY, bit1 DONE
  0x008  PROTO_IDX
  0x00C  RESULT   R  (class_idx << 16) | dist
  0x010-0x018  LEVELS0..2  (80-bit window)
  0x100-0x17C  STAGING (32 x 32-bit words = 1024-bit vector)

RTL FILE LIST (minimum for hdc_core_axi_lite)
---------------------------------------------
  hdc_core_axi_lite_bd_wrapper.sv  <-- add THIS module to Block Design
  hdc_core_axi_lite.sv, hdc_core_top.sv, encoder_top.sv, item_mem.sv,
  bundle_unit.sv, popcount_am.sv, xor_permute_top.sv, permute_stage.sv

Optional (streaming): hdc_stream_wrapper.sv

Repo: https://github.com/harsha240yeager/1024-HDC

GOLDEN TEST ON ZEDBOARD (after bitstream programmed)
----------------------------------------------------
From this folder (repo root or unzipped pack with scripts/):

  powershell -File scripts/prep_golden_test.ps1

Vitis app: sw/hdc_core_golden_test.c + sw/hdc_core_regs.c + sw/golden_vectors.h
UART 115200 -> expect PASS: 200/200 golden cases
