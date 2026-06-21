/*
 * hdc_dma_stream_golden_test.c
 *
 * Phase 2 on-board golden test via AXI DMA + hdc_stream_system_bd_wrapper.
 *
 * Vitis app sources:
 *   hdc_dma_stream_golden_test.c, hdc_dma_stream.c, hdc_core_regs.c, golden_vectors.h
 * Link: xaxidma, xilffs not required.
 *
 * Platform: design with hdc_stream_system @ 0x43C00000, axi_dma @ 0x40400000
 * (enable MM2S + S2MM, 32-bit stream, no SG). Run prep_golden_test first.
 *
 * UART 115200 — expect: PASS: 200/200 stream golden cases
 */

#include "golden_vectors.h"
#include "hdc_core_regs.h"
#include "hdc_dma_stream.h"
#include "xil_cache.h"
#include "xil_printf.h"

#define GOLDEN_RESULTS_BASE  0x00100100U
#define GOLDEN_MAGIC           0xBEC00003U
#define GOLDEN_STATUS_DONE     1U
#define GOLDEN_RESULTS_BYTES   0x20U

static u32 in_buf[HDC_IN_BEATS] __attribute__((aligned(64)));
static u32 out_buf[HDC_OUT_BEATS] __attribute__((aligned(64)));

static void golden_results_publish(u32 n_cases, u32 errors)
{
    Xil_Out32(GOLDEN_RESULTS_BASE + 0x00, GOLDEN_MAGIC);
    Xil_Out32(GOLDEN_RESULTS_BASE + 0x04, GOLDEN_STATUS_DONE);
    Xil_Out32(GOLDEN_RESULTS_BASE + 0x08, n_cases);
    Xil_Out32(GOLDEN_RESULTS_BASE + 0x0C, errors);
    Xil_Out32(GOLDEN_RESULTS_BASE + 0x10, (errors == 0U) ? n_cases : (n_cases - errors));
    Xil_DCacheFlushRange((INTPTR)GOLDEN_RESULTS_BASE, GOLDEN_RESULTS_BYTES);
}

int main(void)
{
    u32 c, k, errors = 0U;
    u32 n_cases = GOLDEN_N_CASES;
    int rc;

    xil_printf("==================================================\r\n");
    xil_printf("HDC stream golden (DMA): %lu cases\r\n", (unsigned long)n_cases);
    xil_printf("==================================================\r\n");

    rc = hdc_dma_init();
    if (rc != 0) {
        xil_printf("DMA init failed (%d)\r\n", rc);
        return -1;
    }

    for (k = 0U; k < GOLDEN_N_CLASS; ++k)
        hdc_load_prototype_from64(k, golden_proto64);
    hdc_load_mask_from64(golden_mask64);

    for (c = 0U; c < n_cases; ++c) {
        u32 exp = golden_expect[c];
        u32 exp_idx  = (exp >> 16) & ((1U << HDC_IDX_W) - 1U);
        u32 exp_dist = exp & ((1U << HDC_DIST_W) - 1U);
        u32 got_idx, got_dist;

        in_buf[0] = golden_levels0[c];
        in_buf[1] = golden_levels1[c];
        in_buf[2] = golden_levels2[c];

        hdc_dma_stream_one(in_buf, out_buf);

        got_dist = out_buf[0] & ((1U << HDC_DIST_W) - 1U);
        got_idx  = (out_buf[0] >> 16) & ((1U << HDC_IDX_W) - 1U);

        if (got_idx != exp_idx || got_dist != exp_dist) {
            errors++;
            xil_printf("FAIL case %lu: exp idx=%lu dist=%lu got idx=%lu dist=%lu\r\n",
                       (unsigned long)c,
                       (unsigned long)exp_idx, (unsigned long)exp_dist,
                       (unsigned long)got_idx, (unsigned long)got_dist);
        }
    }

    xil_printf("==================================================\r\n");
    if (errors == 0U)
        xil_printf("PASS: %lu/%lu stream golden cases\r\n",
                   (unsigned long)n_cases, (unsigned long)n_cases);
    else
        xil_printf("FAIL: %lu errors / %lu\r\n",
                   (unsigned long)errors, (unsigned long)n_cases);
    xil_printf("==================================================\r\n");

    golden_results_publish(n_cases, errors);

    while (1)
        ;

    return (errors == 0U) ? 0 : -1;
}
