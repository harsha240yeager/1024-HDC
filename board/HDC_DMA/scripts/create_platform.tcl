# Create Vitis platform Final_HDC from Phase 2 XSA (DMA + stream system).
set root     [file normalize [file dirname [info script]]/..]
set ws       $root
set xsa      [file normalize [file join $root .. FInal_HDC export hw design_1_wrapper.xsa]]
set plat_dir [file join $root Final_HDC]

if {![file exists $xsa]} {
  error "XSA not found: $xsa\nRun export_hw_platform.tcl in Vivado first."
}

if {[file exists $plat_dir]} {
  puts "INFO: removing stale platform tree $plat_dir"
  file delete -force $plat_dir
}

setws $ws

platform create -name Final_HDC \
  -hw $xsa \
  -proc ps7_cortexa9_0 \
  -os standalone \
  -arch 32 \
  -fsbl-target ps7_cortexa9_0

domain active standalone_domain

bsp regenerate
platform generate

puts "Platform Final_HDC ready: [file join $plat_dir export Final_HDC Final_HDC.xpfm]"
