# Shared ZedBoard programming helpers for xsdb scripts.

proc wait_targets {max} {
    for {set i 0} {$i < $max} {incr i} {
        set t [targets]
        if {[llength $t] > 0} { return $t }
        after 1000
    }
    error "Timed out waiting for JTAG targets"
}

proc reconnect {{url tcp:127.0.0.1:3121}} {
    catch { disconnect }
    after 2000
    connect -url $url
    wait_targets 20
}

proc select_fpga_target {} {
    if {![catch {targets -set -nocase -filter {name =~ "*xc7z020*"}}]} { return }
    if {![catch {targets -set -filter {jtag_device_name =~ "*xc7z020*"}}]} { return }
    if {![catch {targets -set -filter {jtag_device_ctx=~ "*23727093*"}}]} { return }
    foreach t [targets] {
        if {[string match -nocase *xc7z020* $t]} {
            targets -set -nocase $t
            return
        }
    }
    error "Could not find xc7z020 FPGA target"
}

proc halt_apu {} {
    catch { targets -set -nocase -filter {name =~ "APU*"} }
    catch { stop }
}

proc run_ps7_before_pl {ps7_init_script {attempts 3}} {
    puts "\n=== PS7 init before PL (releases PL from reset) ==="
    for {set attempt 1} {$attempt <= $attempts} {incr attempt} {
        puts "  pre-PL PS7 attempt $attempt..."
        if {[catch {targets -set -nocase -filter {name =~ "APU*"}}]} {
            reconnect
        }
        if {![catch {hdc_run_ps7_init $ps7_init_script} err]} {
            puts "Pre-PL PS7 init OK"
            after 2000
            return 1
        }
        puts "    failed: $err"
        reconnect
        after 3000
    }
    puts "WARNING: Pre-PL PS7 init failed; continuing with PL programming anyway."
    return 0
}

proc program_pl_xsdb {bitfile {max_attempts 12}} {
    if {![file exists $bitfile]} {
        error "Missing bitstream: $bitfile"
    }

    halt_apu

    for {set attempt 1} {$attempt <= $max_attempts} {incr attempt} {
        puts "  PL attempt $attempt"
        if {[catch {select_fpga_target} err]} {
            puts "    target select failed: $err"
            reconnect
            halt_apu
            continue
        }
        if {![catch {fpga -file $bitfile} err]} {
            puts "PL programmed successfully via xsdb"
            after 2000
            return 1
        }
        puts "    fpga failed: $err"
        halt_apu
        catch { rst -system }
        after 5000
        reconnect
        halt_apu
    }

    return 0
}

proc program_pl_vivado {vivado_script} {
    if {![file exists $vivado_script]} {
        error "Missing Vivado script: $vivado_script"
    }

    puts "\n=== Vivado fallback for PL programming ==="
    catch { disconnect }
    after 3000

    if {[catch {exec vivado -mode batch -source $vivado_script} result err]} {
        puts "Vivado PL programming failed:"
        puts $err
        if {$result ne ""} {
            puts $result
        }
        reconnect
        return 0
    }

    if {$result ne ""} {
        puts $result
    }
    after 2000
    reconnect
    return 1
}

proc run_ps7_after_pl {ps7_init_script {attempts 5}} {
    puts "\n=== PS7 init after PL ==="
    for {set attempt 1} {$attempt <= $attempts} {incr attempt} {
        puts "  post-PL PS7 attempt $attempt..."
        if {[catch {targets -set -nocase -filter {name =~ "APU*"}}]} {
            reconnect
        }
        if {![catch {hdc_run_ps7_init $ps7_init_script} err]} {
            puts "PS7 initialized"
            return 1
        }
        puts "    failed: $err"
        reconnect
        after 4000
    }
    return 0
}

proc wait_for_a9_target {{attempts 15}} {
    for {set attempt 1} {$attempt <= $attempts} {incr attempt} {
        if {![catch {targets -set -nocase -filter {name =~ "*A9*#0*"}}]} {
            return 1
        }
        if {$attempt == 1 || ($attempt % 3) == 0} {
            puts "  waiting for A9 target (attempt $attempt)..."
        }
        reconnect
        after 2000
    }
    return 0
}

