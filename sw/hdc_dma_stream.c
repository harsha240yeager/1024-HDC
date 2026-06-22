#include "hdc_dma_stream.h"
#include "xaxidma_bdring.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xtime_l.h"

#ifndef HDC_DMA_SG_BD_COUNT
#define HDC_DMA_SG_BD_COUNT 256U
#endif

#define HDC_DMA_BD_ALIGN        64U
#define HDC_DMA_IN_BYTES        (HDC_IN_BEATS * (u32)sizeof(u32))
#define HDC_DMA_OUT_BYTES       (HDC_OUT_BEATS * (u32)sizeof(u32))
#define HDC_DMA_BD_RING_BYTES   (HDC_DMA_SG_BD_COUNT * 64U)

static XAxiDma dma;
static int sg_rings_ready;

static u8 tx_bd_mem[HDC_DMA_BD_RING_BYTES] __attribute__((aligned(HDC_DMA_BD_ALIGN)));
static u8 rx_bd_mem[HDC_DMA_BD_RING_BYTES] __attribute__((aligned(HDC_DMA_BD_ALIGN)));

static int hdc_dma_sg_init_rings(void)
{
    XAxiDma_BdRing *tx = XAxiDma_GetTxRing(&dma);
    XAxiDma_BdRing *rx = XAxiDma_GetRxRing(&dma);
    XAxiDma_Bd bd_template;
    int st;

    if (sg_rings_ready)
        return 0;

    XAxiDma_BdRingIntDisable(tx, XAXIDMA_IRQ_ALL_MASK);
    XAxiDma_BdRingIntDisable(rx, XAXIDMA_IRQ_ALL_MASK);
    XAxiDma_BdRingSetCoalesce(tx, 1, 0);
    XAxiDma_BdRingSetCoalesce(rx, 1, 0);

    st = (int)XAxiDma_BdRingCreate(tx, (UINTPTR)tx_bd_mem, (UINTPTR)tx_bd_mem,
                                   HDC_DMA_BD_ALIGN, (int)HDC_DMA_SG_BD_COUNT);
    if (st != XST_SUCCESS)
        return -10;
    st = (int)XAxiDma_BdRingCreate(rx, (UINTPTR)rx_bd_mem, (UINTPTR)rx_bd_mem,
                                   HDC_DMA_BD_ALIGN, (int)HDC_DMA_SG_BD_COUNT);
    if (st != XST_SUCCESS)
        return -11;

    XAxiDma_BdClear(&bd_template);
    st = (int)XAxiDma_BdRingClone(tx, &bd_template);
    if (st != XST_SUCCESS)
        return -14;
    st = (int)XAxiDma_BdRingClone(rx, &bd_template);
    if (st != XST_SUCCESS)
        return -15;

    st = XAxiDma_BdRingStart(tx);
    if (st != XST_SUCCESS)
        return -12;
    st = XAxiDma_BdRingStart(rx);
    if (st != XST_SUCCESS)
        return -13;

    sg_rings_ready = 1;
    return 0;
}

int hdc_dma_init(void)
{
    XAxiDma_Config *cfg = XAxiDma_LookupConfig(HDC_DMA_DEV_ID);

    sg_rings_ready = 0;
    if (cfg == NULL)
        return -1;
    if (XAxiDma_CfgInitialize(&dma, cfg) != XST_SUCCESS)
        return -2;
    if (XAxiDma_HasSg(&dma))
        return hdc_dma_sg_init_rings();
    return 0;
}

int hdc_dma_has_sg(void)
{
    return XAxiDma_HasSg(&dma) ? 1 : 0;
}

