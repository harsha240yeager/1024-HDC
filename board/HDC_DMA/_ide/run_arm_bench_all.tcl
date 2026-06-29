# Program ARM HDC bench ELF (PS software only path), poll @ 0x00100400.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
source [file join $SCRIPT_DIR paths.tcl]
source [file join $SCRIPT_DIR ps7_init_helpers.tcl]
source [file join $SCRIPT_DIR program_board_helpers.tcl]
source [file join $SCRIPT_DIR phase3_bench_report.tcl]
source [file join $SCRIPT_DIR phase3_arm_bench_report.tcl]

set ARM_BENCH_BASE $::PHASE3_ARM_BENCH_BASE
set ARM_BENCH_MAGIC $::PHASE3_ARM_BENCH_MAGIC
set ARM_BENCH_ELF [file join $HDC_DMA_ROOT app build Final_HDC_arm_bench.elf]
set MAX_WAIT_SEC 300
set PROGRESS_SEC 10

proc jtag_error_recoverable {err} {
    return [expr {
        [string match -nocase *Invalid\ context* $err]
        || [string match -nocase *Invalid\ target* $err]
        || [string match -nocase *Cannot\ flush\ JTAG* $err]
        || [string match -nocase *ftdi_* $err]
        || [string match -nocase *no\ targets* $err]
    }]
}

proc select_apu_no_halt {} {
    catch { targets -set -nocase -filter {name =~ "APU*"} }
}

proc read_u32_running {addr {attempts 10}} {
    set line ""
    for {set i 1} {$i <= $attempts} {incr i} {
        if {[catch {
            select_apu_no_halt
            set raw [mrd -force $addr 1]
            set line [lindex [split $raw "\n"] 0]
        } err]} {
            if {[jtag_error_recoverable $err]} {
                reconnect $::HW_URL
                select_apu_no_halt
            }
            after 300
            continue
        }
        if {[regexp {:[ \t]*([0-9a-fA-F]+)} $line -> hex]} {
            return [expr 0x$hex]
        }
        after 300
    }
    error "Failed to read [format 0x%08x $addr]"
}

foreach f [list $BITFILE $PS7_INIT $FSBL_ELF $ARM_BENCH_ELF] {
    if {![file exists $f]} {
        error "Missing required file: $f"
    }
}

puts "Programming ARM HDC bench:"
puts "  bitstream: $BITFILE"
puts "  app:       $ARM_BENCH_ELF"

connect -url $HW_URL
# Standalone Vitis app — load directly (no FSBL handoff).
program_zed_board $BITFILE $PS7_INIT $FSBL_ELF $ARM_BENCH_ELF $VIVADO_PL 0

puts "CPU running ARM bench — polling @ [format 0x%08X $ARM_BENCH_BASE]..."

set deadline [clock add [clock seconds] $MAX_WAIT_SEC seconds]
set done 0

while {[clock seconds] < $deadline} {
    set magic [read_u32_running $ARM_BENCH_BASE]
    set status [read_u32_running [expr {$ARM_BENCH_BASE + 0x04}]]

    if {$magic == $ARM_BENCH_MAGIC && $status == 1} {
        set done 1
        break
    }
    after 500
}

if {!$done} {
    error "Timeout waiting for ARM bench @ [format 0x%08X $ARM_BENCH_BASE]"
}

if {![phase3_arm_bench_report $ARM_BENCH_BASE]} {
    exit 1
}

exit 0
