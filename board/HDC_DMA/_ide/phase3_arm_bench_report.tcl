# ARM HDC bench DDR layout @ 0x00100400 (magic 0xBEC00006)

set ::PHASE3_ARM_BENCH_BASE 0x00100400
set ::PHASE3_ARM_BENCH_MAGIC 0xBEC00006

proc phase3_arm_bench_report {base} {
    set magic [read_u32_running $base]
    if {$magic != $::PHASE3_ARM_BENCH_MAGIC} {
        puts "ERROR: ARM bench magic [format 0x%08X $magic] != [format 0x%08X $::PHASE3_ARM_BENCH_MAGIC]"
        return 0
    }
    set status   [read_u32_running [expr {$base + 0x04}]]
    set cpu_hz   [read_u32_running [expr {$base + 0x08}]]
    set tmr_hz   [read_u32_running [expr {$base + 0x0C}]]
    set iters    [read_u32_running [expr {$base + 0x10}]]
    set min_us   [read_u32_running [expr {$base + 0x14}]]
    set max_us   [read_u32_running [expr {$base + 0x18}]]
    set mean_us  [read_u32_running [expr {$base + 0x1C}]]
    set tput     [read_u32_running [expr {$base + 0x20}]]
    set g_err    [read_u32_running [expr {$base + 0x24}]]
    set g_chk    [read_u32_running [expr {$base + 0x28}]]

    puts "=================================================="
    puts " ARM HDC software bench (Cortex-A9, hdc_arm_ref)"
    puts "=================================================="
    puts "CPU= [format %lu $cpu_hz] Hz  global_tmr= [format %lu $tmr_hz] Hz  iters= [format %lu $iters]"
    puts "Latency (encode+classify):"
    puts "  min  = [format %lu $min_us] us"
    puts "  max  = [format %lu $max_us] us"
    puts "  mean = [format %lu $mean_us] us"
    puts "  throughput = [format %lu $tput] windows/s"
    puts "Golden spot-check: errors= [format %lu $g_err] / [format %lu $g_chk]"
    if {$g_err == 0 && $g_chk > 0} {
        puts "PASS: [format %lu $g_chk]/[format %lu $g_chk] golden cases (ARM infer)"
        puts "=================================================="
        return 1
    }
    puts "FAIL: golden spot-check"
    puts "=================================================="
    return 0
}
