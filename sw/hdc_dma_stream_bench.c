/*
 * hdc_dma_stream_bench.c
 *
 * Phase 2 board benchmark: time one DMA stream inference (S2MM start + MM2S +
 * busy-wait) for BENCH_ITERS windows, then verify all golden cases.
 *
 * Publishes results to DDR @ 0x00100000 for JTAG readback (same layout as
 * Phase 1 hdc_core_bench.c). Magic 0xBEC00002 marks Phase 2 DMA bench.
 *
 * Sources: hdc_dma_stream_bench.c, hdc_dma_stream.c, hdc_core_regs.c,
 *          golden_vectors.h
 *
 * Optional: -DBENCH_ITERS=5000
 */

#include "golden_vectors.h"
#include "hdc_core_regs.h"
#include "hdc_dma_stream.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xparameters.h"
#include "xtime_l.h"
#include "sleep.h"

#ifndef BENCH_ITERS
#define BENCH_ITERS 1000U
#endif

#ifndef GOLDEN_MAX_CASES
#define GOLDEN_MAX_CASES GOLDEN_N_CASES
#endif

#define CPU_HZ          XPAR_CPU_CORTEXA9_CORE_CLOCK_FREQ_HZ
#define GLOBAL_TMR_HZ   (XPAR_CPU_CORTEXA9_CORE_CLOCK_FREQ_HZ / 2U)

#define BENCH_RESULTS_BASE   0x00100000U
#define BENCH_MAGIC          0xBEC00002U
#define BENCH_STATUS_RUNNING 0U
#define BENCH_STATUS_DONE    1U
#define BENCH_RESULTS_BYTES  0x40U

#define PHASE1_BASELINE_US   3U

static u32 in_buf[HDC_IN_BEATS] __attribute__((aligned(64)));
static u32 out_buf[HDC_OUT_BEATS] __attribute__((aligned(64)));

static void bench_results_wr(u32 off, u32 val)
{
    Xil_Out32(BENCH_RESULTS_BASE + off, val);
}

static void bench_results_flush(void)
{
    Xil_DCacheFlushRange((INTPTR)BENCH_RESULTS_BASE, BENCH_RESULTS_BYTES);
}

static void bench_publish_results(u32 status, u32 iters, u32 min_us, u32 max_us,
                                  u32 mean_us, u32 throughput,
                                  u32 golden_errors, u32 golden_checked)
{
    bench_results_wr(0x00, BENCH_MAGIC);
    bench_results_wr(0x04, status);
    bench_results_wr(0x08, CPU_HZ);
    bench_results_wr(0x0C, GLOBAL_TMR_HZ);
    bench_results_wr(0x10, iters);
    bench_results_wr(0x14, min_us);
    bench_results_wr(0x18, max_us);
    bench_results_wr(0x1C, mean_us);
    bench_results_wr(0x20, throughput);
    bench_results_wr(0x24, golden_errors);
    bench_results_wr(0x28, golden_checked);
    bench_results_flush();
}

static u32 ticks_to_us(XTime ticks)
{
    if (GLOBAL_TMR_HZ == 0U)
        return 0U;
    return (u32)((ticks * 1000000ULL) / (u64)GLOBAL_TMR_HZ);
}

static int stream_timed(u32 lvl0, u32 lvl1, u32 lvl2, XTime *elapsed)
{
    XTime t0, t1;

    in_buf[0] = lvl0;
    in_buf[1] = lvl1;
    in_buf[2] = lvl2;

    XTime_GetTime(&t0);
    hdc_dma_stream_one(in_buf, out_buf);
    XTime_GetTime(&t1);

    *elapsed = t1 - t0;
    return 0;
}

