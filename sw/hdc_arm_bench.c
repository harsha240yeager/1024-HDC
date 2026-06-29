/*
 * hdc_arm_bench.c — ARM-only HDC timing benchmark (Cortex-A9, no PL accelerator).
 *
 * Measures encode + masked-Hamming classify on golden co-sim windows using
 * sw/hdc_arm_ref.c (same algorithm as python_ref/hdc_ref / RTL encoder path).
 *
 * JTAG DDR readback @ 0x00100400, magic 0xBEC00006.
 *
 * Sources: hdc_arm_bench.c, hdc_arm_ref.c, golden_vectors.h, arm_bench_data.h
 */

#include "arm_bench_data.h"
#include "golden_vectors.h"
#include "hdc_arm_ref.h"

#include "xil_cache.h"
#include "xil_io.h"
#include "xil_printf.h"
#include "xparameters.h"
#include "xtime_l.h"

#ifndef BENCH_ITERS
#define BENCH_ITERS 1000U
#endif

#ifndef BENCH_BATCH_WINDOWS
#define BENCH_BATCH_WINDOWS 200U
#endif

#define HDC_ARM_D        1024
#define HDC_ARM_CNT_BITS 6
#define HDC_ARM_WORDS    16U
#define ARM_BENCH_N_CLASS  8U

#define CPU_HZ           XPAR_CPU_CORTEXA9_CORE_CLOCK_FREQ_HZ
#define GLOBAL_TMR_HZ    (XPAR_CPU_CORTEXA9_CORE_CLOCK_FREQ_HZ / 2U)

#define ARM_BENCH_BASE   0x00100400U
#define ARM_BENCH_MAGIC  0xBEC00006U
#define ARM_BENCH_DONE   1U
#define ARM_BENCH_BYTES  0x40U

static HdcArmMem g_mem;
static uint64_t g_query[HDC_ARM_WORDS];
static uint64_t g_protos[ARM_BENCH_N_CLASS][HDC_ARM_WORDS];
static uint64_t g_mask[HDC_ARM_WORDS];

static void bench_wr(u32 off, u32 val)
{
    Xil_Out32(ARM_BENCH_BASE + off, val);
}

static void bench_flush(void)
{
    Xil_DCacheFlushRange((INTPTR)ARM_BENCH_BASE, ARM_BENCH_BYTES);
}

static u32 ticks_to_us(XTime ticks)
{
    if (GLOBAL_TMR_HZ == 0U)
        return 0U;
    return (u32)((ticks * 1000000ULL) / (u64)GLOBAL_TMR_HZ);
}

static void publish(u32 status, u32 iters, u32 min_us, u32 max_us, u32 mean_us,
                    u32 throughput, u32 golden_errors, u32 golden_checked)
{
    bench_wr(0x00, ARM_BENCH_MAGIC);
    bench_wr(0x04, status);
    bench_wr(0x08, CPU_HZ);
    bench_wr(0x0C, GLOBAL_TMR_HZ);
    bench_wr(0x10, iters);
    bench_wr(0x14, min_us);
    bench_wr(0x18, max_us);
    bench_wr(0x1C, mean_us);
    bench_wr(0x20, throughput);
    bench_wr(0x24, golden_errors);
    bench_wr(0x28, golden_checked);
    bench_flush();
}

static int arm_infer_timed(u32 l0, u32 l1, u32 l2, XTime *elapsed, int *pred_out)
{
    int grid[HDC_ARM_N_CH][HDC_ARM_N_FEAT];
    int dist;
    XTime t0, t1;

    hdc_arm_unpack_levels(l0, l1, l2, grid);
    XTime_GetTime(&t0);
    hdc_arm_encode_grid(&g_mem, grid, g_query);
    *pred_out = hdc_arm_classify(g_query, g_protos, g_mask, (int)ARM_BENCH_N_CLASS,
                                 (int)HDC_ARM_WORDS, &dist);
    XTime_GetTime(&t1);
    *elapsed = t1 - t0;
    return 0;
}

