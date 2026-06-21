#include "hdc_dma_stream.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xtime_l.h"

static XAxiDma dma;

int hdc_dma_init(void)
{
    XAxiDma_Config *cfg = XAxiDma_LookupConfig(HDC_DMA_DEV_ID);

    if (cfg == NULL)
        return -1;
    if (XAxiDma_CfgInitialize(&dma, cfg) != XST_SUCCESS)
        return -2;
    if (XAxiDma_HasSg(&dma)) {
        xil_printf("HDC DMA: scatter-gather not supported in this driver\r\n");
        return -3;
    }
    return 0;
}

static void dma_stream_xfer_one(const u32 *in3, u32 *out1, HdcDmaStreamTiming *timing)
{
    const u32 in_bytes  = (u32)(HDC_IN_BEATS * sizeof(u32));
    const u32 out_bytes = (u32)(HDC_OUT_BEATS * sizeof(u32));
    XTime t0, t1, t2, t3;

    Xil_DCacheFlushRange((INTPTR)in3, in_bytes);
    Xil_DCacheInvalidateRange((INTPTR)out1, out_bytes);

    if (timing != NULL) {
        XTime_GetTime(&t0);
    }

    /* S2MM must be running before results arrive (avoid ST_OUT stall). */
    XAxiDma_SimpleTransfer(&dma, (UINTPTR)out1, out_bytes, XAXIDMA_DEVICE_TO_DMA);
    XAxiDma_SimpleTransfer(&dma, (UINTPTR)in3, in_bytes, XAXIDMA_DMA_TO_DEVICE);

    if (timing != NULL) {
        XTime_GetTime(&t1);
        timing->ticks_mm2s_submit = (u64)(t1 - t0);
    }

    while (XAxiDma_Busy(&dma, XAXIDMA_DMA_TO_DEVICE))
        ;

    if (timing != NULL) {
        XTime_GetTime(&t2);
        timing->ticks_mm2s_done = (u64)(t2 - t0);
    }

    while (XAxiDma_Busy(&dma, XAXIDMA_DEVICE_TO_DMA))
        ;

    if (timing != NULL) {
        XTime_GetTime(&t3);
        timing->ticks_s2mm_done = (u64)(t3 - t0);
        timing->ticks_total = timing->ticks_s2mm_done;
    }

    Xil_DCacheInvalidateRange((INTPTR)out1, out_bytes);
}

void hdc_dma_stream_one(const u32 *in3, u32 *out1)
{
    dma_stream_xfer_one(in3, out1, NULL);
}

int hdc_dma_stream_one_timed(const u32 *in3, u32 *out1, HdcDmaStreamTiming *timing)
{
    if (timing == NULL)
        return -1;
    timing->ticks_total = 0U;
    timing->ticks_mm2s_submit = 0U;
    timing->ticks_mm2s_done = 0U;
    timing->ticks_s2mm_done = 0U;
    dma_stream_xfer_one(in3, out1, timing);
    return 0;
}

int hdc_dma_stream_batch(const u32 *in_words, u32 *out_words, u32 n_windows)
{
    u32 i;
    u32 in_bytes  = n_windows * HDC_IN_BEATS * (u32)sizeof(u32);
    u32 out_bytes = n_windows * HDC_OUT_BEATS * (u32)sizeof(u32);

    if (n_windows == 0U)
        return 0;

    /* Simple-mode AXI DMA + stream wrapper (s_axis_tready only in ST_IN) cannot
     * sustain one long MM2S burst for N windows — the PS hangs in Busy().
     * Run N back-to-back single-window transfers; proto/mask stay loaded.
     * True one-transfer batch needs SG DMA with per-window TLAST (see README). */
    Xil_DCacheFlushRange((INTPTR)in_words, in_bytes);
    Xil_DCacheInvalidateRange((INTPTR)out_words, out_bytes);

    for (i = 0U; i < n_windows; ++i) {
        hdc_dma_stream_one(in_words + (i * HDC_IN_BEATS),
                           out_words + (i * HDC_OUT_BEATS));
    }

    Xil_DCacheInvalidateRange((INTPTR)out_words, out_bytes);
    return 0;
}

void hdc_dma_stream_batch_sequential(const u32 *in_words, u32 *out_words, u32 n_windows)
{
    (void)hdc_dma_stream_batch(in_words, out_words, n_windows);
}
