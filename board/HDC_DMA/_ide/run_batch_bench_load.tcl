# Load Phase 3 batch bench ELF and poll DDR @ 0x00100200.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
source [file join $SCRIPT_DIR paths.tcl]
source [file join $SCRIPT_DIR program_board_helpers.tcl]

set BATCH_BASE  0x00100200
set BATCH_MAGIC 0xBEC00004
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

if {![file exists $BATCH_BENCH_ELF]} {
    error "Missing batch bench ELF: $BATCH_BENCH_ELF"
}

puts "Loading batch bench ELF (PL must already be programmed):"
puts "  app: $BATCH_BENCH_ELF"

connect -url $HW_URL
wait_targets 20
load_elf_on_a9_0 $BATCH_BENCH_ELF "batch_bench"
con

puts "CPU running batch bench — polling @ [format 0x%08X $BATCH_BASE] (max ${MAX_WAIT_SEC}s)..."

set deadline [clock add [clock seconds] $MAX_WAIT_SEC seconds]
set next_progress [clock add [clock seconds] $PROGRESS_SEC seconds]
set done 0

while {[clock seconds] < $deadline} {
    set magic [read_u32_running $BATCH_BASE]
    set status [read_u32_running [expr {$BATCH_BASE + 0x04}]]

    if {$magic == $BATCH_MAGIC && $status == 1} {
        set done 1
        break
    }

    if {[clock seconds] >= $next_progress} {
        set batch_n [read_u32_running [expr {$BATCH_BASE + 0x10}]]
        puts "[clock format [clock seconds] -format {%H:%M:%S}] magic=[format 0x%08X $magic] status=$status batch_n=$batch_n"
        set next_progress [clock add [clock seconds] $PROGRESS_SEC seconds]
    }

    after 1000
}

if {!$done} {
    set magic [read_u32_running $BATCH_BASE]
    set status [read_u32_running [expr {$BATCH_BASE + 0x04}]]
    puts "ERROR: batch bench did not finish within ${MAX_WAIT_SEC}s (magic=[format 0x%08X $magic] status=$status)"
    exit 1
}

set cpu_hz        [read_u32_running [expr {$BATCH_BASE + 0x08}]]
set gtmr_hz       [read_u32_running [expr {$BATCH_BASE + 0x0C}]]
set batch_n       [read_u32_running [expr {$BATCH_BASE + 0x10}]]
set batch_total   [read_u32_running [expr {$BATCH_BASE + 0x14}]]
set batch_mean    [read_u32_running [expr {$BATCH_BASE + 0x18}]]
set throughput    [read_u32_running [expr {$BATCH_BASE + 0x1C}]]
set e2e_mean      [read_u32_running [expr {$BATCH_BASE + 0x20}]]
set e2e_mm2s      [read_u32_running [expr {$BATCH_BASE + 0x24}]]
set e2e_samples   [read_u32_running [expr {$BATCH_BASE + 0x28}]]

puts "=================================================="
puts "HDC Phase 3 batch bench (DMA stream @ [format 0x%08X $DMA_BASE])"
puts "CPU=$cpu_hz Hz  global_tmr=$gtmr_hz Hz"
puts "=================================================="
puts "--- Sustained batch ($batch_n windows, proto loaded once) ---"
puts "total = $batch_total us  mean = $batch_mean us/window"
puts "throughput ~ $throughput windows/s"
puts "--- E2E proxy (MM2S+S2MM submit -> both idle, $e2e_samples samples) ---"
puts "mean = $e2e_mean us  (MM2S done @ $e2e_mm2s us)"
puts "=================================================="
