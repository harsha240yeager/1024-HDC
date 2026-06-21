# Host-side Phase 2 stream golden test over JTAG (AXI DMA + config regs).
#
# Prerequisite: hw_server running; PL programmed + PS7 initialized.
# Set HDC_IDE to the board Tcl directory (paths.tcl, program_board_helpers.tcl).
#
# Usage:
#   export HDC_IDE=/path/to/HDC_DMA/_ide
#   xsdb scripts/run_stream_golden_jtag.tcl [vecdir]

set SCRIPT_DIR [file dirname [file normalize [info script]]]
set REPO_ROOT  [file normalize [file join $SCRIPT_DIR ..]]

if {[info exists env(HDC_IDE)] && $env(HDC_IDE) ne ""} {
    set HDC_IDE $env(HDC_IDE)
} else {
    error "Set HDC_IDE to board Tcl dir (e.g. export HDC_IDE=/path/to/HDC_DMA/_ide)"
}

source [file join $HDC_IDE paths.tcl]
source [file join $HDC_IDE program_board_helpers.tcl]

if {$argc >= 1} {
    set VECDIR [file normalize [lindex $argv 0]]
} elseif {[info exists env(HDC_GOLDEN_VECDIR)] && $env(HDC_GOLDEN_VECDIR) ne ""} {
    set VECDIR [file normalize $env(HDC_GOLDEN_VECDIR)]
} else {
    set VECDIR [file join $REPO_ROOT python_ref vectors cosim_core]
}

foreach f [list \
    [file join $VECDIR core_proto.hex] \
    [file join $VECDIR core_mask.hex] \
    [file join $VECDIR core_levels.hex] \
    [file join $VECDIR core_expect.hex]] {
    if {![file exists $f]} {
        error "Missing golden vector file: $f"
    }
}

set WORDS64   16
set N_CLASS   8
set VEC_WORDS 32
set IDX_W     3
set DIST_W    11
set N_CASES   200
set IN_BEATS  3
set OUT_BEATS 1

set REG_CTRL   [expr {$HDC_BASE + 0x000}]
set REG_PIDX   [expr {$HDC_BASE + 0x008}]
set REG_STAGE  [expr {$HDC_BASE + 0x100}]

set CTRL_LOAD_PROTO 0x2
set CTRL_LOAD_MASK  0x4

set DMA_MM2S [expr {$DMA_BASE + 0x000}]
set DMA_S2MM [expr {$DMA_BASE + 0x030}]

set IN_BUF  0x00100000
set OUT_BUF 0x00101000

set DMA_CR_RUNSTOP 0x1
set DMA_SR_IDLE    0x2
set DMA_SR_HALTED  0x1

proc jtag_error_recoverable {err} {
    return [expr {
        [string match -nocase *Invalid\ context* $err]
        || [string match -nocase *Invalid\ target* $err]
        || [string match -nocase *Cannot\ flush\ JTAG* $err]
        || [string match -nocase *ftdi_* $err]
        || [string match -nocase *no\ targets* $err]
        || [string match -nocase *Memory\ read\ error* $err]
        || [string match -nocase *Memory\ write\ error* $err]
    }]
}

proc prepare_mem_access {} {
    global HDC_BASE DMA_BASE IN_BUF OUT_BUF
    if {[catch {targets -set -nocase -filter {name =~ "APU*"}} err]} {
        reconnect
        targets -set -nocase -filter {name =~ "APU*"}
    }
    catch { stop }
    memmap -addr $HDC_BASE -size 0x1000 -flags 3
    memmap -addr $DMA_BASE -size 0x1000 -flags 3
    memmap -addr $IN_BUF -size 0x1000 -flags 3
    memmap -addr $OUT_BUF -size 0x1000 -flags 3
}

