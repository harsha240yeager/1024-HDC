/*
 * Portable C reference for ARM-only HDC (hdc_ref / encoder_top semantics).
 * Host build verifies accuracy on VDI; cross-compile for Cortex-A9 timing/energy.
 */

#include "hdc_arm_ref.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define EMG_MAXL 21

static int words_for_d(int D) {
    return D / HDC_ARM_BPW;
}

static int get_bit(const uint64_t *words, int bit_idx) {
    int wi = bit_idx / HDC_ARM_BPW;
    int bi = bit_idx % HDC_ARM_BPW;
    return (int)((words[wi] >> bi) & 1ULL);
}

static void set_bit(uint64_t *words, int bit_idx, int val) {
    int wi = bit_idx / HDC_ARM_BPW;
    int bi = bit_idx % HDC_ARM_BPW;
    if (val)
        words[wi] |= (1ULL << bi);
    else
        words[wi] &= ~(1ULL << bi);
}

static void bits_zero(uint64_t *words, int words_n) {
    memset(words, 0, (size_t)words_n * sizeof(uint64_t));
}

static void bits_copy(uint64_t *dst, const uint64_t *src, int words_n) {
    memcpy(dst, src, (size_t)words_n * sizeof(uint64_t));
}

static void bits_xor(uint64_t *dst, const uint64_t a[], const uint64_t b[], int words_n) {
    for (int i = 0; i < words_n; i++)
        dst[i] = a[i] ^ b[i];
}

static void unpack_words(const uint64_t in[], int words_n, uint64_t out[]) {
    memcpy(out, in, (size_t)words_n * sizeof(uint64_t));
}

static void pack_words(const uint64_t in[], int words_n, uint64_t out[]) {
    memcpy(out, in, (size_t)words_n * sizeof(uint64_t));
}

static void permute(const uint64_t in_w[], int words_n, int mode, int param, uint64_t out_w[]) {
    uint64_t in_copy[32];
    uint64_t tmp[32];
    if (words_n > 32)
        return;
    memcpy(in_copy, in_w, (size_t)words_n * sizeof(uint64_t));
    memcpy(tmp, in_w, (size_t)words_n * sizeof(uint64_t));

    if (mode == 0) {
        for (int k = 0; k < words_n; k++) {
            int src = (words_n - 1) - k;
            tmp[k] = in_copy[src];
        }
    } else if (mode == 1) {
        int bitrot = param % HDC_ARM_BPW;
        for (int k = 0; k < words_n; k++) {
            if (bitrot == 0)
                tmp[k] = in_copy[k];
            else
                tmp[k] = ((in_copy[k] >> bitrot) |
                          (in_copy[k] << (HDC_ARM_BPW - bitrot))) &
                         UINT64_MAX >> (64 - HDC_ARM_BPW);
        }
    } else if (mode == 2) {
        int D = words_n * HDC_ARM_BPW;
        int rot = param % D;
        int word_rot = rot / HDC_ARM_BPW;
        int bit_rot = rot % HDC_ARM_BPW;
        for (int k = 0; k < words_n; k++) {
            int src0 = (k + word_rot) % words_n;
            int src1 = (k + word_rot + 1) % words_n;
            if (bit_rot == 0)
                tmp[k] = in_copy[src0];
            else
                tmp[k] = ((in_copy[src0] >> bit_rot) |
                          (in_copy[src1] << (HDC_ARM_BPW - bit_rot))) &
                         ((1ULL << HDC_ARM_BPW) - 1ULL);
        }
    }
    pack_words(tmp, words_n, out_w);
}

static void bind_permute_bits(const uint64_t in_vec[], const uint64_t bind_vec[],
                              int perm_mode, int perm_param, int words_n, uint64_t out[]) {
    uint64_t bound[32];
    uint64_t in_w[32];
    uint64_t bind_w[32];
    unpack_words(in_vec, words_n, in_w);
    unpack_words(bind_vec, words_n, bind_w);
    bits_xor(bound, in_w, bind_w, words_n);
    permute(bound, words_n, perm_mode, perm_param, out);
}

static void encode_record_pair(const HdcArmMem *mem, int channel, int feature, int level,
                               uint64_t out[]) {
    uint64_t t1[32];
    uint64_t permuted[32];
    int words = mem->words;

    bits_xor(t1, mem->channel[channel], mem->value[level], words);
    permute(mem->feature[feature], words, 2, feature, permuted);
    bits_xor(out, t1, permuted, words);
}

