/*
 * hdc_core_golden_test.c
 *
 * On-board golden test: mirrors tb/tb_core_axi_cosim.sv against Python vectors.
 *
 * Before building in Vitis (from repo root):
 *   powershell -File scripts/prep_golden_test.ps1
 * or:
 *   python python_ref/generate_vectors.py --core --out-dir python_ref/vectors/cosim_core --count 200 --seed 42
 *   python python_ref/tools/export_golden_c.py python_ref/vectors/cosim_core sw/golden_vectors.h
 *
 * Vitis app sources: hdc_core_golden_test.c, hdc_core_regs.c, golden_vectors.h
 * Platform: same .xsa as smoke test (hdc_core_axi_lite @ 0x43C00000)
 * Bitstream must use item_mem_*.mem from the same cosim_core dir (seed 42).
 *
 * UART 115200 — expect: PASS: 200/200 golden cases
 */

#include "golden_vectors.h"
#include "hdc_core_regs.h"
#include "xil_printf.h"

#ifndef GOLDEN_MAX_CASES
#define GOLDEN_MAX_CASES GOLDEN_N_CASES
#endif

int main(void)
{
    u32 c, k, errors = 0U, checked = 0U;
    u32 n_cases = GOLDEN_N_CASES;

    if (GOLDEN_MAX_CASES < n_cases)
        n_cases = GOLDEN_MAX_CASES;

    xil_printf("==================================================\r\n");
    xil_printf("HDC golden test: %lu cases (D=1024, N_CLASS=%lu)\r\n",
               (unsigned long)n_cases, (unsigned long)GOLDEN_N_CLASS);
    xil_printf("==================================================\r\n");

    for (k = 0U; k < GOLDEN_N_CLASS; ++k)
        hdc_load_prototype_from64(k, golden_proto64);
    hdc_load_mask_from64(golden_mask64);

    for (c = 0U; c < n_cases; ++c) {
        u32 got_idx, got_dist, exp, exp_idx, exp_dist;
        int rc;

        rc = hdc_classify_levels(golden_levels0[c], golden_levels1[c],
                                 golden_levels2[c], &got_idx, &got_dist);
        checked++;

        exp = golden_expect[c];
        exp_idx  = (exp >> 16) & ((1U << HDC_IDX_W) - 1U);
        exp_dist = exp & ((1U << HDC_DIST_W) - 1U);

        if (rc != 0 || got_idx != exp_idx || got_dist != exp_dist) {
            errors++;
            xil_printf("--------------------------------------------------\r\n");
            xil_printf("FAIL case %lu\r\n", (unsigned long)c);
            if (rc != 0)
                xil_printf("  inference timed out\r\n");
            xil_printf("  expected idx=%lu dist=%lu\r\n",
                       (unsigned long)exp_idx, (unsigned long)exp_dist);
            xil_printf("  got      idx=%lu dist=%lu\r\n",
                       (unsigned long)got_idx, (unsigned long)got_dist);
            xil_printf("--------------------------------------------------\r\n");
        }
    }

    xil_printf("==================================================\r\n");
    if (errors == 0U)
        xil_printf("PASS: %lu/%lu golden cases\r\n",
                   (unsigned long)checked, (unsigned long)checked);
    else
        xil_printf("FAIL: %lu errors / %lu checked\r\n",
                   (unsigned long)errors, (unsigned long)checked);
    xil_printf("==================================================\r\n");

    return (errors == 0U) ? 0 : -1;
}
