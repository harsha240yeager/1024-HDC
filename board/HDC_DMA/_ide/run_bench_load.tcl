# Load bench ELF on already-programmed board and poll DDR @ 0x00100000.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
source [file join $SCRIPT_DIR paths.tcl]
source [file join $SCRIPT_DIR program_board_helpers.tcl]
source [file join $SCRIPT_DIR phase3_bench_report.tcl]

set BENCH_BASE $::PHASE3_BENCH_BASE
set BENCH_MAGIC $::PHASE3_BENCH_MAGIC
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

if {![file exists $BENCH_ELF]} {
    error "Missing bench ELF: $BENCH_ELF"
}

puts "Loading bench ELF (PL must already be programmed):"
puts "  app: $BENCH_ELF"

connect -url $HW_URL
wait_targets 20
load_elf_on_a9_0 $BENCH_ELF "bench"
con

puts "CPU running bench — polling @ [format 0x%08X $BENCH_BASE] (max ${MAX_WAIT_SEC}s)..."

set deadline [clock add [clock seconds] $MAX_WAIT_SEC seconds]
set next_progress [clock add [clock seconds] $PROGRESS_SEC seconds]
set done 0

while {[clock seconds] < $deadline} {
    set magic [read_u32_running $BENCH_BASE]
    set status [read_u32_running [expr {$BENCH_BASE + 0x04}]]

    if {$magic == $BENCH_MAGIC && $status == 1} {
        set done 1
        break
    }

    if {[clock seconds] >= $next_progress} {
        set iters [read_u32_running [expr {$BENCH_BASE + 0x10}]]
        puts "[clock format [clock seconds] -format {%H:%M:%S}] magic=[format 0x%08X $magic] status=$status iters=$iters"
        set next_progress [clock add [clock seconds] $PROGRESS_SEC seconds]
    }

    after 1000
}

if {!$done} {
    set magic [read_u32_running $BENCH_BASE]
    set status [read_u32_running [expr {$BENCH_BASE + 0x04}]]
    puts "ERROR: bench did not finish within ${MAX_WAIT_SEC}s (magic=[format 0x%08X $magic] status=$status)"
    exit 1
}

set cpu_hz     [read_u32_running [expr {$BENCH_BASE + 0x08}]]
set gtmr_hz    [read_u32_running [expr {$BENCH_BASE + 0x0C}]]
set iters      [read_u32_running [expr {$BENCH_BASE + 0x10}]]
set min_us     [read_u32_running [expr {$BENCH_BASE + 0x14}]]
set max_us     [read_u32_running [expr {$BENCH_BASE + 0x18}]]
set mean_us    [read_u32_running [expr {$BENCH_BASE + 0x1C}]]
set throughput [read_u32_running [expr {$BENCH_BASE + 0x20}]]
set g_errors   [read_u32_running [expr {$BENCH_BASE + 0x24}]]
set g_checked  [read_u32_running [expr {$BENCH_BASE + 0x28}]]

set batch_magic [read_u32_running $::PHASE3_BATCH_BASE]
set batch_n 0
set batch_us 0
set batch_tput 0
set batch_golden_errors 1
if {$batch_magic == $::PHASE3_BATCH_MAGIC} {
    set batch_n [read_u32_running [expr {$::PHASE3_BATCH_BASE + 0x10}]]
    set batch_us [read_u32_running [expr {$::PHASE3_BATCH_BASE + 0x14}]]
    set batch_tput [read_u32_running [expr {$::PHASE3_BATCH_BASE + 0x18}]]
    set batch_golden_errors [read_u32_running [expr {$::PHASE3_BATCH_BASE + 0x1C}]]
}

set rc [phase3_print_bench_results $cpu_hz $gtmr_hz $iters $min_us $max_us $mean_us \
    $throughput $g_errors $g_checked $batch_n $batch_us $batch_tput $batch_golden_errors]
exit $rc
