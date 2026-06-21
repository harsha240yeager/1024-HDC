#include "hdc_core_regs.h"
#include "xil_io.h"

void hdc_wr(u32 off, u32 val)
{
    Xil_Out32(HDC_AXI_BASEADDR + off, val);
}

u32 hdc_rd(u32 off)
{
    return Xil_In32(HDC_AXI_BASEADDR + off);
}

u32 hdc_proto32(u32 class_idx, u32 word_idx, const u64 *proto64)
{
    u64 w64 = proto64[class_idx * HDC_WORDS64 + (word_idx >> 1)];
    return (word_idx & 1U) ? (u32)(w64 >> 32) : (u32)(w64 & 0xFFFFFFFFULL);
}

u32 hdc_mask32(u32 word_idx, const u64 *mask64)
{
    u64 w64 = mask64[word_idx >> 1];
    return (word_idx & 1U) ? (u32)(w64 >> 32) : (u32)(w64 & 0xFFFFFFFFULL);
}

void hdc_fill_staging_words(const u32 *vec_words)
{
    u32 i;
    for (i = 0U; i < HDC_VEC_WORDS; ++i)
        hdc_wr(HDC_REG_STAGING + i * 4U, vec_words[i]);
}

void hdc_load_prototype_from64(u32 class_idx, const u64 *proto64)
{
    u32 staging[HDC_VEC_WORDS];
    u32 w;
    for (w = 0U; w < HDC_VEC_WORDS; ++w)
        staging[w] = hdc_proto32(class_idx, w, proto64);
    hdc_fill_staging_words(staging);
    hdc_wr(HDC_REG_PROTO_IDX, class_idx);
    hdc_wr(HDC_REG_CTRL, HDC_CTRL_LOAD_PROTO);
}

void hdc_load_mask_from64(const u64 *mask64)
{
    u32 staging[HDC_VEC_WORDS];
    u32 w;
    for (w = 0U; w < HDC_VEC_WORDS; ++w)
        staging[w] = hdc_mask32(w, mask64);
    hdc_fill_staging_words(staging);
    hdc_wr(HDC_REG_CTRL, HDC_CTRL_LOAD_MASK);
}

int hdc_classify_levels(u32 lvl0, u32 lvl1, u32 lvl2,
                        u32 *class_idx, u32 *class_dist)
{
    u32 status, result, guard = 1000000U;

    hdc_wr(HDC_REG_LEVELS0, lvl0);
    hdc_wr(HDC_REG_LEVELS1, lvl1);
    hdc_wr(HDC_REG_LEVELS2, lvl2);
    hdc_wr(HDC_REG_CTRL, HDC_CTRL_START);

    do {
        status = hdc_rd(HDC_REG_STATUS);
    } while (((status & HDC_STATUS_DONE) == 0U) && (--guard > 0U));

    if ((status & HDC_STATUS_DONE) == 0U)
        return -1;

    result = hdc_rd(HDC_REG_RESULT);
    *class_idx  = (result >> 16) & ((1U << HDC_IDX_W) - 1U);
    *class_dist = result & ((1U << HDC_DIST_W) - 1U);
    hdc_wr(HDC_REG_CTRL, HDC_CTRL_CLR_DONE);
    return 0;
}
