# Regenerate BSP from a new XSA (e.g. after enabling AXI DMA scatter-gather).
#
# Usage:
#   xsct scripts/update_platform_from_xsa.tcl <path/to/design_1_wrapper.xsa>
#
set root [file normalize [file dirname [info script]]/..]
set xsa  [lindex $argv 0]

if {$xsa eq ""} {
  set xsa [file normalize [file join $root platform export Final_HDC hw design_1_wrapper.xsa]]
}

if {![file exists $xsa]} {
  error "XSA not found: $xsa"
}

set spr [file join $root platform platform.spr]
if {![file exists $spr]} {
  error "Platform SPR not found: $spr"
}

puts "INFO: workspace  = $root"
puts "INFO: platform   = $spr"
puts "INFO: update hw  = $xsa"

setws $root
platform read $spr
platform config -updatehw $xsa

domain active standalone_domain
bsp regenerate

domain active zynq_fsbl
bsp regenerate

platform generate

puts "SUCCESS: platform updated from $xsa"