static void bundle_threshold(const int *counts, int n_accum, int D, uint64_t out_words[]) {
    int thr = n_accum >> 1;
    bits_zero(out_words, words_for_d(D));
    for (int i = 0; i < D; i++) {
        if (counts[i] >= thr)
            set_bit(out_words, i, 1);
    }
}

static int read_hex_u64(const char *line, uint64_t *out) {
    char *end = NULL;
    unsigned long long v = strtoull(line, &end, 16);
    if (end == line)
        return -1;
    *out = (uint64_t)v;
    return 0;
}

static int load_mem_table(const char *path, int rows, int words, uint64_t table[][HDC_ARM_WORDS_DEFAULT]) {
    FILE *fp = fopen(path, "rb");
    char line[256];
    if (!fp)
        return -1;
    for (int r = 0; r < rows; r++) {
        for (int w = 0; w < words; w++) {
            if (!fgets(line, sizeof(line), fp)) {
                fclose(fp);
                return -1;
            }
            /* strip comments / whitespace */
            char *p = line;
            while (*p == ' ' || *p == '\t')
                p++;
            if (*p == '/' || *p == '\0' || *p == '\n')
                w--;
            else if (read_hex_u64(p, &table[r][w]) != 0) {
                fclose(fp);
                return -1;
            }
        }
    }
    fclose(fp);
    return 0;
}

int hdc_arm_load_mem(HdcArmMem *mem, const char *dir, int D, int cnt_bits) {
    char path[512];
    int words = words_for_d(D);
    if (words > HDC_ARM_WORDS_DEFAULT || D != words * HDC_ARM_BPW)
        return -1;

    mem->D = D;
    mem->words = words;
    mem->cnt_bits = cnt_bits;
    mem->cnt_max = (1 << cnt_bits) - 1;

    snprintf(path, sizeof(path), "%s/item_mem_channel.mem", dir);
    if (load_mem_table(path, HDC_ARM_N_CH, words, mem->channel) != 0)
        return -1;
    snprintf(path, sizeof(path), "%s/item_mem_feature.mem", dir);
    if (load_mem_table(path, HDC_ARM_N_FEAT, words, mem->feature) != 0)
        return -1;
    snprintf(path, sizeof(path), "%s/item_mem_value.mem", dir);
    if (load_mem_table(path, HDC_ARM_N_LEVELS, words, mem->value) != 0)
        return -1;
    return 0;
}

int hdc_arm_load_mem_embedded(
    HdcArmMem *mem,
    int D,
    int cnt_bits,
    const uint64_t channel[][HDC_ARM_WORDS_DEFAULT],
    const uint64_t feature[][HDC_ARM_WORDS_DEFAULT],
    const uint64_t value[][HDC_ARM_WORDS_DEFAULT]) {
    int words = words_for_d(D);
    if (words > HDC_ARM_WORDS_DEFAULT || D != words * HDC_ARM_BPW)
        return -1;

    mem->D = D;
    mem->words = words;
    mem->cnt_bits = cnt_bits;
    mem->cnt_max = (1 << cnt_bits) - 1;

    memcpy(mem->channel, channel, sizeof(uint64_t) * HDC_ARM_N_CH * (size_t)words);
    memcpy(mem->feature, feature, sizeof(uint64_t) * HDC_ARM_N_FEAT * (size_t)words);
    memcpy(mem->value, value, sizeof(uint64_t) * HDC_ARM_N_LEVELS * (size_t)words);
    return 0;
}

void hdc_arm_unpack_levels(uint32_t l0, uint32_t l1, uint32_t l2,
                           int grid[HDC_ARM_N_CH][HDC_ARM_N_FEAT]) {
    const int level_w = 4; /* log2(16) */
    uint64_t lo = (uint64_t)l0 | ((uint64_t)l1 << 32);
    uint16_t hi = (uint16_t)(l2 & 0xFFFFU);

    for (int c = 0; c < HDC_ARM_N_CH; c++) {
        for (int f = 0; f < HDC_ARM_N_FEAT; f++) {
            int p = c * HDC_ARM_N_FEAT + f;
            int shift = p * level_w;
            int level;
            if (shift < 64)
                level = (int)((lo >> shift) & 0xFU);
            else
                level = (int)((hi >> (shift - 64)) & 0xFU);
            grid[c][f] = level;
        }
    }
}

