#include "hdc_dma_stream.h"
#include "xil_cache.h"
#include "xil_printf.h"

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

void hdc_dma_stream_one(const u32 *in3, u32 *out1)
{
    const u32 in_bytes  = (u32)(HDC_IN_BEATS * sizeof(u32));
    const u32 out_bytes = (u32)(HDC_OUT_BEATS * sizeof(u32));

    Xil_DCacheFlushRange((INTPTR)in3, in_bytes);
    Xil_DCacheInvalidateRange((INTPTR)out1, out_bytes);

    /* S2MM must be running before results arrive (avoid ST_OUT stall). */
    XAxiDma_SimpleTransfer(&dma, (UINTPTR)out1, out_bytes, XAXIDMA_DEVICE_TO_DMA);
    XAxiDma_SimpleTransfer(&dma, (UINTPTR)in3, in_bytes, XAXIDMA_DMA_TO_DEVICE);

    while (XAxiDma_Busy(&dma, XAXIDMA_DEVICE_TO_DMA))
        ;
    while (XAxiDma_Busy(&dma, XAXIDMA_DMA_TO_DEVICE))
        ;

    Xil_DCacheInvalidateRange((INTPTR)out1, out_bytes);
}