proc load_elf_on_a9_0 {elf label} {
    if {![wait_for_a9_target]} {
        error "A9 target not available to load $label"
    }
    set max_attempts 8
    for {set attempt 1} {$attempt <= $max_attempts} {incr attempt} {
        catch { stop }
        if {![catch {dow $elf} err]} {
            puts "$label loaded"
            return
        }
        puts "  $label load attempt $attempt/$max_attempts failed: $err"
        reconnect
        after [expr {3000 + $attempt * 2000}]
        if {![wait_for_a9_target]} {
            error "A9 target not available to load $label"
        }
    }
    error "Failed to load $label after $max_attempts attempts"
}

proc load_bin_to_ddr {bin addr {chunk_bytes 65536} {max_attempts 20}} {
    if {![file exists $bin]} {
        error "Missing vectors bin: $bin"
    }
    set fd [open $bin r]
    fconfigure $fd -translation binary
    set offset 0
    set tmp "/tmp/emg_chunk.bin"
    puts "Loading [file tail $bin] to DDR [format 0x%08X $addr] (chunk ${chunk_bytes}B) ..."
    while {![eof $fd]} {
        set chunk [read $fd $chunk_bytes]
        set n [string length $chunk]
        if {$n == 0} {
            break
        }
        set cfd [open $tmp w]
        fconfigure $cfd -translation binary
        puts -nonewline $cfd $chunk
        close $cfd
        set ok 0
        set addr_cur [expr {$addr + $offset}]
        for {set a 1} {$a <= $max_attempts && !$ok} {incr a} {
            if {![catch {dow -data $tmp $addr_cur} err]} {
                set ok 1
            } else {
                if {($a % 3) == 1} {
                    puts "  chunk @ [format 0x%08X $addr_cur] attempt $a/$max_attempts: $err"
                }
                catch { disconnect }
                after 3000
                catch { connect -url $::HW_URL }
                for {set w 1} {$w <= 60} {incr w} {
                    set t [catch { targets } tlist]
                    if {$t == 0 && [llength $tlist] > 0} { break }
                    after 1000
                }
                catch { targets -set -nocase -filter {name =~ "APU*"} }
                after [expr {1000 + $a * 500}]
            }
        }
        if {!$ok} {
            close $fd
            catch { file delete -force $tmp }
            error "Failed loading vectors bin at offset $offset ([format 0x%08X $addr_cur])"
        }
        incr offset $n
        if {($offset % 1048576) < $chunk_bytes} {
            puts "  [format %.1f [expr {$offset / 1048576.0}]] / [format %.1f [expr {[file size $bin] / 1048576.0}]] MiB"
        }
    }
    close $fd
    catch { file delete -force $tmp }
    puts "Vectors bin loaded ($offset bytes)"
}

proc program_zed_board {bitfile ps7_init fsbl_elf app_elf {vivado_pl_script ""} {use_fsbl 1} {vectors_bin ""} {vectors_addr 0x02000000}} {
    set tlist [wait_targets 20]
    puts "=== JTAG targets ==="
    foreach t $tlist { puts "  $t" }

    run_ps7_before_pl $ps7_init

    puts "\n=== Programming PL bitstream ==="
    set programmed [program_pl_xsdb $bitfile 12]

    if {!$programmed && $vivado_pl_script ne ""} {
        set programmed [program_pl_vivado $vivado_pl_script]
    }

    if {!$programmed} {
        error "PL programming failed after xsdb retries and Vivado fallback"
    }

    if {![run_ps7_after_pl $ps7_init]} {
        error "PS7 initialization failed after PL programming"
    }

    if {$use_fsbl} {
        load_elf_on_a9_0 $fsbl_elf "FSBL"
        con
        after 3000
        if {![wait_for_a9_target]} {
            error "Lost JTAG targets after starting FSBL"
        }
        catch { stop }
    }

    load_elf_on_a9_0 $app_elf "HDC_app"
    if {$vectors_bin ne "" && [file exists $vectors_bin]} {
        load_bin_to_ddr $vectors_bin $vectors_addr
    }
    con
    puts "Programming and run complete"
}
