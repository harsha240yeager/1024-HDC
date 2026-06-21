#ifndef HDC_CORE_REGS_H
#define HDC_CORE_REGS_H

#include "xil_types.h"

#define HDC_AXI_BASEADDR    0x43C00000U

#define HDC_REG_CTRL        0x000U
#define HDC_REG_STATUS      0x004U
#define HDC_REG_PROTO_IDX   0x008U
#define HDC_REG_RESULT      0x00CU
#define HDC_REG_LEVELS0     0x010U
#define HDC_REG_LEVELS1     0x014U
#define HDC_REG_LEVELS2     0x018U
#define HDC_REG_STAGING     0x100U

#define HDC_CTRL_START      0x1U
#define HDC_CTRL_LOAD_PROTO 0x2U
#define HDC_CTRL_LOAD_MASK  0x4U
#define HDC_CTRL_CLR_DONE   0x8U

#define HDC_STATUS_BUSY     0x1U
#define HDC_STATUS_DONE     0x2U

#define HDC_VEC_WORDS       32U
#define HDC_WORDS64         16U
#define HDC_N_CLASS         8U
#define HDC_IDX_W           3U
#define HDC_DIST_W          11U

void hdc_wr(u32 off, u32 val);
u32  hdc_rd(u32 off);

u32 hdc_proto32(u32 class_idx, u32 word_idx, const u64 *proto64);
u32 hdc_mask32(u32 word_idx, const u64 *mask64);

void hdc_fill_staging_words(const u32 *vec_words);
void hdc_load_prototype_from64(u32 class_idx, const u64 *proto64);
void hdc_load_mask_from64(const u64 *mask64);

int hdc_classify_levels(u32 lvl0, u32 lvl1, u32 lvl2,
                        u32 *class_idx, u32 *class_dist);

#endif
