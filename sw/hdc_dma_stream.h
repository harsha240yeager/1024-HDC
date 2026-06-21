#ifndef HDC_DMA_STREAM_H
#define HDC_DMA_STREAM_H

#include "xaxidma.h"
#include "xil_types.h"

/* Match Address Editor after Phase 2 BD (typical Xilinx defaults). */
#ifndef HDC_DMA_DEV_ID
#define HDC_DMA_DEV_ID      XPAR_AXIDMA_0_DEVICE_ID
#endif

#define HDC_IN_BEATS        3U
#define HDC_OUT_BEATS       1U

int  hdc_dma_init(void);
void hdc_dma_stream_one(const u32 *in3, u32 *out1);

#endif
