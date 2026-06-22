# Paths for HDC_DMA Phase 2 (stream + AXI DMA).
# HDC_DMA_ROOT is derived from this file's location inside the repo.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
set HDC_DMA_ROOT [file normalize [file join $SCRIPT_DIR ..]]
set REPO_ROOT    [file normalize [file join $HDC_DMA_ROOT ../..]]

if {[info exists env(HDC_VIVADO_ROOT)] && $env(HDC_VIVADO_ROOT) ne ""} {
    set HDC_VIVADO_ROOT [file normalize $env(HDC_VIVADO_ROOT)]
} else {
    set HDC_VIVADO_ROOT ""
}

set BITFILE  [file join $HDC_DMA_ROOT app _ide bitstream design_1_wrapper.bit]
set PS7_INIT [file join $HDC_DMA_ROOT app _ide psinit ps7_init.tcl]
set FSBL_ELF [file join $HDC_DMA_ROOT platform zynq_fsbl fsbl.elf]
set APP_ELF  [file join $HDC_DMA_ROOT app build Final_HDC_dma_golden.elf]
set BENCH_ELF [file join $HDC_DMA_ROOT app build Final_HDC_dma_bench.elf]
set BATCH_BENCH_ELF [file join $HDC_DMA_ROOT app build Final_HDC_dma_batch_bench.elf]
set EMG_ELF       [file join $HDC_DMA_ROOT app build Final_HDC_dma_emg.elf]
set VIVADO_PL [file join $SCRIPT_DIR program_pl_vivado.tcl]

set HDC_BASE 0x43C00000
set DMA_BASE 0x40400000
set HW_URL   tcp:127.0.0.1:3121
