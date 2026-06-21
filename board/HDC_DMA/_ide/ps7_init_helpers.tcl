# Safe PS7 init helpers for xsdb scripts.
#
# Always source ps7_init.tcl at global scope. Sourcing it from inside a proc
# leaves PCW_SILICON_VER_* as local variables and ps7_init fails with:
#   can't read "PCW_SILICON_VER_1_0": no such variable

proc hdc_source_ps7_init {script} {
    if {![file exists $script]} {
        error "Missing ps7 init script: $script"
    }
    if {![info exists ::hdc_ps7_init_loaded]} {
        uplevel #0 [list source $script]
        set ::hdc_ps7_init_loaded 1
    }
}

proc hdc_run_ps7_init {script} {
    hdc_source_ps7_init $script

    if {[catch {targets -set -nocase -filter {name =~ "APU*"}} err]} {
        error "Could not select APU target for PS7 init: $err"
    }
    catch {stop}

    ps7_init
    ps7_post_config
}
