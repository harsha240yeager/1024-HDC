# Shared Phase 3 EMG replay result readback @ 0x00100300.

set ::PHASE3_EMG_BASE  0x00100300
set ::PHASE3_EMG_MAGIC 0xBEC00005
set ::PHASE3_EMG_FROZEN_BASELINE_X1000 90300
set ::PHASE3_EMG_TOL_X1000 500

proc phase3_format_pct_x1000 {val} {
    set whole [expr {$val / 1000}]
    set frac  [expr {($val % 1000) / 10}]
    return [format "%d.%02d" $whole $frac]
}

proc phase3_print_emg_results {n correct errors accuracy_x1000 export_ref_x1000 engine_stage_b} {
    global PHASE3_EMG_FROZEN_BASELINE_X1000 PHASE3_EMG_TOL_X1000

    set acc_str [phase3_format_pct_x1000 $accuracy_x1000]
    set ref_str [phase3_format_pct_x1000 $export_ref_x1000]

    if {$accuracy_x1000 >= $export_ref_x1000} {
        set delta_x1000 [expr {$accuracy_x1000 - $export_ref_x1000}]
    } else {
        set delta_x1000 [expr {$export_ref_x1000 - $accuracy_x1000}]
    }
    set delta_str [phase3_format_pct_x1000 $delta_x1000]

    set pass_tol 0
    if {$delta_x1000 <= $PHASE3_EMG_TOL_X1000} {
        set pass_tol 1
    }

    puts "=================================================="
    puts "HDC Phase 3 EMG replay (sw/hdc_emg_board_test.c)"
    puts "DDR readback @ [format 0x%08X $::PHASE3_EMG_BASE]"
    puts "=================================================="
    puts "EMG replay: N=$n correct=$correct accuracy=${acc_str}%"
    if {$export_ref_x1000 > 0} {
        puts "Export ref: ${ref_str}%"
    }
    if {$pass_tol} {
        puts "Board vs export: delta=${delta_str}%  PASS (0.5% tol)"
    } else {
        puts "Board vs export: delta=${delta_str}%  FAIL (0.5% tol)"
    }
    if {$engine_stage_b} {
        set base_str [phase3_format_pct_x1000 $PHASE3_EMG_FROZEN_BASELINE_X1000]
        puts "INFO frozen baseline (Stage B): ${base_str}%"
    }
    puts "errors=$errors"
    puts "=================================================="

    if {$n == 0} {
        return 1
    }
    return [expr {!$pass_tol}]
}
