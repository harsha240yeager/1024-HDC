/*
 * hdc_dma_stream_batch_bench.c — Phase 3 sustained throughput + E2E latency proxy.
 *
 * Sustained: BATCH_WINDOWS sequential DMA inferences (proto/mask loaded once).
 * E2E proxy: global timer from S2MM+MM2S submit through both channels idle
 *            (approximates input launch → result available in DDR).
 *
 * Publishes @ 0x00100200, magic 0xBEC00004.
 */

#include "golden_vectors.h"
#include "hdc_core_regs.h"
#include "hdc_dma_stream.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xparameters.h"
#include "xtime_l.h"
#include "sleep.h"

#ifndef BATCH_WINDOWS
#define BATCH_WINDOWS 10000U
#endif

#ifndef E2E_SAMPLES
#define E2E_SAMPLES 100U
#endif

#define CPU_HZ         XPAR_CPU_CORTEXA9_CORE_CLOCK_FREQ_HZ
#define GLOBAL_TMR_HZ  (XPAR_CPU_CORTEXA9_CORE_CLOCK_FREQ_HZ / 2U)

#define RESULTS_BASE   0x00100200U
#define RESULTS_MAGIC  0xBEC00004U
#define RESULTS_DONE   1U
#define RESULTS_BYTES  0x40U

static u32 in_buf[HDC_IN_BEATS] __attribute__((aligned(64)));
static u32 out_buf[HDC_OUT_BEATS] __attribute__((aligned(64)));

static void results_wr(u32 off, u32 val)
{
    Xil_Out32(RESULTS_BASE + off, val);
}

static void results_flush(void)
{
    Xil_DCacheFlushRange((INTPTR)RESULTS_BASE, RESULTS_BYTES);
}

static u32 ticks_to_us(u64 ticks)
{
    if (GLOBAL_TMR_HZ == 0U)
        return 0U;
    return (u32)((ticks * 1000000ULL) / (u64)GLOBAL_TMR_HZ);
}

static void publish(u32 status, u32 batch_n, u32 batch_total_us, u32 batch_mean_us,
                    u32 throughput, u32 e2e_mean_us, u32 e2e_mm2s_us)
{
    results_wr(0x00, RESULTS_MAGIC);
    results_wr(0x04, status);
    results_wr(0x08, CPU_HZ);
    results_wr(0x0C, GLOBAL_TMR_HZ);
    results_wr(0x10, batch_n);
    results_wr(0x14, batch_total_us);
    results_wr(0x18, batch_mean_us);
    results_wr(0x1C, throughput);
    results_wr(0x20, e2e_mean_us);
    results_wr(0x24, e2e_mm2s_us);
    results_wr(0x28, E2E_SAMPLES);
    results_flush();
}

int main(void)
{
    u32 i, k, idx = 0U;
    u32 batch_n = BATCH_WINDOWS;
    u64 batch_ticks = 0ULL, e2e_sum = 0ULL, mm2s_sum = 0ULL;
    XTime t0, t1;
    u32 batch_total_us, batch_mean_us, throughput, e2e_mean_us, e2e_mm2s_us;
    int rc;

    publish(0U, batch_n, 0U, 0U, 0U, 0U, 0U);

    xil_printf("==================================================\r\n");
    xil_printf("HDC Phase 3 batch bench (DMA stream)\r\n");
    xil_printf("  sustained windows = %lu\r\n", (unsigned long)batch_n);
    xil_printf("  E2E timed samples = %lu\r\n", (unsigned long)E2E_SAMPLES);
    xil_printf("==================================================\r\n");

    rc = hdc_dma_init();
    if (rc != 0) {
        xil_printf("DMA init failed (%d)\r\n", rc);
        return -1;
    }

    for (k = 0U; k < GOLDEN_N_CLASS; ++k)
        hdc_load_prototype_from64(k, golden_proto64);
    hdc_load_mask_from64(golden_mask64);

    for (i = 0U; i < E2E_SAMPLES; ++i) {
        HdcDmaStreamTiming tm;

        in_buf[0] = golden_levels0[idx];
        in_buf[1] = golden_levels1[idx];
        in_buf[2] = golden_levels2[idx];
        idx++;
        if (idx >= GOLDEN_N_CASES)
            idx = 0U;

        hdc_dma_stream_one_timed(in_buf, out_buf, &tm);
        e2e_sum += tm.ticks_total;
        mm2s_sum += tm.ticks_mm2s_done;
    }

    XTime_GetTime(&t0);
    for (i = 0U; i < batch_n; ++i) {
        in_buf[0] = golden_levels0[idx];
        in_buf[1] = golden_levels1[idx];
        in_buf[2] = golden_levels2[idx];
        idx++;
        if (idx >= GOLDEN_N_CASES)
            idx = 0U;
        hdc_dma_stream_one(in_buf, out_buf);
    }
    XTime_GetTime(&t1);
    batch_ticks = (u64)(t1 - t0);

    batch_total_us = ticks_to_us(batch_ticks);
    batch_mean_us = (batch_n > 0U) ? (batch_total_us / batch_n) : 0U;
    throughput = (batch_mean_us > 0U) ? (1000000U / batch_mean_us) : 0U;
    e2e_mean_us = ticks_to_us(e2e_sum / (u64)E2E_SAMPLES);
    e2e_mm2s_us = ticks_to_us(mm2s_sum / (u64)E2E_SAMPLES);

    xil_printf("--- Sustained batch (%lu windows, proto loaded once) ---\r\n",
               (unsigned long)batch_n);
    xil_printf("total = %lu us  mean = %lu us/window\r\n",
               (unsigned long)batch_total_us, (unsigned long)batch_mean_us);
    xil_printf("throughput ~ %lu windows/s\r\n", (unsigned long)throughput);
    xil_printf("--- E2E proxy (submit both DMA dirs -> both idle) ---\r\n");
    xil_printf("mean = %lu us  (MM2S done @ %lu us)\r\n",
               (unsigned long)e2e_mean_us, (unsigned long)e2e_mm2s_us);
    xil_printf("==================================================\r\n");

    publish(RESULTS_DONE, batch_n, batch_total_us, batch_mean_us,
            throughput, e2e_mean_us, e2e_mm2s_us);

    while (1)
        sleep(1);

    return 0;
}
