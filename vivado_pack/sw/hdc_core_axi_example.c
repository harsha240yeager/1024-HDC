/*
 * hdc_core_axi_example.c — single-window smoke test (dummy protos).
 * See hdc_core_golden_test.c for full 200-case board golden test.
 */

#include "hdc_core_regs.h"
#include "xil_printf.h"

int main(void)
{
    u32 prototypes[HDC_N_CLASS][HDC_VEC_WORDS];
    u32 mask[HDC_VEC_WORDS];
    u32 levels[3] = { 0x12345678U, 0x9ABCDEF0U, 0x0000ABCDU };
    u32 k, i, idx = 0U, dist = 0U;
    int rc;

    xil_printf("HDC core AXI example start\r\n");

    for (k = 0U; k < HDC_N_CLASS; ++k)
        for (i = 0U; i < HDC_VEC_WORDS; ++i)
            prototypes[k][i] = (k << 24) | i;
    for (i = 0U; i < HDC_VEC_WORDS; ++i)
        mask[i] = 0xFFFFFFFFU;

    for (k = 0U; k < HDC_N_CLASS; ++k) {
        hdc_fill_staging_words(prototypes[k]);
        hdc_wr(HDC_REG_PROTO_IDX, k);
        hdc_wr(HDC_REG_CTRL, HDC_CTRL_LOAD_PROTO);
    }
    hdc_fill_staging_words(mask);
    hdc_wr(HDC_REG_CTRL, HDC_CTRL_LOAD_MASK);

    rc = hdc_classify_levels(levels[0], levels[1], levels[2], &idx, &dist);
    if (rc != 0) {
        xil_printf("ERROR: inference timed out\r\n");
        return -1;
    }

    xil_printf("Predicted class = %lu  (Hamming distance = %lu)\r\n",
               (unsigned long)idx, (unsigned long)dist);
    xil_printf("HDC core AXI example complete\r\n");
    return 0;
}
