# Regenerate standalone BSP from XSA using HSI (works when platform.spr update fails).
#
# Usage:
#   xsct scripts/regenerate_bsp_from_xsa.tcl <xsa> <bsp_dir>
#
set xsa     [lindex $argv 0]
set bsp_dir [lindex $argv 1]

if {$xsa eq ""} {
  set xsa [file normalize [file join [file dirname [info script]] .. platform export Final_HDC hw design_1_wrapper.xsa]]
}
if {$bsp_dir eq ""} {
  set bsp_dir [file normalize [file join [file dirname [info script]] .. platform ps7_cortexa9_0 standalone_domain bsp]]
}

if {![file exists $xsa]} {
  error "XSA not found: $xsa"
}

set work [file normalize [file join $bsp_dir _hsi_regen]]
file mkdir $work
cd $work

puts "INFO: HSI regen work = $work"
puts "INFO: XSA           = $xsa"
puts "INFO: BSP target    = $bsp_dir"

hsi open_hw_design $xsa
hsi set_repo_path [file join $env(XILINX_VITIS) data embeddedsw]

set sw design_1_wrapper_bsp
catch { hsi delete_sw_design $sw }
hsi create_sw_design $sw -proc ps7_cortexa9_0 -os standalone

set gen_dir [file join $work generated_bsp]
file mkdir $gen_dir
hsi generate_bsp -dir $gen_dir

# Merge generated BSP into the existing tree (preserve lscript linkage paths).
proc copy_tree {src dst} {
  if {![file exists $src]} { return }
  file mkdir $dst
  foreach f [glob -nocomplain -directory $src *] {
    set base [file tail $f]
    set target [file join $dst $base]
    if {[file isdirectory $f]} {
      file delete -force $target
      file copy -force $f $target
    } else {
      file copy -force $f $target
    }
  }
}

foreach sub {ps7_cortexa9_0/include ps7_cortexa9_0/lib ps7_cortexa9_0/libsrc} {
  copy_tree [file join $gen_dir $sub] [file join $bsp_dir $sub]
}

# Top-level BSP files
foreach f {Makefile system.mss Xilinx.spec} {
  set src [file join $gen_dir $f]
  if {[file exists $src]} {
    file copy -force $src [file join $bsp_dir $f]
  }
}

puts "SUCCESS: BSP regenerated under $bsp_dir"
if {[file exists [file join $bsp_dir ps7_cortexa9_0/include/xparameters.h]]} {
  set fh [open [file join $bsp_dir ps7_cortexa9_0/include/xparameters.h] r]
  while {[gets $fh line] >= 0} {
    if {[string match *INCLUDE_SG* $line]} { puts $line }
  }
  close $fh
}