int main(void)
{
    u32 i, n = BENCH_ITERS;
    u32 min_us = 0xFFFFFFFFU, max_us = 0U, sum_us = 0U;
    u32 golden_errors = 0U;
    u32 golden_checked = 0U;
    XTime elapsed;

    xil_printf("\r\n=== ARM HDC bench (PS software, hdc_arm_ref) ===\r\n");

    if (hdc_arm_load_mem_embedded(&g_mem, HDC_ARM_D, HDC_ARM_CNT_BITS,
                                  arm_im_channel, arm_im_feature, arm_im_value) != 0) {
        xil_printf("ERROR: item mem load\r\n");
        publish(2U, 0U, 0U, 0U, 0U, 0U, 1U, 0U);
        return 1;
    }

    for (i = 0U; i < HDC_ARM_WORDS; i++)
        g_mask[i] = golden_mask64[i];

    for (i = 0U; i < ARM_BENCH_N_CLASS; i++) {
        u32 base = i * GOLDEN_WORDS64;
        u32 w;
        for (w = 0U; w < HDC_ARM_WORDS; w++)
            g_protos[i][w] = golden_proto64[base + w];
    }

    publish(0U, n, 0U, 0U, 0U, 0U, 0U, 0U);

    for (i = 0U; i < n; i++) {
        u32 c = i % GOLDEN_N_CASES;
        int pred;
        u32 us;

        arm_infer_timed(golden_levels0[c], golden_levels1[c], golden_levels2[c],
                        &elapsed, &pred);
        us = ticks_to_us(elapsed);
        if (us < min_us)
            min_us = us;
        if (us > max_us)
            max_us = us;
        sum_us += us;

        if (i < GOLDEN_N_CASES) {
            u32 expect_cls = (golden_expect[i] >> 16) & 0xFFU;
            golden_checked++;
            if ((u32)pred != expect_cls)
                golden_errors++;
        }
    }

    {
        u32 mean_us = (n > 0U) ? (sum_us / n) : 0U;
        u32 tput = (mean_us > 0U) ? (1000000U / mean_us) : 0U;
        xil_printf("ARM HDC: iters=%lu min=%lu max=%lu mean=%lu us  tput=%lu win/s\r\n",
                   (unsigned long)n, (unsigned long)min_us, (unsigned long)max_us,
                   (unsigned long)mean_us, (unsigned long)tput);
        xil_printf("Golden spot-check: errors=%lu checked=%lu\r\n",
                   (unsigned long)golden_errors, (unsigned long)golden_checked);
        publish(ARM_BENCH_DONE, n, min_us, max_us, mean_us, tput,
                golden_errors, golden_checked);
    }

    /* Sustained batch (back-to-back, no extra timing overhead) */
    {
        u32 batch_n = BENCH_BATCH_WINDOWS;
        if (batch_n > GOLDEN_N_CASES)
            batch_n = GOLDEN_N_CASES;
        XTime t0, t1;
        XTime_GetTime(&t0);
        for (i = 0U; i < batch_n; i++) {
            int grid[HDC_ARM_N_CH][HDC_ARM_N_FEAT];
            int pred, dist;
            hdc_arm_unpack_levels(golden_levels0[i], golden_levels1[i], golden_levels2[i], grid);
            hdc_arm_encode_grid(&g_mem, grid, g_query);
            pred = hdc_arm_classify(g_query, g_protos, g_mask, (int)ARM_BENCH_N_CLASS,
                                    (int)HDC_ARM_WORDS, &dist);
            (void)pred;
        }
        XTime_GetTime(&t1);
        {
            u32 batch_us = ticks_to_us(t1 - t0);
            u32 batch_tput = (batch_us > 0U) ? ((batch_n * 1000000U) / batch_us) : 0U;
            xil_printf("ARM HDC batch: n=%lu total=%lu us  tput=%lu win/s\r\n",
                       (unsigned long)batch_n, (unsigned long)batch_us,
                       (unsigned long)batch_tput);
        }
    }

    xil_printf("=== ARM HDC bench DONE ===\r\n");
    return 0;
}
