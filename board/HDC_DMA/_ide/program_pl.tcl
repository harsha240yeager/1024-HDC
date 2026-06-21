# Program HDC_DMA Phase 2 PL + PS7 init only (no application).
# Use before host-side stream golden test over JTAG.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
source [file join $SCRIPT_DIR paths.tcl]
source [file join $SCRIPT_DIR ps7_init_helpers.tcl]
source [file join $SCRIPT_DIR program_board_helpers.tcl]

foreach f [list $BITFILE $PS7_INIT $FSBL_ELF] {
    if {![file exists $f]} {
        error "Missing required file: $f"
    }
}

puts "Programming HDC_DMA PL only (no application):"
puts "  bitstream: $BITFILE"

connect -url $HW_URL
set tlist [wait_targets 20]
puts "=== JTAG targets ==="
foreach t $tlist { puts "  $t" }

run_ps7_before_pl $PS7_INIT
puts "\n=== Programming PL bitstream ==="
if {![program_pl_xsdb $BITFILE 12]} {
    if {$VIVADO_PL ne "" && [file exists $VIVADO_PL]} {
        if {![program_pl_vivado $VIVADO_PL]} {
            error "PL programming failed"
        }
    } else {
        error "PL programming failed"
    }
}
if {![run_ps7_after_pl $PS7_INIT]} {
    error "PS7 init failed after PL"
}
load_elf_on_a9_0 $FSBL_ELF "FSBL"
con
after 3000
if {![wait_for_a9_target]} {
    error "Lost A9 target after FSBL"
}
catch { targets -set -nocase -filter {name =~ "*A9*#0*"} }
catch { stop }
puts "PL + FSBL ready for host-side access @ HDC=[format 0x%08X $HDC_BASE] DMA=[format 0x%08X $DMA_BASE]"
