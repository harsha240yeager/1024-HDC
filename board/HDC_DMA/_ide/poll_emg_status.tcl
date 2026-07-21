# Read EMG replay status @ 0x00100300 without reprogramming.
set SCRIPT_DIR [file dirname [file normalize [info script]]]
source [file join $SCRIPT_DIR paths.tcl]
source [file join $SCRIPT_DIR program_board_helpers.tcl]
source [file join $SCRIPT_DIR phase3_emg_report.tcl]

set EMG_BASE $::PHASE3_EMG_BASE
set EMG_MAGIC $::PHASE3_EMG_MAGIC

proc read_u32 {addr} {
    recover_apu_chain 3 "poll APU"
    catch { targets -set -nocase -filter {name =~ "APU*"} }
    set raw [mrd -force $addr 1]
    set line [lindex [split $raw "\n"] 0]
    if {[regexp {:[ \t]*([0-9a-fA-F]+)} $line -> hex]} {
        return [expr 0x$hex]
    }
    error "parse fail: $line"
}

connect -url $HW_URL
after 2000

set magic [read_u32 $EMG_BASE]
set status [read_u32 [expr {$EMG_BASE + 0x04}]]
set n [read_u32 [expr {$EMG_BASE + 0x08}]]
set correct [read_u32 [expr {$EMG_BASE + 0x0C}]]
set accuracy_x1000 [read_u32 [expr {$EMG_BASE + 0x10}]]
set errors [read_u32 [expr {$EMG_BASE + 0x14}]]
set export_ref_x1000 [read_u32 [expr {$EMG_BASE + 0x18}]]

puts "magic=[format 0x%08X $magic] expected=[format 0x%08X $EMG_MAGIC]"
puts "status=$status n=$n correct=$correct acc_x1000=$accuracy_x1000 ref_x1000=$export_ref_x1000 errors=$errors"

if {$magic == $EMG_MAGIC && $status == 1} {
    set rc [phase3_print_emg_results $n $correct $errors $accuracy_x1000 $export_ref_x1000 0]
    exit $rc
}
puts "RUNNING or stale (status=$status)"
exit 2
