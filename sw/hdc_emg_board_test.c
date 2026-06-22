/*
 * hdc_emg_board_test.c — Phase 3 EMG dataset replay on ZedBoard (SG DMA stream).
 *
 * Sources: hdc_emg_board_test.c, hdc_dma_stream.c, hdc_core_regs.c,
 *          emg_board_vectors.h (from scripts/export_emg_board_vectors.py)
 *
 * JTAG readback @ 0x00100300, magic 0xBEC00005.
 *
 * v2 PASS: |board_acc - EMG_EXPORT_REF_ACCURACY| <= 0.5%
 * Frozen 90.30% baseline printed as INFO when EMG_ENGINE_STAGE_B is set.
 */

#include "hdc_core_regs.h"
#include "hdc_dma_stream.h"
#include "xil_cache.h"
#include "xil_printf.h"

#if __has_include("emg_board_vectors.h")
#include "emg_board_vectors.h"
#endif

#ifndef EMG_EXPORT_REF_ACCURACY_X1000
#ifdef EMG_PYTHON_REF_ACCURACY_X1000
#define EMG_EXPORT_REF_ACCURACY_X1000 EMG_PYTHON_REF_ACCURACY_X1000
#else
#define EMG_EXPORT_REF_ACCURACY_X1000 0U
#endif
#endif

#ifndef EMG_BOARD_WINDOWS
#define EMG_BOARD_WINDOWS 0U
#endif

#ifndef EMG_N_SUBJECTS
#define EMG_N_SUBJECTS 1U
#endif

#define EMG_RESULTS_BASE        0x00100300U
#define EMG_MAGIC               0xBEC00005U
#define EMG_STATUS_DONE         1U
#define EMG_RESULTS_BYTES       0x20U

#define EMG_FROZEN_BASELINE_X1000  90300U
#define EMG_ACCURACY_TOL_X1000    500U

#ifndef EMG_BATCH_CHUNK
#define EMG_BATCH_CHUNK 200U
#endif

#if EMG_BOARD_WINDOWS > 0 && defined(EMG_USE_DDR_VECTORS) && (EMG_USE_DDR_VECTORS > 0U)
static u32 *emg_levels0;
static u32 *emg_levels1;
static u32 *emg_levels2;
static u8 *emg_labels;

static void emg_map_ddr_vectors(void)
{
    u32 base = EMG_VECTORS_DDR_BASE;

    emg_levels0 = (u32 *)(UINTPTR)(base + EMG_OFF_LEVELS0);
    emg_levels1 = (u32 *)(UINTPTR)(base + EMG_OFF_LEVELS1);
    emg_levels2 = (u32 *)(UINTPTR)(base + EMG_OFF_LEVELS2);
    emg_labels = (u8 *)(UINTPTR)(base + EMG_OFF_LABELS);
    Xil_DCacheInvalidateRange(
        (INTPTR)(base + EMG_OFF_LEVELS0),
        EMG_OFF_EXPECT + (EMG_BOARD_WINDOWS * sizeof(u32)) - EMG_OFF_LEVELS0);
}
#endif

#if EMG_BOARD_WINDOWS > 0
static u32 in_batch[EMG_BATCH_CHUNK * HDC_IN_BEATS] __attribute__((aligned(64)));
static u32 out_batch[EMG_BATCH_CHUNK * HDC_OUT_BEATS] __attribute__((aligned(64)));
#endif

static void emg_results_publish(u32 status, u32 n, u32 correct, u32 errors,
                                u32 accuracy_x1000, u32 export_ref_x1000)
{
    Xil_Out32(EMG_RESULTS_BASE + 0x00, EMG_MAGIC);
    Xil_Out32(EMG_RESULTS_BASE + 0x04, status);
    Xil_Out32(EMG_RESULTS_BASE + 0x08, n);
    Xil_Out32(EMG_RESULTS_BASE + 0x0C, correct);
    Xil_Out32(EMG_RESULTS_BASE + 0x10, accuracy_x1000);
    Xil_Out32(EMG_RESULTS_BASE + 0x14, errors);
    Xil_Out32(EMG_RESULTS_BASE + 0x18, export_ref_x1000);
    Xil_DCacheFlushRange((INTPTR)EMG_RESULTS_BASE, EMG_RESULTS_BYTES);
}

#if EMG_BOARD_WINDOWS > 0

static void load_protos_for_subject(u32 subj_idx)
{
    u32 base = subj_idx * EMG_N_CLASS * EMG_WORDS64;
    u32 k;

    for (k = 0U; k < EMG_N_CLASS; ++k)
        hdc_load_prototype_from64(k, &emg_proto64[base + k * EMG_WORDS64]);
}

static void pack_chunk(u32 offset, u32 chunk_n)
{
    u32 i;

    for (i = 0U; i < chunk_n; ++i) {
        u32 idx = offset + i;

        in_batch[i * HDC_IN_BEATS + 0U] = emg_levels0[idx];
        in_batch[i * HDC_IN_BEATS + 1U] = emg_levels1[idx];
        in_batch[i * HDC_IN_BEATS + 2U] = emg_levels2[idx];
    }
}

static u32 label_to_class_idx(u8 raw_label)
{
    if (raw_label >= 1U && raw_label <= 5U)
        return (u32)raw_label - 1U;
    return 0xFFFFFFFFU;
}

