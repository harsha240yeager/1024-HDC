# Vivado PL-only fallback when xsdb fpga programming fails.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
source [file join $SCRIPT_DIR paths.tcl]

if {![file exists $BITFILE]} {
    error "Missing bitstream: $BITFILE"
}

open_hw_manager
connect_hw_server -url localhost:3121 -allow_non_jtag
after 2000

set targets [get_hw_targets -quiet]
if {[llength $targets] == 0} {
    error "No hardware targets found"
}

open_hw_target [lindex $targets 0]
after 2000

set devs [get_hw_devices -quiet]
if {[llength $devs] == 0} {
    error "No hardware devices found"
}

set dev [lindex $devs 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
after 2000

set bit_files [get_property PROGRAM.FILE $dev]
if {$bit_files eq ""} {
    set_property PROGRAM.FILE $BITFILE $dev
}

program_hw_devices $dev
after 2000
close_hw_target
close_hw_manager

puts "PL programmed successfully via Vivado HW Manager fallback"