proc read_u32 {addr {attempts 10}} {
    set line ""
    for {set i 1} {$i <= $attempts} {incr i} {
        if {[catch {
            set raw [mrd -force $addr 1]
            set line [lindex [split $raw "\n"] 0]
        } err]} {
            if {[jtag_error_recoverable $err]} {
                reconnect
                prepare_mem_access
            }
            after 300
            continue
        }
        if {[regexp {:[ \t]*([0-9a-fA-F]+)} $line -> hex]} {
            return [scan $hex %x]
        }
        if {($i % 3) == 0} {
            reconnect
            prepare_mem_access
        }
        after 300
    }
    error "Failed to read [format 0x%08x $addr] (last: '$line')"
}

proc write_u32 {addr val {attempts 10}} {
    for {set i 1} {$i <= $attempts} {incr i} {
        if {![catch {mwr -force $addr $val} err]} {
            return
        }
        if {[jtag_error_recoverable $err]} {
            reconnect
            prepare_mem_access
        }
        after 300
    }
    error "Failed to write [format 0x%08x $addr] = [format 0x%08x $val]: $err"
}

proc read_hex_file {path} {
    set fh [open $path r]
    set lines {}
    while {[gets $fh line] >= 0} {
        set s [string trim $line]
        if {$s ne "" && ![string match "//*" $s]} {
            lappend lines [expr "0x$s"]
        }
    }
    close $fh
    return $lines
}

proc proto32 {proto kcls w} {
    global WORDS64
    set idx [expr {$kcls * $WORDS64 + ($w >> 1)}]
    set w64 [lindex $proto $idx]
    if {$w & 1} {
        return [expr {($w64 >> 32) & 0xFFFFFFFF}]
    }
    return [expr {$w64 & 0xFFFFFFFF}]
}

proc mask32 {mask w} {
    set w64 [lindex $mask [expr {$w >> 1}]]
    if {$w & 1} {
        return [expr {($w64 >> 32) & 0xFFFFFFFF}]
    }
    return [expr {$w64 & 0xFFFFFFFF}]
}

proc fill_staging {words} {
    global REG_STAGE VEC_WORDS
    for {set w 0} {$w < $VEC_WORDS} {incr w} {
        write_u32 [expr {$REG_STAGE + $w * 4}] [lindex $words $w]
    }
}

proc load_prototype {proto kcls} {
    global REG_CTRL REG_PIDX CTRL_LOAD_PROTO VEC_WORDS
    set staging {}
    for {set w 0} {$w < $VEC_WORDS} {incr w} {
        lappend staging [proto32 $proto $kcls $w]
    }
    fill_staging $staging
    write_u32 $REG_PIDX $kcls
    write_u32 $REG_CTRL $CTRL_LOAD_PROTO
    after 2
}

proc load_mask_vec {mask} {
    global REG_CTRL CTRL_LOAD_MASK VEC_WORDS
    set staging {}
    for {set w 0} {$w < $VEC_WORDS} {incr w} {
        lappend staging [mask32 $mask $w]
    }
    fill_staging $staging
    write_u32 $REG_CTRL $CTRL_LOAD_MASK
    after 2
}

proc split_levels {packed} {
    set lvl0 [expr {$packed & 0xFFFFFFFF}]
    set lvl1 [expr {($packed >> 32) & 0xFFFFFFFF}]
    set lvl2 [expr {($packed >> 64) & 0xFFFF}]
    return [list $lvl0 $lvl1 $lvl2]
}

proc dma_wait_idle {chan_base {max 100000}} {
    global DMA_SR_IDLE
    for {set i 0} {$i < $max} {incr i} {
        set sr [read_u32 [expr {$chan_base + 0x04}]]
        if {($sr & $DMA_SR_IDLE) != 0} {
            return 1
        }
        after 1
    }
    return 0
}

