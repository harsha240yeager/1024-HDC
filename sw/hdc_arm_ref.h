#ifndef HDC_ARM_REF_H
#define HDC_ARM_REF_H

#include <stdint.h>

#define HDC_ARM_D_DEFAULT       1024
#define HDC_ARM_WORDS_DEFAULT   16
#define HDC_ARM_BPW             64
#define HDC_ARM_N_CH            4
#define HDC_ARM_N_FEAT          5
#define HDC_ARM_N_LEVELS        16
#define HDC_ARM_N_PAIRS         (HDC_ARM_N_CH * HDC_ARM_N_FEAT)
#define HDC_ARM_N_CLASS         5
#define HDC_ARM_CNT_BITS        6
#define HDC_ARM_CNT_MAX         ((1 << HDC_ARM_CNT_BITS) - 1)

typedef struct {
    int D;
    int words;
    int cnt_bits;
    int cnt_max;
    uint64_t channel[HDC_ARM_N_CH][HDC_ARM_WORDS_DEFAULT];
    uint64_t feature[HDC_ARM_N_FEAT][HDC_ARM_WORDS_DEFAULT];
    uint64_t value[HDC_ARM_N_LEVELS][HDC_ARM_WORDS_DEFAULT];
} HdcArmMem;

/* Load item_mem_*.mem from directory (RTL hex layout). Returns 0 on success. */
int hdc_arm_load_mem(HdcArmMem *mem, const char *dir, int D, int cnt_bits);

/* Load item memory from embedded u64 tables (bare-metal bench). */
int hdc_arm_load_mem_embedded(
    HdcArmMem *mem,
    int D,
    int cnt_bits,
    const uint64_t channel[][HDC_ARM_WORDS_DEFAULT],
    const uint64_t feature[][HDC_ARM_WORDS_DEFAULT],
    const uint64_t value[][HDC_ARM_WORDS_DEFAULT]);

/* Unpack RTL level words -> 4x5 grid (inverse of pack_levels_u32). */
void hdc_arm_unpack_levels(uint32_t l0, uint32_t l1, uint32_t l2,
                           int grid[HDC_ARM_N_CH][HDC_ARM_N_FEAT]);

/* Map 21-level envelope sample to 16-level grid (matches level21_to_grid). */
void hdc_arm_sample_to_grid(const int sample_q4[HDC_ARM_N_CH], int grid[HDC_ARM_N_CH][HDC_ARM_N_FEAT]);

/* Encode 4x5 level grid -> query hypervector (bits as uint64 words, LSB-first). */
void hdc_arm_encode_grid(const HdcArmMem *mem, const int grid[HDC_ARM_N_CH][HDC_ARM_N_FEAT],
                         uint64_t out_words[]);

/* Masked Hamming; returns class index (argmin distance). */
int hdc_arm_classify(const uint64_t query[], const uint64_t protos[][HDC_ARM_WORDS_DEFAULT],
                     const uint64_t mask[], int n_class, int words, int *best_dist);

/* Compare two hypervectors; return popcount diff (for self-test). */
int hdc_arm_hamming(const uint64_t a[], const uint64_t b[], const uint64_t mask[], int words);

/* Unlimited majority bundle over encoded query HVs (class prototype training). */
int hdc_arm_train_proto(
    const HdcArmMem *mem,
    const int *samples_q4,
    int n_total,
    const int *indices,
    int n_indices,
    uint64_t out_words[]);

#endif /* HDC_ARM_REF_H */
