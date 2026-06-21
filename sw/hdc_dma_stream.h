#ifndef HDC_DMA_STREAM_H
#define HDC_DMA_STREAM_H

#include "xaxidma.h"
#include "xil_types.h"

#ifndef HDC_DMA_DEV_ID
#define HDC_DMA_DEV_ID      XPAR_AXIDMA_0_DEVICE_ID
#endif

#define HDC_IN_BEATS        3U
#define HDC_OUT_BEATS       1U

int  hdc_dma_init(void);
void hdc_dma_stream_one(const u32 *in3, u32 *out1);
int  hdc_dma_stream_batch(const u32 *in_words, u32 *out_words, u32 n_windows);

#endif