proc dma_simple_xfer {chan_base buf_addr length} {
    global DMA_CR_RUNSTOP DMA_SR_HALTED
    set sr [read_u32 [expr {$chan_base + 0x04}]]
    if {($sr & $DMA_SR_HALTED) == 0} {
        if {![dma_wait_idle $chan_base]} {
            error "DMA channel busy @ [format 0x%08x $chan_base]"
        }
    }
    write_u32 [expr {$chan_base + 0x18}] $buf_addr
    set cr [read_u32 [expr {$chan_base + 0x00}]]
    write_u32 [expr {$chan_base + 0x00}] [expr {$cr | $DMA_CR_RUNSTOP}]
    write_u32 [expr {$chan_base + 0x28}] $length
}

proc stream_classify_case {lvl0 lvl1 lvl2} {
    global IN_BUF OUT_BUF DMA_MM2S DMA_S2MM IN_BEATS OUT_BEATS IDX_W DIST_W

    write_u32 $IN_BUF $lvl0
    write_u32 [expr {$IN_BUF + 4}] $lvl1
    write_u32 [expr {$IN_BUF + 8}] $lvl2
    write_u32 $OUT_BUF 0

    dma_simple_xfer $DMA_S2MM $OUT_BUF [expr {$OUT_BEATS * 4}]
    dma_simple_xfer $DMA_MM2S $IN_BUF [expr {$IN_BEATS * 4}]

    if {![dma_wait_idle $DMA_S2MM]} {
        return [list -1 -1 0]
    }
    if {![dma_wait_idle $DMA_MM2S]} {
        return [list -1 -1 0]
    }

    set out1 [read_u32 $OUT_BUF]
    set got_idx  [expr {($out1 >> 16) & ((1 << $IDX_W) - 1)}]
    set got_dist [expr {$out1 & ((1 << $DIST_W) - 1)}]
    return [list $got_idx $got_dist 1]
}

set proto  [read_hex_file [file join $VECDIR core_proto.hex]]
set mask   [read_hex_file [file join $VECDIR core_mask.hex]]
set levels [read_hex_file [file join $VECDIR core_levels.hex]]
set expect [read_hex_file [file join $VECDIR core_expect.hex]]

if {[llength $expect] < $N_CASES} {
    set N_CASES [llength $expect]
}

puts "=================================================="
puts "HDC stream JTAG golden test: $N_CASES cases (D=1024, N_CLASS=$N_CLASS)"
puts "  VECDIR = $VECDIR"
puts "  HDC    = [format 0x%08X $HDC_BASE]"
puts "  DMA    = [format 0x%08X $DMA_BASE]"
puts "=================================================="

catch { disconnect }
after 1000
connect -url $HW_URL
wait_targets 20
prepare_mem_access

for {set k 0} {$k < $N_CLASS} {incr k} {
    load_prototype $proto $k
}
load_mask_vec $mask

set errors 0
set checked 0

for {set c 0} {$c < $N_CASES} {incr c} {
    set packed [lindex $levels $c]
    foreach {lvl0 lvl1 lvl2} [split_levels $packed] { break }

    set exp [lindex $expect $c]
    set exp_idx  [expr {($exp >> 16) & ((1 << $IDX_W) - 1)}]
    set exp_dist [expr {$exp & ((1 << $DIST_W) - 1)}]

    foreach {got_idx got_dist ok} [stream_classify_case $lvl0 $lvl1 $lvl2] { break }
    incr checked

    if {!$ok || $got_idx != $exp_idx || $got_dist != $exp_dist} {
        incr errors
        puts "--------------------------------------------------"
        puts "FAIL case $c"
        if {!$ok} { puts "  stream/DMA timed out" }
        puts "  expected idx=$exp_idx dist=$exp_dist"
        puts "  got      idx=$got_idx dist=$got_dist"
        puts "--------------------------------------------------"
    }

    if {(($c + 1) % 25) == 0} {
        puts "  ... [expr {$c + 1}] / $N_CASES checked (errors so far: $errors)"
    }
}

puts "=================================================="
if {$errors == 0} {
    puts "PASS: $checked/$checked stream golden cases"
} else {
    puts "FAIL: $errors errors / $checked checked"
}
puts "=================================================="

if {$errors != 0} {
    exit 1
}
