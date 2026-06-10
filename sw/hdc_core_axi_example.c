/*
 * hdc_core_axi_example.c
 *
 * Bare-metal Zynq PS driver for the end-to-end HDC inference core exposed by
 * rtl/hdc_core_axi_lite.sv.  Demonstrates the full programming sequence:
 *   1. Load each trained class prototype (staging buffer -> LOAD_PROTO).
 *   2. Load the pruning mask (staging buffer -> LOAD_MASK).
 *   3. For each quantized EMG window: write the level grid, START, poll DONE,
 *      and read back the predicted class index + Hamming distance.
 *
 * The prototypes / mask / level grids are produced offline by
 *   python python_ref/generate_vectors.py --core
 * (see core_proto.hex / core_mask.hex / core_levels.hex).
 */

#include "xil_io.h"
#include "xil_printf.h"
#include "sleep.h"

#define HDC_AXI_BASEADDR    0x43C00000U

/* Register map (byte offsets) -- see hdc_core_axi_lite.sv */
#define HDC_REG_CTRL        0x000U
#define HDC_REG_STATUS      0x004U
#define HDC_REG_PROTO_IDX   0x008U
#define HDC_REG_RESULT      0x00CU
#define HDC_REG_LEVELS0     0x010U
#define HDC_REG_LEVELS1     0x014U
#define HDC_REG_LEVELS2     0x018U
#define HDC_REG_STAGING     0x100U

/* CTRL bits (write-1 to pulse) */
#define HDC_CTRL_START      0x1U
#define HDC_CTRL_LOAD_PROTO 0x2U
#define HDC_CTRL_LOAD_MASK  0x4U
#define HDC_CTRL_CLR_DONE   0x8U

/* STATUS bits */
#define HDC_STATUS_BUSY     0x1U
#define HDC_STATUS_DONE     0x2U

#define HDC_VEC_WORDS       32U          /* 1024 bits / 32 */
#define HDC_N_CLASS         8U

static inline void hdc_wr(u32 off, u32 val) { Xil_Out32(HDC_AXI_BASEADDR + off, val); }
static inline u32  hdc_rd(u32 off)          { return Xil_In32(HDC_AXI_BASEADDR + off); }

/* Fill the 1024-bit staging buffer (32 little-endian 32-bit words). */
static void hdc_fill_staging(const u32 *vec_words)
{
    u32 i;
    for (i = 0U; i < HDC_VEC_WORDS; ++i)
        hdc_wr(HDC_REG_STAGING + i * 4U, vec_words[i]);
}

static void hdc_load_prototype(u32 class_idx, const u32 *proto_words)
{
    hdc_fill_staging(proto_words);
    hdc_wr(HDC_REG_PROTO_IDX, class_idx);
    hdc_wr(HDC_REG_CTRL, HDC_CTRL_LOAD_PROTO);
}

static void hdc_load_mask(const u32 *mask_words)
{
    hdc_fill_staging(mask_words);
    hdc_wr(HDC_REG_CTRL, HDC_CTRL_LOAD_MASK);
}

/* Run one inference. levels[] packs level[p] at bits [p*4 +: 4] (80 bits). */
static int hdc_classify(const u32 levels[3], u32 *class_idx, u32 *class_dist)
{
    u32 status, result, guard = 100000U;

    hdc_wr(HDC_REG_LEVELS0, levels[0]);
    hdc_wr(HDC_REG_LEVELS1, levels[1]);
    hdc_wr(HDC_REG_LEVELS2, levels[2]);
    hdc_wr(HDC_REG_CTRL, HDC_CTRL_START);

    do {
        status = hdc_rd(HDC_REG_STATUS);
    } while (((status & HDC_STATUS_DONE) == 0U) && (--guard > 0U));

    if ((status & HDC_STATUS_DONE) == 0U)
        return -1;

    result      = hdc_rd(HDC_REG_RESULT);
    *class_idx  = (result >> 16) & 0x7U;        /* IDX_W = 3 */
    *class_dist = result & 0x7FFU;              /* DIST_W = 11 */

    hdc_wr(HDC_REG_CTRL, HDC_CTRL_CLR_DONE);
    return 0;
}

int main(void)
{
    /* In a real system these come from the trained model (core_*.hex). */
    u32 prototypes[HDC_N_CLASS][HDC_VEC_WORDS];
    u32 mask[HDC_VEC_WORDS];
    u32 levels[3] = { 0x12345678U, 0x9ABCDEF0U, 0x0000ABCDU };
    u32 k, i, idx = 0U, dist = 0U;
    int rc;

    xil_printf("HDC core AXI example start\r\n");

    for (k = 0U; k < HDC_N_CLASS; ++k)
        for (i = 0U; i < HDC_VEC_WORDS; ++i)
            prototypes[k][i] = (k << 24) | i;
    for (i = 0U; i < HDC_VEC_WORDS; ++i)
        mask[i] = 0xFFFFFFFFU;               /* all-ones = unmasked */

    for (k = 0U; k < HDC_N_CLASS; ++k)
        hdc_load_prototype(k, prototypes[k]);
    hdc_load_mask(mask);

    rc = hdc_classify(levels, &idx, &dist);
    if (rc != 0) {
        xil_printf("ERROR: inference timed out\r\n");
        return -1;
    }

    xil_printf("Predicted class = %lu  (Hamming distance = %lu)\r\n",
               (unsigned long)idx, (unsigned long)dist);
    xil_printf("HDC core AXI example complete\r\n");
    return 0;
}