static u32 run_golden_batch(u32 *errors_out)
{
    u32 c, k, errors = 0U, checked = 0U;
    u32 n_cases = GOLDEN_N_CASES;

    if (GOLDEN_MAX_CASES < n_cases)
        n_cases = GOLDEN_MAX_CASES;

    for (k = 0U; k < GOLDEN_N_CLASS; ++k)
        hdc_load_prototype_from64(k, golden_proto64);
    hdc_load_mask_from64(golden_mask64);

    for (c = 0U; c < n_cases; ++c) {
        u32 exp, exp_idx, exp_dist, got_idx, got_dist;

        in_buf[0] = golden_levels0[c];
        in_buf[1] = golden_levels1[c];
        in_buf[2] = golden_levels2[c];
        hdc_dma_stream_one(in_buf, out_buf);

        checked++;
        exp = golden_expect[c];
        exp_idx  = (exp >> 16) & ((1U << HDC_IDX_W) - 1U);
        exp_dist = exp & ((1U << HDC_DIST_W) - 1U);
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

    *errors_out = errors;
    return checked;
}

int main(void)
{
    u32 i, k, timeouts = 0U;
    u32 n_iters = BENCH_ITERS;
    u32 min_us = 0xFFFFFFFFU, max_us = 0U, mean_us = 0U;
    u64 sum_us = 0ULL;
    XTime dt, min_ticks = (XTime)-1, max_ticks = 0U, mean_ticks = 0U;
    u64 sum_ticks = 0ULL;
    u32 golden_errors = 0U, golden_checked = 0U;
    u32 idx_case = 0U;
    int rc;

    rc = hdc_dma_init();
    if (rc != 0) {
        xil_printf("DMA init failed (%d)\r\n", rc);
        return -1;
    }

    bench_publish_results(BENCH_STATUS_RUNNING, n_iters, 0U, 0U, 0U, 0U, 0U, 0U);

    xil_printf("==================================================\r\n");
    xil_printf("HDC Phase 2 bench (DMA stream @ 0x%08x)\r\n", (u32)XPAR_AXIDMA_0_BASEADDR);
    xil_printf("CPU=%lu Hz  global_tmr=%lu Hz  iters=%lu\r\n",
               (unsigned long)CPU_HZ, (unsigned long)GLOBAL_TMR_HZ,
               (unsigned long)n_iters);
    xil_printf("Phase 1 baseline: ~%u us/window (AXI-Lite poll)\r\n", PHASE1_BASELINE_US);
    xil_printf("==================================================\r\n");

    for (k = 0U; k < GOLDEN_N_CLASS; ++k)
        hdc_load_prototype_from64(k, golden_proto64);
    hdc_load_mask_from64(golden_mask64);

    for (i = 0U; i < n_iters; ++i) {
        u32 us;

        rc = stream_timed(golden_levels0[idx_case], golden_levels1[idx_case],
                          golden_levels2[idx_case], &dt);
        idx_case++;
        if (idx_case >= GOLDEN_N_CASES)
            idx_case = 0U;

        if (rc != 0) {
            timeouts++;
            continue;
        }

        if (dt < min_ticks)
            min_ticks = dt;
        if (dt > max_ticks)
            max_ticks = dt;
        sum_ticks += (u64)dt;

        us = ticks_to_us(dt);
        if (us < min_us)
            min_us = us;
        if (us > max_us)
            max_us = us;
        sum_us += (u64)us;
    }

    if (n_iters > timeouts) {
        mean_ticks = (XTime)(sum_ticks / (u64)(n_iters - timeouts));
        mean_us = (u32)(sum_us / (u64)(n_iters - timeouts));
    }

    xil_printf("--- Latency (DMA stream one window, incl. busy-wait) ---\r\n");
    if (timeouts > 0U)
        xil_printf("timeouts = %lu / %lu\r\n",
                   (unsigned long)timeouts, (unsigned long)n_iters);

    if (n_iters > timeouts) {
        xil_printf("min  = %lu us  (%llu ticks)\r\n",
                   (unsigned long)ticks_to_us(min_ticks),
                   (unsigned long long)min_ticks);
        xil_printf("max  = %lu us  (%llu ticks)\r\n",
                   (unsigned long)ticks_to_us(max_ticks),
                   (unsigned long long)max_ticks);
        xil_printf("mean = %lu us  (%llu ticks)\r\n",
                   (unsigned long)mean_us,
                   (unsigned long long)mean_ticks);
        if (mean_us > 0U)
            xil_printf("throughput ~ %lu windows/s (1/mean)\r\n",
                       (unsigned long)(1000000U / mean_us));
        if (mean_us > PHASE1_BASELINE_US)
            xil_printf("vs Phase 1 baseline (%u us): +%lu us (slower)\r\n",
                       PHASE1_BASELINE_US,
                       (unsigned long)(mean_us - PHASE1_BASELINE_US));
        else if (mean_us > 0U)
            xil_printf("vs Phase 1 baseline (%u us): %lu us faster\r\n",
                       PHASE1_BASELINE_US,
                       (unsigned long)(PHASE1_BASELINE_US - mean_us));
    } else {
        xil_printf("TIMEOUT: no successful inferences\r\n");
    }

    xil_printf("--- Golden batch check ---\r\n");
    golden_checked = run_golden_batch(&golden_errors);

    if (golden_errors == 0U)
        xil_printf("PASS: %lu/%lu stream golden cases\r\n",
                   (unsigned long)golden_checked,
                   (unsigned long)golden_checked);
    else
        xil_printf("FAIL: %lu errors / %lu checked\r\n",
                   (unsigned long)golden_errors,
                   (unsigned long)golden_checked);

    xil_printf("==================================================\r\n");

    {
        u32 throughput = (mean_us > 0U) ? (1000000U / mean_us) : 0U;
        u32 rmin = (n_iters > timeouts) ? ticks_to_us(min_ticks) : 0U;
        u32 rmax = (n_iters > timeouts) ? ticks_to_us(max_ticks) : 0U;

        bench_publish_results(BENCH_STATUS_DONE, n_iters, rmin, rmax, mean_us,
                              throughput, golden_errors, golden_checked);
    }

    while (1)
        sleep(1);

    if (timeouts > 0U || golden_errors > 0U)
        return -1;
    return 0;
}
