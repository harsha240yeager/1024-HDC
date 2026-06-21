# Load golden ELF on already-programmed board and poll DDR @ 0x00100100.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
source [file join $SCRIPT_DIR paths.tcl]
source [file join $SCRIPT_DIR program_board_helpers.tcl]

set GOLDEN_BASE  0x00100100
set GOLDEN_MAGIC 0xBEC00003
set MAX_WAIT_SEC 600
set PROGRESS_SEC 15

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

if {![file exists $APP_ELF]} {
    error "Missing golden ELF: $APP_ELF"
}

puts "Loading golden ELF (PL must already be programmed):"
puts "  app: $APP_ELF"

connect -url $HW_URL
wait_targets 20
load_elf_on_a9_0 $APP_ELF "golden"
con

puts "CPU running golden — polling @ [format 0x%08X $GOLDEN_BASE] (max ${MAX_WAIT_SEC}s)..."

set deadline [clock add [clock seconds] $MAX_WAIT_SEC seconds]
set next_progress [clock add [clock seconds] $PROGRESS_SEC seconds]
set done 0

while {[clock seconds] < $deadline} {
    set magic [read_u32_running $GOLDEN_BASE]
    set status [read_u32_running [expr {$GOLDEN_BASE + 0x04}]]

    if {$magic == $GOLDEN_MAGIC && $status == 1} {
        set done 1
        break
    }

    if {[clock seconds] >= $next_progress} {
        set n_cases [read_u32_running [expr {$GOLDEN_BASE + 0x08}]]
        set errors [read_u32_running [expr {$GOLDEN_BASE + 0x0C}]]
        puts "[clock format [clock seconds] -format {%H:%M:%S}] magic=[format 0x%08X $magic] status=$status n=$n_cases err=$errors"
        set next_progress [clock add [clock seconds] $PROGRESS_SEC seconds]
    }

    after 1000
}

if {!$done} {
    set magic [read_u32_running $GOLDEN_BASE]
    set status [read_u32_running [expr {$GOLDEN_BASE + 0x04}]]
    puts "ERROR: golden did not finish within ${MAX_WAIT_SEC}s (magic=[format 0x%08X $magic] status=$status)"
    exit 1
}

set n_cases  [read_u32_running [expr {$GOLDEN_BASE + 0x08}]]
set errors   [read_u32_running [expr {$GOLDEN_BASE + 0x0C}]]
set passed   [read_u32_running [expr {$GOLDEN_BASE + 0x10}]]

puts "=================================================="
puts "HDC Phase 2 golden app (sw/hdc_dma_stream_golden_test.c)"
puts "DDR readback @ [format 0x%08X $GOLDEN_BASE]"
puts "=================================================="
if {$errors == 0} {
    puts "PASS: $passed/$n_cases stream golden cases"
} else {
    puts "FAIL: $errors errors / $n_cases checked (passed=$passed)"
}
puts "=================================================="

if {$errors != 0} {
    exit 1
}