static u32 score_chunk(u32 offset, u32 chunk_n, u32 *correct_out)
{
    u32 i, correct = 0U;

    for (i = 0U; i < chunk_n; ++i) {
        u32 idx = offset + i;
        u32 out1 = out_batch[i * HDC_OUT_BEATS];
        u32 got_idx = (out1 >> 16) & ((1U << HDC_IDX_W) - 1U);
        u32 expect_idx = label_to_class_idx(emg_labels[idx]);

        if (expect_idx != 0xFFFFFFFFU && got_idx == expect_idx)
            correct++;
    }

    *correct_out = correct;
    return 0U;
}

static int emg_replay_subject(u32 offset, u32 subj_n, u32 *correct_out)
{
    u32 pos, total_correct = 0U;
    int rc;

    for (pos = 0U; pos < subj_n; pos += EMG_BATCH_CHUNK) {
        u32 chunk_n = subj_n - pos;

        if (chunk_n > EMG_BATCH_CHUNK)
            chunk_n = EMG_BATCH_CHUNK;

        pack_chunk(offset + pos, chunk_n);
        rc = hdc_dma_stream_batch(in_batch, out_batch, chunk_n);
        if (rc != 0)
            return rc;

        {
            u32 chunk_correct = 0U;

            score_chunk(offset + pos, chunk_n, &chunk_correct);
            total_correct += chunk_correct;
        }
    }

    *correct_out = total_correct;
    return 0;
}

static int emg_replay_batch(u32 *correct_out, u32 *errors_out)
{
    u32 subj, offset = 0U, total_correct = 0U;
    int rc;

    for (subj = 0U; subj < EMG_N_SUBJECTS; ++subj) {
        u32 subj_n = emg_subj_windows[subj];
        u32 subj_correct = 0U;

        load_protos_for_subject(subj);
        rc = emg_replay_subject(offset, subj_n, &subj_correct);
        if (rc != 0)
            return rc;

        total_correct += subj_correct;
        offset += subj_n;
    }

    *correct_out = total_correct;
    *errors_out = EMG_BOARD_WINDOWS - total_correct;
    return 0;
}

#endif /* EMG_BOARD_WINDOWS > 0 */

int main(void)
{
#if EMG_BOARD_WINDOWS == 0
    xil_printf("==================================================\r\n");
    xil_printf("HDC EMG board replay (no vectors linked)\r\n");
    xil_printf("Run: python3 scripts/export_emg_board_vectors.py\r\n");
    xil_printf("Then rebuild Final_HDC_dma_emg.elf\r\n");
    xil_printf("==================================================\r\n");
    emg_results_publish(0U, 0U, 0U, 0U, 0U, 0U);
#else
    u32 n = EMG_BOARD_WINDOWS;
    u32 correct = 0U, errors = 0U;
    u32 accuracy_x1000 = 0U;
    u32 delta_x1000 = 0U;
    int rc, pass_tol = 0;

#if defined(EMG_USE_DDR_VECTORS) && (EMG_USE_DDR_VECTORS > 0U)
    emg_map_ddr_vectors();
#endif

    rc = hdc_dma_init();
    if (rc != 0) {
        xil_printf("DMA init failed (%d)\r\n", rc);
        emg_results_publish(0U, n, 0U, n, 0U, EMG_EXPORT_REF_ACCURACY_X1000);
        return -1;
    }

    hdc_load_mask_from64(emg_mask64);

    rc = emg_replay_batch(&correct, &errors);
    if (rc != 0) {
        xil_printf("EMG batch DMA failed (%d)\r\n", rc);
        emg_results_publish(0U, n, correct, n - correct, 0U,
                            EMG_EXPORT_REF_ACCURACY_X1000);
        return -1;
    }

    if (n > 0U)
        accuracy_x1000 = (u32)(((u64)correct * 100000ULL) / n);

    if (accuracy_x1000 >= EMG_EXPORT_REF_ACCURACY_X1000)
        delta_x1000 = accuracy_x1000 - EMG_EXPORT_REF_ACCURACY_X1000;
    else
        delta_x1000 = EMG_EXPORT_REF_ACCURACY_X1000 - accuracy_x1000;

    pass_tol = (delta_x1000 <= EMG_ACCURACY_TOL_X1000) ? 1 : 0;

    emg_results_publish(EMG_STATUS_DONE, n, correct, errors, accuracy_x1000,
                        EMG_EXPORT_REF_ACCURACY_X1000);

    xil_printf("==================================================\r\n");
    xil_printf("HDC EMG replay v2 (%lu subjects, %lu windows)\r\n",
               (unsigned long)EMG_N_SUBJECTS, (unsigned long)n);
    xil_printf("EMG replay: N=%lu correct=%lu accuracy=%lu.%02lu%%\r\n",
               (unsigned long)n, (unsigned long)correct,
               (unsigned long)(accuracy_x1000 / 1000U),
               (unsigned long)((accuracy_x1000 % 1000U) / 10U));
    xil_printf("Export ref: %lu.%02lu%%  delta=%lu.%02lu%%  %s (0.5%% tol)\r\n",
               (unsigned long)(EMG_EXPORT_REF_ACCURACY_X1000 / 1000U),
               (unsigned long)((EMG_EXPORT_REF_ACCURACY_X1000 % 1000U) / 10U),
               (unsigned long)(delta_x1000 / 1000U),
               (unsigned long)((delta_x1000 % 1000U) / 10U),
               pass_tol ? "PASS" : "FAIL");
#if defined(EMG_ENGINE_STAGE_B)
    xil_printf("INFO frozen baseline (Stage B): %lu.%02lu%%\r\n",
               (unsigned long)(EMG_FROZEN_BASELINE_X1000 / 1000U),
               (unsigned long)((EMG_FROZEN_BASELINE_X1000 % 1000U) / 10U));
#endif
    xil_printf("==================================================\r\n");
#endif

    while (1)
        ;

    return 0;
}
