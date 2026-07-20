# JTAG chain diagnostic — prints all targets and recovery attempts.
set SCRIPT_DIR [file dirname [file normalize [info script]]]
source [file join $SCRIPT_DIR paths.tcl]

proc dump_targets {label} {
    puts "\n=== $label ==="
    set tlist [catch { targets } err]
    if {$tlist != 0} {
        puts "  targets failed: $err"
        return
    }
    set tlist [targets]
    if {[llength $tlist] == 0} {
        puts "  (no targets)"
        return
    }
    foreach t $tlist {
        puts "  $t"
    }
    catch {
        targets -set -nocase -filter {name =~ "APU*"}
        puts "  APU select: OK"
    } apu_err
    if {[info exists apu_err]} {
        puts "  APU select: $apu_err"
        unset apu_err
    }
}

set log [open /tmp/hdc_jtag_diagnose.log w]
proc log_puts {msg} {
    global log
    puts $msg
    puts $log $msg
    flush $log
    flush stdout
}

log_puts "HDC JTAG diagnostic [clock format [clock seconds]]"
log_puts "HW_URL=$HW_URL"

catch { disconnect }
after 2000

log_puts "\n--- connect ---"
if {[catch { connect -url $HW_URL } err]} {
    log_puts "connect FAILED: $err"
    close $log
    exit 1
}
after 2000
dump_targets "initial"

log_puts "\n--- rst -system (catch) ---"
catch { targets -set -nocase -filter {name =~ "APU*"} }
catch { rst -system } rst_err
if {[info exists rst_err]} {
    log_puts "  rst -system: $rst_err"
} else {
    log_puts "  rst -system: OK"
}
after 5000
dump_targets "after rst -system"

log_puts "\n--- reconnect ---"
catch { disconnect }
after 3000
connect -url $HW_URL
after 3000
dump_targets "after reconnect"

log_puts "\n--- try DAP target + rst ---"
foreach t [targets] {
    if {[string match -nocase *DAP* $t]} {
        catch { targets -set -nocase $t }
        log_puts "  selected: $t"
        break
    }
}
catch { rst -system } rst2
log_puts "  rst from DAP: [expr {[info exists rst2] ? $rst2 : OK}]"
after 5000
catch { disconnect }
after 2000
connect -url $HW_URL
after 3000
dump_targets "after DAP rst + reconnect"

log_puts "\n--- try fpga target only ---"
catch { targets -set -nocase -filter {name =~ "*xc7z020*"} }
log_puts "  xc7z020 select: [catch { targets -set -nocase -filter {name =~ \"*xc7z020*\"} } e; set e]"
dump_targets "final"

set apu_ok 0
catch {
    targets -set -nocase -filter {name =~ "APU*"}
    set apu_ok 1
}
if {$apu_ok} {
    log_puts "\nRESULT: APU AVAILABLE — board ready for EMG replay"
    close $log
    exit 0
} else {
    log_puts "\nRESULT: NO APU — physical recovery required (see docs/USB_UART_JTAG.md)"
    close $log
    exit 2
}
