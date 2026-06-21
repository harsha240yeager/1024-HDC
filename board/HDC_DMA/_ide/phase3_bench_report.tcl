# Shared Phase 3 bench result readback (single-window @ 0x00100000, batch @ 0x00100100).

set ::PHASE3_BENCH_BASE  0x00100000
set ::PHASE3_BENCH_MAGIC 0xBEC00002
set ::PHASE3_BATCH_BASE  0x00100100
set ::PHASE3_BATCH_MAGIC 0xBEC00003
set ::PHASE3_PHASE1_BASELINE_US 3

proc phase3_read_bench_results {} {
    global PHASE3_BENCH_BASE PHASE3_BATCH_BASE

    set cpu_hz     [read_u32_running [expr {$PHASE3_BENCH_BASE + 0x08}]]
    set gtmr_hz    [read_u32_running [expr {$PHASE3_BENCH_BASE + 0x0C}]]
    set iters      [read_u32_running [expr {$PHASE3_BENCH_BASE + 0x10}]]
    set min_us     [read_u32_running [expr {$PHASE3_BENCH_BASE + 0x14}]]
    set max_us     [read_u32_running [expr {$PHASE3_BENCH_BASE + 0x18}]]
    set mean_us    [read_u32_running [expr {$PHASE3_BENCH_BASE + 0x1C}]]
    set throughput [read_u32_running [expr {$PHASE3_BENCH_BASE + 0x20}]]
    set g_errors   [read_u32_running [expr {$PHASE3_BENCH_BASE + 0x24}]]
    set g_checked  [read_u32_running [expr {$PHASE3_BENCH_BASE + 0x28}]]

    set batch_magic [read_u32_running $PHASE3_BATCH_BASE]
    set batch_n 0
    set batch_us 0
    set batch_tput 0
    set batch_golden_errors 1

    if {$batch_magic == $::PHASE3_BATCH_MAGIC} {
        set batch_n [read_u32_running [expr {$PHASE3_BATCH_BASE + 0x10}]]
        set batch_us [read_u32_running [expr {$PHASE3_BATCH_BASE + 0x14}]]
        set batch_tput [read_u32_running [expr {$PHASE3_BATCH_BASE + 0x18}]]
        set batch_golden_errors [read_u32_running [expr {$PHASE3_BATCH_BASE + 0x1C}]]
    }

    return [list $cpu_hz $gtmr_hz $iters $min_us $max_us $mean_us $throughput \
                 $g_errors $g_checked $batch_n $batch_us $batch_tput $batch_golden_errors]
}

proc phase3_print_bench_results {cpu_hz gtmr_hz iters min_us max_us mean_us throughput \
                                 g_errors g_checked batch_n batch_us batch_tput batch_golden_errors} {
    global DMA_BASE PHASE3_PHASE1_BASELINE_US

    puts "=================================================="
    puts "HDC Phase 3 bench (DMA stream @ [format 0x%08X $DMA_BASE])"
    puts "CPU=$cpu_hz Hz  global_tmr=$gtmr_hz Hz  single_iters=$iters"
    puts "=================================================="
    puts "--- Single-window DMA latency ---"
    puts "min  = $min_us us"
    puts "max  = $max_us us"
    puts "mean = $mean_us us"
    puts "throughput ~ $throughput windows/s (1/mean)"
    puts "--- vs Phase 1 AXI-Lite baseline (~${PHASE3_PHASE1_BASELINE_US} us/window) ---"
    if {$mean_us > $PHASE3_PHASE1_BASELINE_US} {
        puts "delta = +[expr {$mean_us - $PHASE3_PHASE1_BASELINE_US}] us (slower than Phase 1)"
    } elseif {$mean_us > 0} {
        puts "delta = -[expr {$PHASE3_PHASE1_BASELINE_US - $mean_us}] us (faster than Phase 1)"
    }
    puts "--- Batch DMA throughput ---"
    puts "total   = $batch_us us"
    if {$batch_n > 0 && $batch_us > 0} {
        puts "mean/window ~ [expr {$batch_us / $batch_n}] us (total / N)"
    }
    puts "throughput ~ $batch_tput windows/s (batch / total)"
    puts "--- Golden batch check (batch DMA outputs) ---"
    if {$batch_golden_errors == 0 && $batch_n > 0} {
        puts "PASS: $batch_n/$batch_n batch golden cases"
    } elseif {$batch_n > 0} {
        puts "FAIL: $batch_golden_errors batch errors / $batch_n"
    } else {
        puts "FAIL: batch section missing or empty"
    }
    puts "--- Golden batch check (per-window DMA) ---"
    if {$g_errors == 0} {
        puts "PASS: $g_checked/$g_checked stream golden cases"
    } else {
        puts "FAIL: $g_errors errors / $g_checked checked"
    }
    puts "=================================================="

    if {$g_errors != 0} {
        return 1
    }
    if {$batch_n == 0 || $batch_golden_errors != 0} {
        return 1
    }
    return 0
}
