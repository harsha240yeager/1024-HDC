# Program EMG replay ELF, keep CPU running, poll results @ 0x00100300.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
source [file join $SCRIPT_DIR paths.tcl]
source [file join $SCRIPT_DIR ps7_init_helpers.tcl]
source [file join $SCRIPT_DIR program_board_helpers.tcl]
source [file join $SCRIPT_DIR phase3_emg_report.tcl]

set EMG_BASE $::PHASE3_EMG_BASE
set EMG_MAGIC $::PHASE3_EMG_MAGIC
set MAX_WAIT_SEC 600
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

foreach f [list $BITFILE $PS7_INIT $FSBL_ELF $EMG_ELF] {
    if {![file exists $f]} {
        error "Missing required file: $f"
    }
}

puts "Programming HDC_DMA EMG replay with:"
puts "  bitstream: $BITFILE"
puts "  app:       $EMG_ELF"

connect -url $HW_URL
program_zed_board $BITFILE $PS7_INIT $FSBL_ELF $EMG_ELF $VIVADO_PL 1

puts "CPU running EMG replay — polling @ [format 0x%08X $EMG_BASE] (max ${MAX_WAIT_SEC}s)..."

set deadline [clock add [clock seconds] $MAX_WAIT_SEC seconds]
set next_progress [clock add [clock seconds] $PROGRESS_SEC seconds]
set done 0

while {[clock seconds] < $deadline} {
    set magic [read_u32_running $EMG_BASE]
    set status [read_u32_running [expr {$EMG_BASE + 0x04}]]

    if {$magic == $EMG_MAGIC && $status == 1} {
        set done 1
        break
    }

    if {[clock seconds] >= $next_progress} {
        set n [read_u32_running [expr {$EMG_BASE + 0x08}]]
        set correct [read_u32_running [expr {$EMG_BASE + 0x0C}]]
        puts "[clock format [clock seconds] -format {%H:%M:%S}] magic=[format 0x%08X $magic] status=$status n=$n correct=$correct"
        set next_progress [clock add [clock seconds] $PROGRESS_SEC seconds]
    }

    after 1000
}

if {!$done} {
    set magic [read_u32_running $EMG_BASE]
    set status [read_u32_running [expr {$EMG_BASE + 0x04}]]
    puts "ERROR: EMG replay did not finish within ${MAX_WAIT_SEC}s (magic=[format 0x%08X $magic] status=$status)"
    exit 1
}

set n               [read_u32_running [expr {$EMG_BASE + 0x08}]]
set correct         [read_u32_running [expr {$EMG_BASE + 0x0C}]]
set accuracy_x1000  [read_u32_running [expr {$EMG_BASE + 0x10}]]
set errors          [read_u32_running [expr {$EMG_BASE + 0x14}]]
set export_ref_x1000 [read_u32_running [expr {$EMG_BASE + 0x18}]]

set rc [phase3_print_emg_results $n $correct $errors $accuracy_x1000 $export_ref_x1000 0]
exit $rc