static void dma_simple_xfer_one(const u32 *in3, u32 *out1, HdcDmaStreamTiming *timing)
{
    const u32 in_bytes  = HDC_DMA_IN_BYTES;
    const u32 out_bytes = HDC_DMA_OUT_BYTES;
    XTime t0, t1, t2, t3;

    Xil_DCacheFlushRange((INTPTR)in3, in_bytes);
    Xil_DCacheInvalidateRange((INTPTR)out1, out_bytes);

    if (timing != NULL)
        XTime_GetTime(&t0);

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

static int dma_sg_xfer(const u32 *in_words, u32 *out_words, u32 n_windows,
                       HdcDmaStreamTiming *timing)
{
    XAxiDma_BdRing *tx = XAxiDma_GetTxRing(&dma);
    XAxiDma_BdRing *rx = XAxiDma_GetRxRing(&dma);
    XAxiDma_Bd *tx_bds, *rx_bds, *bdp;
    u32 in_bytes = n_windows * HDC_DMA_IN_BYTES;
    u32 out_bytes = n_windows * HDC_DMA_OUT_BYTES;
    u32 tx_len_mask = tx->MaxTransferLen;
    u32 rx_len_mask = rx->MaxTransferLen;
    int i, rc, tx_done = 0, rx_done = 0;
    XTime t0 = 0, t1 = 0, t2 = 0, t3 = 0;

    if (n_windows == 0U)
        return 0;
    if (n_windows > HDC_DMA_SG_BD_COUNT)
        return -1;

    Xil_DCacheFlushRange((INTPTR)in_words, in_bytes);
    Xil_DCacheInvalidateRange((INTPTR)out_words, out_bytes);

    rc = XAxiDma_BdRingAlloc(tx, (int)n_windows, &tx_bds);
    if (rc != XST_SUCCESS)
        return -2;
    rc = XAxiDma_BdRingAlloc(rx, (int)n_windows, &rx_bds);
    if (rc != XST_SUCCESS) {
        XAxiDma_BdRingUnAlloc(tx, (int)n_windows, tx_bds);
        return -3;
    }

    bdp = tx_bds;
    for (i = 0; i < (int)n_windows; ++i) {
        u32 ctrl = XAXIDMA_BD_CTRL_TXSOF_MASK | XAXIDMA_BD_CTRL_TXEOF_MASK;
        u32 off = (u32)i * HDC_IN_BEATS;

        XAxiDma_BdSetCtrl(bdp, ctrl);
        XAxiDma_BdSetBufAddr(bdp, (UINTPTR)(in_words + off));
        XAxiDma_BdSetId(bdp, (UINTPTR)(in_words + off));
        rc = XAxiDma_BdSetLength(bdp, HDC_DMA_IN_BYTES, tx_len_mask);
        if (rc != XST_SUCCESS)
            goto sg_fail;
        bdp = (XAxiDma_Bd *)XAxiDma_BdRingNext(tx, bdp);
    }

    bdp = rx_bds;
    for (i = 0; i < (int)n_windows; ++i) {
        u32 off = (u32)i * HDC_OUT_BEATS;

        XAxiDma_BdSetCtrl(bdp, 0);
        XAxiDma_BdSetBufAddr(bdp, (UINTPTR)(out_words + off));
        XAxiDma_BdSetId(bdp, (UINTPTR)(out_words + off));
        rc = XAxiDma_BdSetLength(bdp, HDC_DMA_OUT_BYTES, rx_len_mask);
        if (rc != XST_SUCCESS)
            goto sg_fail;
        bdp = (XAxiDma_Bd *)XAxiDma_BdRingNext(rx, bdp);
    }

    if (timing != NULL)
        XTime_GetTime(&t0);

    Xil_DCacheFlushRange((INTPTR)tx_bd_mem, HDC_DMA_BD_RING_BYTES);
    Xil_DCacheFlushRange((INTPTR)rx_bd_mem, HDC_DMA_BD_RING_BYTES);

    rc = XAxiDma_BdRingToHw(rx, (int)n_windows, rx_bds);
    if (rc != XST_SUCCESS)
        goto sg_fail;
    rc = XAxiDma_BdRingToHw(tx, (int)n_windows, tx_bds);
    if (rc != XST_SUCCESS)
        goto sg_fail;

    if (timing != NULL) {
        XTime_GetTime(&t1);
        timing->ticks_mm2s_submit = (u64)(t1 - t0);
    }

    while (tx_done < (int)n_windows || rx_done < (int)n_windows) {
        XAxiDma_Bd *done;
        int got;

        got = XAxiDma_BdRingFromHw(rx, XAXIDMA_ALL_BDS, &done);
        if (got > 0) {
            XAxiDma_BdRingFree(rx, got, done);
            rx_done += got;
        }
        got = XAxiDma_BdRingFromHw(tx, XAXIDMA_ALL_BDS, &done);
        if (got > 0) {
            if (timing != NULL && tx_done == 0)
                XTime_GetTime(&t2);
            XAxiDma_BdRingFree(tx, got, done);
            tx_done += got;
        }
    }

    if (timing != NULL) {
        XTime_GetTime(&t3);
        timing->ticks_mm2s_done = (u64)(t2 - t0);
        timing->ticks_s2mm_done = (u64)(t3 - t0);
        timing->ticks_total = timing->ticks_s2mm_done;
    }

    Xil_DCacheInvalidateRange((INTPTR)out_words, out_bytes);
    return 0;

sg_fail:
    XAxiDma_BdRingUnAlloc(tx, (int)n_windows, tx_bds);
    XAxiDma_BdRingUnAlloc(rx, (int)n_windows, rx_bds);
    return -4;
}

static void dma_stream_xfer_one(const u32 *in3, u32 *out1, HdcDmaStreamTiming *timing)
{
    if (XAxiDma_HasSg(&dma)) {
        (void)dma_sg_xfer(in3, out1, 1U, timing);
        return;
    }
    dma_simple_xfer_one(in3, out1, timing);
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
    u32 in_bytes  = n_windows * HDC_DMA_IN_BYTES;
    u32 out_bytes = n_windows * HDC_OUT_BEATS * (u32)sizeof(u32);

    if (n_windows == 0U)
        return 0;

    if (XAxiDma_HasSg(&dma))
        return dma_sg_xfer(in_words, out_words, n_windows, NULL);

    /* Simple-mode one MM2S/S2MM pair — requires input FIFO in hdc_stream_wrapper. */
    Xil_DCacheFlushRange((INTPTR)in_words, in_bytes);
    Xil_DCacheInvalidateRange((INTPTR)out_words, out_bytes);

    XAxiDma_SimpleTransfer(&dma, (UINTPTR)out_words, out_bytes, XAXIDMA_DEVICE_TO_DMA);
    XAxiDma_SimpleTransfer(&dma, (UINTPTR)in_words, in_bytes, XAXIDMA_DMA_TO_DEVICE);

    while (XAxiDma_Busy(&dma, XAXIDMA_DMA_TO_DEVICE))
        ;
    while (XAxiDma_Busy(&dma, XAXIDMA_DEVICE_TO_DMA))
        ;

    Xil_DCacheInvalidateRange((INTPTR)out_words, out_bytes);
    return 0;
}

void hdc_dma_stream_batch_sequential(const u32 *in_words, u32 *out_words, u32 n_windows)
{
    u32 i;

    for (i = 0U; i < n_windows; ++i) {
        hdc_dma_stream_one(in_words + (i * HDC_IN_BEATS),
                           out_words + (i * HDC_OUT_BEATS));
    }
}
