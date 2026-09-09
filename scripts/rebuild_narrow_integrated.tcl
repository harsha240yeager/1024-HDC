# Narrow integrated rebuild — wraps Final_HDC/rebuild_from_synth.tcl with RTL registration.
#
# Requires: HDC_VIVADO_ROOT=/path/to/FInal_HDC (set by run_narrow_integrated_bitstream.sh)

if {![info exists ::env(HDC_VIVADO_ROOT)]} {
    error "Set HDC_VIVADO_ROOT to the FInal_HDC directory before running this script"
}
set proj_dir [file normalize $::env(HDC_VIVADO_ROOT)]
set repo     [file normalize [file join [file dirname [info script]] ..]]

set xsa_dir  [file join $proj_dir export hw]
set xsa_file [file join $xsa_dir design_1_wrapper.xsa]
set proj_file [file join $proj_dir FInal_HDC.xpr]
set ooc_log   [file join $proj_dir FInal_HDC.runs design_1_hdc_stream_system_0_0_synth_1 runme.log]

proc count_crit_msgs {file} {
    if {![file exists $file]} { return 0 }
    set fh [open $file r]
    set n 0
    while {[gets $fh line] >= 0} {
        if {[regexp {^CRITICAL WARNING:} $line]} { incr n }
    }
    close $fh
    return $n
}

proc require_zero_crit {stage} {
    set sess [get_msg_config -count -severity {CRITICAL WARNING}]
    if {$sess > 0} {
        error "$stage: Vivado session has $sess critical warning(s)"
    }
}

file mkdir $xsa_dir
cd $proj_dir
open_project $proj_file
set_property source_mgmt_mode All [current_project]
source [file join $repo scripts prep_narrow_integrated_project.tcl]
source [file join $proj_dir attach_mem_synth_hook.tcl]

puts "INFO: resetting HDC OOC + top synth + impl..."
foreach run_name {
    design_1_hdc_stream_system_0_0_synth_1
    synth_1
    impl_1
} {
    set run [get_runs -quiet $run_name]
    if {$run ne ""} {
        reset_run $run
        puts "INFO: reset $run_name"
    }
}

puts "INFO: === Step 1/3: synthesis ==="
launch_runs synth_1 -jobs 8
wait_on_run synth_1

set st [get_property STATUS [get_runs synth_1]]
if {$st ne "synth_design Complete!"} {
    error "synth_1 failed: $st"
}

set ooc_crit [count_crit_msgs $ooc_log]
puts "INFO: HDC OOC log critical warnings: $ooc_crit"
if {$ooc_crit > 0} {
    error "HDC OOC synthesis log contains $ooc_crit CRITICAL WARNING line(s): $ooc_log"
}
require_zero_crit "synthesis"

puts "INFO: === Step 2/3: implementation + bitstream ==="
launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1

set st [get_property STATUS [get_runs impl_1]]
if {$st ne "write_bitstream Complete!"} {
    error "impl_1 failed: $st"
}
require_zero_crit "implementation"

puts "INFO: === Step 3/3: export XSA ==="
open_run impl_1
write_hw_platform -fixed -include_bit -force -file $xsa_file
require_zero_crit "export"

catch { save_project }
close_project
puts "SUCCESS: narrow integrated synthesis/impl/export complete"
puts "XSA: $xsa_file"
