# Create and build Phase 2 DMA golden-test application on Final_HDC platform.
set root     [file normalize [file dirname [info script]]/..]
set ws       $root
set sw_root  /home/bsp-lab/1024-HDC/sw
set app_name Final_HDC_dma_golden
set app_dir  [file join $root $app_name]
set plat_xpfm [file join $root Final_HDC export Final_HDC Final_HDC.xpfm]

if {![file exists $plat_xpfm]} {
  error "Platform not found: $plat_xpfm"
}

setws $ws

if {[file exists $app_dir]} {
  puts "INFO: removing stale app $app_dir"
  file delete -force $app_dir
}

app create -name $app_name \
  -platform $plat_xpfm \
  -domain standalone_domain \
  -template empty_application \
  -lang C

set app_src [file join $app_dir src]
file mkdir $app_src

set user_cfg [file join $app_src UserConfig.cmake]
set fd [open $user_cfg w]
puts $fd {cmake_minimum_required(VERSION 3.16)
set(USER_COMPILE_DEFINITIONS "")
set(USER_UNDEFINED_SYMBOLS "__clang__")
set(USER_INCLUDE_DIRECTORIES "$sw_root")
set(USER_COMPILE_SOURCES
  "$sw_root/hdc_dma_stream_golden_test.c"
  "$sw_root/hdc_dma_stream.c"
  "$sw_root/hdc_core_regs.c"
)
set(USER_COMPILE_WARNINGS_ALL -Wall)
set(USER_COMPILE_WARNINGS_EXTRA -Wextra)
set(USER_COMPILE_WARNINGS_AS_ERRORS )
set(USER_COMPILE_OPTIMIZATION_LEVEL -O0)
set(USER_COMPILE_DEBUG_LEVEL -g3)
set(USER_LINK_LIBRARIES )
set(USER_LINK_DIRECTORIES )
set(USER_LINKER_SCRIPT "${CMAKE_SOURCE_DIR}/lscript.ld")
set(USER_LINK_OTHER_FLAGS )
}
close $fd

# Copy linker script from platform export if app template did not provide one.
set lscript_src [file join $root Final_HDC ps7_cortexa9_0 standalone_domain bsp ps7_cortexa9_0 libsrc standalone_v9_2 src lscript.ld]
if {![file exists $lscript_src]} {
  set lscript_src [file join $root Final_HDC export Final_HDC sw Final_HDC standalone_domain bsp lscript.ld]
}
if {[file exists $lscript_src]} {
  file copy -force $lscript_src [file join $app_src lscript.ld]
}

app config -build-config Release
app build -name $app_name

puts "Built: [file join $app_dir build $app_name.elf]"