void hdc_arm_sample_to_grid(const int sample_q4[HDC_ARM_N_CH], int grid[HDC_ARM_N_CH][HDC_ARM_N_FEAT]) {
    for (int c = 0; c < HDC_ARM_N_CH; c++) {
        int lvl21 = sample_q4[c];
        if (lvl21 < 0)
            lvl21 = 0;
        if (lvl21 > EMG_MAXL)
            lvl21 = EMG_MAXL;
        int lvl16 = (int)(((double)lvl21 * (HDC_ARM_N_LEVELS - 1) / (double)EMG_MAXL) + 0.5);
        if (lvl16 < 0)
            lvl16 = 0;
        if (lvl16 >= HDC_ARM_N_LEVELS)
            lvl16 = HDC_ARM_N_LEVELS - 1;
        for (int f = 0; f < HDC_ARM_N_FEAT; f++)
            grid[c][f] = lvl16;
    }
}

void hdc_arm_encode_grid(const HdcArmMem *mem, const int grid[HDC_ARM_N_CH][HDC_ARM_N_FEAT],
                         uint64_t out_words[]) {
    int counts[1024];
    int n_accum = 0;
    int D = mem->D;
    int words = mem->words;

    for (int i = 0; i < D; i++)
        counts[i] = 0;
    bits_zero(out_words, words);

    for (int c = 0; c < HDC_ARM_N_CH; c++) {
        for (int f = 0; f < HDC_ARM_N_FEAT; f++) {
            uint64_t part[32];
            int level = grid[c][f];
            if (level < 0)
                level = 0;
            if (level >= HDC_ARM_N_LEVELS)
                level = HDC_ARM_N_LEVELS - 1;
            encode_record_pair(mem, c, f, level, part);
            for (int bit = 0; bit < D; bit++) {
                if (get_bit(part, bit)) {
                    if (counts[bit] < mem->cnt_max)
                        counts[bit]++;
                }
            }
            n_accum++;
        }
    }
    bundle_threshold(counts, n_accum, D, out_words);
}

int hdc_arm_hamming(const uint64_t a[], const uint64_t b[], const uint64_t mask[], int words) {
    int dist = 0;
    for (int wi = 0; wi < words; wi++) {
        uint64_t diff = (a[wi] ^ b[wi]) & mask[wi];
        dist += __builtin_popcountll(diff);
    }
    return dist;
}

int hdc_arm_classify(const uint64_t query[], const uint64_t protos[][HDC_ARM_WORDS_DEFAULT],
                     const uint64_t mask[], int n_class, int words, int *best_dist) {
    int best_c = 0;
    int best_d = hdc_arm_hamming(query, protos[0], mask, words);
    for (int k = 1; k < n_class; k++) {
        int d = hdc_arm_hamming(query, protos[k], mask, words);
        if (d < best_d) {
            best_d = d;
            best_c = k;
        }
    }
    if (best_dist)
        *best_dist = best_d;
    return best_c;
}

int hdc_arm_train_proto(
    const HdcArmMem *mem,
    const int *samples_q4,
    int n_total,
    const int *indices,
    int n_indices,
    uint64_t out_words[]) {
    int counts[1024];
    int D = mem->D;
    int words = mem->words;

    if (n_indices <= 0)
        return -1;
    for (int i = 0; i < D; i++)
        counts[i] = 0;

    for (int j = 0; j < n_indices; j++) {
        int row = indices[j];
        if (row < 0 || row >= n_total)
            return -1;
        const int *sample = samples_q4 + row * HDC_ARM_N_CH;
        int grid[HDC_ARM_N_CH][HDC_ARM_N_FEAT];
        uint64_t q[32];
        hdc_arm_sample_to_grid(sample, grid);
        hdc_arm_encode_grid(mem, grid, q);
        for (int bit = 0; bit < D; bit++) {
            if (get_bit(q, bit))
                counts[bit]++;
        }
    }
    bundle_threshold(counts, n_indices, D, out_words);
    return 0;
}

#ifdef HDC_ARM_REF_MAIN
/* Minimal self-test: load mem, encode zeros grid. */
int main(int argc, char **argv) {
    HdcArmMem mem;
    const char *dir = argc > 1 ? argv[1] : "python_ref/mem_files";
    if (hdc_arm_load_mem(&mem, dir, 1024, 6) != 0) {
        fprintf(stderr, "load mem failed from %s\n", dir);
        return 1;
    }
    int grid[HDC_ARM_N_CH][HDC_ARM_N_FEAT] = {{0}};
    uint64_t q[HDC_ARM_WORDS_DEFAULT];
    hdc_arm_encode_grid(&mem, grid, q);
    printf("hdc_arm_ref self-test OK (encoded zero grid)\n");
    return 0;
}
#endif
