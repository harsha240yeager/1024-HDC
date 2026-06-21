# Program ZedBoard with HDC_DMA Phase 2 bitstream + DMA golden app.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
source [file join $SCRIPT_DIR paths.tcl]
source [file join $SCRIPT_DIR ps7_init_helpers.tcl]
source [file join $SCRIPT_DIR program_board_helpers.tcl]

foreach f [list $BITFILE $PS7_INIT $FSBL_ELF $APP_ELF] {
    if {![file exists $f]} {
        error "Missing required file: $f"
    }
}

puts "Programming HDC_DMA Phase 2 with:"
puts "  bitstream: $BITFILE"
puts "  app:       $APP_ELF"

connect -url $HW_URL
program_zed_board $BITFILE $PS7_INIT $FSBL_ELF $APP_ELF $VIVADO_PL 1
