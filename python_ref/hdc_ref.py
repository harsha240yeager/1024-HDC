"""
Bit-exact Python golden reference for the 1024HDC project.

Matches RTL semantics in:
  - xor_permute_top.sv   (bind = XOR, then permute)
  - permute_stage.sv     (modes 00/01/10/11)
  - bundle_unit.sv       (majority threshold: cnt >= n_accum >> 1)
  - popcount_am.sv       (masked Hamming distance + argmin)
  - pruning_mask.sv      (per-bit AND before popcount)

EMG encoding follows the record model in HDC_Research_Plan.md Eq. (3.1).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

ArrayLike = Union[np.ndarray, Sequence[int]]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HDCConfig:
    D: int = 1024
    words: int = 16
    bits_per_word: int = 64
    seed: int = 42

    # EMG record encoding defaults (Section 3 of research plan)
    n_channels: int = 4
    n_features: int = 5
    n_levels: int = 16

    # Item-memory sizes
    n_channel_items: int = 4
    n_feature_items: int = 5
    n_value_items: int = 16

    def __post_init__(self) -> None:
        if self.words * self.bits_per_word != self.D:
            raise ValueError(
                f"words * bits_per_word ({self.words * self.bits_per_word}) "
                f"must equal D ({self.D})"
            )

    @property
    def n_pairs(self) -> int:
        return self.n_channels * self.n_features


# ---------------------------------------------------------------------------
# Bit-vector helpers (RTL bit 0 = LSB of flat vector)
# ---------------------------------------------------------------------------

def zeros(D: int) -> np.ndarray:
    return np.zeros(D, dtype=np.uint8)


def pack_u64_words(bits: np.ndarray, words: int, bits_per_word: int) -> np.ndarray:
    """Pack D bits into `words` uint64 values (word i = bits [64*i+63 : 64*i])."""
    if bits.shape[0] != words * bits_per_word:
        raise ValueError("bit length mismatch")
    out = np.zeros(words, dtype=np.uint64)
    for wi in range(words):
        chunk = bits[wi * bits_per_word : (wi + 1) * bits_per_word]
        val = np.uint64(0)
        for bi, b in enumerate(chunk):
            if b:
                val |= np.uint64(1) << np.uint64(bi)
        out[wi] = val
    return out


def unpack_u64_words(words_u64: np.ndarray, bits_per_word: int) -> np.ndarray:
    bits = np.zeros(words_u64.shape[0] * bits_per_word, dtype=np.uint8)
    for wi, word in enumerate(words_u64):
        for bi in range(bits_per_word):
            bits[wi * bits_per_word + bi] = (int(word) >> bi) & 1
    return bits


def bits_from_u64_words(words_u64: ArrayLike, D: int) -> np.ndarray:
    arr = np.asarray(words_u64, dtype=np.uint64)
    return unpack_u64_words(arr, D // arr.shape[0])


def bits_to_hex_lines(bits: np.ndarray, words: int, bits_per_word: int) -> List[str]:
    packed = pack_u64_words(bits, words, bits_per_word)
    return [f"{int(w):016x}" for w in packed]


def bits_from_hex_lines(lines: Sequence[str], D: int) -> np.ndarray:
    bpw = 64
    words = D // bpw
    if len(lines) != words:
        raise ValueError(f"expected {words} hex lines, got {len(lines)}")
    u64 = [int(line.strip(), 16) for line in lines]
    return bits_from_u64_words(u64, D)


def random_bits(rng: np.random.Generator, D: int) -> np.ndarray:
    return rng.integers(0, 2, size=D, dtype=np.uint8)


def hamming(a: np.ndarray, b: np.ndarray, mask: Optional[np.ndarray] = None) -> int:
    diff = (a ^ b) & 1
    if mask is not None:
        diff = diff & (mask & 1)
    return int(diff.sum())


# ---------------------------------------------------------------------------
# permute_stage.sv (combinational semantics)
# ---------------------------------------------------------------------------

def _unpack_words(bits: np.ndarray, cfg: HDCConfig) -> List[int]:
    words: List[int] = []
    for wi in range(cfg.words):
        w = 0
        for bi in range(cfg.bits_per_word):
            if bits[wi * cfg.bits_per_word + bi]:
                w |= 1 << bi
        words.append(w)
    return words


def _pack_words(words: List[int], cfg: HDCConfig) -> np.ndarray:
    bits = zeros(cfg.D)
    for wi, w in enumerate(words):
        for bi in range(cfg.bits_per_word):
            bits[wi * cfg.bits_per_word + bi] = (w >> bi) & 1
    return bits


def permute(bits: np.ndarray, mode: int, param: int, cfg: HDCConfig) -> np.ndarray:
    """Match permute_stage.sv case(mode)."""
    in_w = _unpack_words(bits, cfg)
    tmp = list(in_w)

    if mode == 0:
        for k in range(cfg.words):
            src = (cfg.words - 1) - k
            tmp[k] = in_w[src]
    elif mode == 1:
        bitrot = int(param) % cfg.bits_per_word
        for k in range(cfg.words):
            if bitrot == 0:
                tmp[k] = in_w[k]
            else:
                tmp[k] = ((in_w[k] >> bitrot) | (in_w[k] << (cfg.bits_per_word - bitrot))) & (
                    (1 << cfg.bits_per_word) - 1
                )
    elif mode == 2:
        rot = int(param) % cfg.D
        word_rot = rot // cfg.bits_per_word
        bit_rot = rot % cfg.bits_per_word
        for k in range(cfg.words):
            src0 = (k + word_rot) % cfg.words
            src1 = (k + word_rot + 1) % cfg.words
            if bit_rot == 0:
                tmp[k] = in_w[src0]
            else:
                tmp[k] = (
                    (in_w[src0] >> bit_rot)
                    | (in_w[src1] << (cfg.bits_per_word - bit_rot))
                ) & ((1 << cfg.bits_per_word) - 1)
    else:
        tmp = list(in_w)

    return _pack_words(tmp, cfg)


def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a ^ b) & 1


def bind_permute(
    in_vec: np.ndarray,
    bind_vec: np.ndarray,
    perm_mode: int,
    perm_param: int,
    cfg: HDCConfig,
) -> np.ndarray:
    """Match xor_permute_top datapath (XOR then permute)."""
    bound = bind(in_vec, bind_vec)
    return permute(bound, perm_mode, perm_param, cfg)


# ---------------------------------------------------------------------------
# bundle_unit.sv
# ---------------------------------------------------------------------------

def bundle_threshold(counts: np.ndarray, n_accum: int) -> np.ndarray:
    """Majority threshold: out[i] = (counts[i] >= n_accum >> 1)."""
    thr = int(n_accum) >> 1
    return (counts >= thr).astype(np.uint8)


class BundleAccumulator:
    """Software model of bundle_unit.sv accumulation + threshold."""

    def __init__(self, cfg: HDCConfig, cnt_bits: int = 6) -> None:
        self.cfg = cfg
        self.cnt_bits = cnt_bits
        self._max = (1 << cnt_bits) - 1
        self.clear()

    def clear(self) -> None:
        self.counts = np.zeros(self.cfg.D, dtype=np.int32)
        self.n_accum = 0

    def accumulate(self, vec: np.ndarray) -> None:
        v = np.asarray(vec, dtype=np.uint8) & 1
        active = v.astype(bool)
        self.counts[active] = np.minimum(self.counts[active] + 1, self._max)
        self.n_accum += 1

    def threshold(self) -> np.ndarray:
        if self.n_accum == 0:
            return zeros(self.cfg.D)
        return bundle_threshold(self.counts, self.n_accum)


def bundle_majority(vectors: Sequence[np.ndarray], cfg: HDCConfig) -> np.ndarray:
    acc = BundleAccumulator(cfg)
    for v in vectors:
        acc.accumulate(v)
    return acc.threshold()


# ---------------------------------------------------------------------------
# Item memory
# ---------------------------------------------------------------------------

class ItemMemory:
    """Random orthogonal item HVs + continuous value HVs."""

    def __init__(self, cfg: HDCConfig) -> None:
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.channel = self._random_table(cfg.n_channel_items)
        self.feature = self._random_table(cfg.n_feature_items)
        self.value = self._continuous_value_table(cfg.n_value_items)

    def _random_table(self, n: int) -> np.ndarray:
        return np.stack([random_bits(self.rng, self.cfg.D) for _ in range(n)], axis=0)

    def _continuous_value_table(self, levels: int) -> np.ndarray:
        """Adjacent levels differ in ~D/levels bits (continuous item memory)."""
        if levels < 2:
            raise ValueError("levels must be >= 2")
        v_min = random_bits(self.rng, self.cfg.D)
        v_max = random_bits(self.rng, self.cfg.D)
        table = np.zeros((levels, self.cfg.D), dtype=np.uint8)
        flip_budget = max(1, self.cfg.D // levels)
        for level in range(levels):
            target_flips = (level * flip_budget) // (levels - 1)
            out = v_min.copy()
            diff = v_min ^ v_max
            diff_idx = np.flatnonzero(diff)
            self.rng.shuffle(diff_idx)
            pick = diff_idx[:target_flips]
            out[pick] = v_max[pick]
            table[level] = out
        return table

    def export_mem_files(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, table in [
            ("item_mem_channel", self.channel),
            ("item_mem_feature", self.feature),
            ("item_mem_value", self.value),
        ]:
            path = out_dir / f"{name}.mem"
            with path.open("w", encoding="utf-8") as f:
                for row in table:
                    for line in bits_to_hex_lines(row, self.cfg.words, self.cfg.bits_per_word):
                        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Encoder + classifier
# ---------------------------------------------------------------------------

@dataclass
class ClassifierResult:
    class_id: int
    distance: int
    distances: np.ndarray


class HDCEngine:
    def __init__(self, cfg: HDCConfig) -> None:
        self.cfg = cfg

    def bind_permute(
        self,
        in_vec: np.ndarray,
        bind_vec: np.ndarray,
        perm_mode: int,
        perm_param: int,
    ) -> np.ndarray:
        return bind_permute(in_vec, bind_vec, perm_mode, perm_param, self.cfg)

    def encode_record_pair(
        self,
        channel: int,
        feature: int,
        level: int,
        mem: ItemMemory,
    ) -> np.ndarray:
        """Single (channel, feature, value) bind with feature-position permute."""
        hv_ch = mem.channel[channel]
        hv_val = mem.value[level]
        hv_feat = mem.feature[feature]
        permuted_feat = permute(hv_feat, mode=2, param=feature, cfg=self.cfg)
        return bind(bind(hv_ch, hv_val), permuted_feat)

    def encode_emg_window(
        self,
        quantized: np.ndarray,
        mem: ItemMemory,
    ) -> np.ndarray:
        """
        quantized shape: (n_channels, n_features), values in [0, n_levels-1].
        Returns bundled 1024-bit query hypervector.
        """
        q = np.asarray(quantized, dtype=np.int32)
        if q.shape != (self.cfg.n_channels, self.cfg.n_features):
            raise ValueError(
                f"expected shape ({self.cfg.n_channels}, {self.cfg.n_features}), got {q.shape}"
            )
        parts: List[np.ndarray] = []
        for c in range(self.cfg.n_channels):
            for f in range(self.cfg.n_features):
                level = int(q[c, f])
                if not 0 <= level < self.cfg.n_levels:
                    raise ValueError(f"quantized value out of range at ({c},{f}): {level}")
                parts.append(self.encode_record_pair(c, f, level, mem))
        return bundle_majority(parts, self.cfg)

    def classify(
        self,
        query: np.ndarray,
        class_hvs: np.ndarray,
        mask: Optional[np.ndarray] = None,
    ) -> ClassifierResult:
        if mask is None:
            mask = np.ones(self.cfg.D, dtype=np.uint8)
        distances = np.array(
            [hamming(query, class_hvs[k], mask=mask) for k in range(class_hvs.shape[0])],
            dtype=np.int32,
        )
        class_id = int(distances.argmin())
        return ClassifierResult(class_id=class_id, distance=int(distances[class_id]), distances=distances)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_class_hypervectors(
    query_hvs: np.ndarray,
    labels: np.ndarray,
    cfg: HDCConfig,
    n_classes: Optional[int] = None,
) -> np.ndarray:
    """Single-pass majority bundling per class."""
    labels = np.asarray(labels, dtype=np.int32)
    if n_classes is None:
        n_classes = int(labels.max()) + 1
    class_hvs = np.zeros((n_classes, cfg.D), dtype=np.uint8)
    for c in range(n_classes):
        idx = np.where(labels == c)[0]
        if idx.size == 0:
            continue
        vecs = [query_hvs[i] for i in idx]
        class_hvs[c] = bundle_majority(vecs, cfg)
    return class_hvs


# ---------------------------------------------------------------------------
# Hook A / Twist 1 / Twist 2 — pruning masks
# ---------------------------------------------------------------------------

def per_bit_fisher_scores(query_hvs: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """
    Per-bit Fisher-like score: between-class variance / (within-class variance + eps).
    Higher = more discriminative.
    """
    x = np.asarray(query_hvs, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int32)
    scores = np.zeros(x.shape[1], dtype=np.float64)
    eps = 1e-6
    for bit in range(x.shape[1]):
        col = x[:, bit]
        overall_var = col.var()
        if overall_var < eps:
            scores[bit] = 0.0
            continue
        within = 0.0
        for c in np.unique(y):
            idx = y == c
            if idx.sum() <= 1:
                continue
            within += col[idx].var() * idx.sum()
        within /= max(1, len(y))
        scores[bit] = overall_var / (within + eps)
    return scores


def mask_from_scores(
    scores: np.ndarray,
    keep_ratio: float,
    rng: Optional[np.random.Generator] = None,
    *,
    informed: bool = True,
) -> np.ndarray:
    D = scores.shape[0]
    n_keep = max(1, int(round(D * keep_ratio)))
    mask = zeros(D)
    if informed:
        top = np.argsort(-scores)[:n_keep]
        mask[top] = 1
    else:
        if rng is None:
            rng = np.random.default_rng(0)
        pick = rng.choice(D, size=n_keep, replace=False)
        mask[pick] = 1
    return mask


def make_pruning_masks(
    query_hvs: np.ndarray,
    labels: np.ndarray,
    keep_ratio: float,
    cfg: HDCConfig,
    *,
    random_seed: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Twist 1: informed (Fisher) vs random mask at identical density."""
    scores = per_bit_fisher_scores(query_hvs, labels)
    informed = mask_from_scores(scores, keep_ratio, informed=True)
    random_m = mask_from_scores(
        scores, keep_ratio, rng=np.random.default_rng(random_seed), informed=False
    )
    return informed, random_m


def cross_subject_mask_experiment(
    query_hvs: np.ndarray,
    labels: np.ndarray,
    subject_ids: np.ndarray,
    cfg: HDCConfig,
    *,
    keep_ratio: float = 0.5,
    train_subjects: Optional[Sequence[int]] = None,
    random_seed: int = 0,
) -> Dict[str, object]:
    """
    Twist 2: train masks on a subject subset, evaluate on held-out subjects.

    Returns per-subject-mask accuracies for:
      - per_subject_oracle (separate mask per train subject, eval on all)
      - pooled (one mask from all train subjects)
      - random (same density, train subjects only)
    """
    subject_ids = np.asarray(subject_ids, dtype=np.int32)
    labels = np.asarray(labels, dtype=np.int32)
    uniq = sorted(int(s) for s in np.unique(subject_ids))
    if train_subjects is None:
        half = len(uniq) // 2
        train_subjects = uniq[:half]
    train_set = set(int(s) for s in train_subjects)
    test_set = [s for s in uniq if s not in train_set]

    train_idx = np.array([s in train_set for s in subject_ids], dtype=bool)
    test_idx = np.array([s in test_set for s in subject_ids], dtype=bool)

    class_hvs = train_class_hypervectors(query_hvs[train_idx], labels[train_idx], cfg)
    engine = HDCEngine(cfg)

    def eval_mask(mask: np.ndarray) -> float:
        correct = 0
        total = int(test_idx.sum())
        if total == 0:
            return 0.0
        for i in np.where(test_idx)[0]:
            pred = engine.classify(query_hvs[i], class_hvs, mask=mask).class_id
            if pred == int(labels[i]):
                correct += 1
        return correct / total

    train_q = query_hvs[train_idx]
    train_y = labels[train_idx]

    pooled_scores = per_bit_fisher_scores(train_q, train_y)
    pooled_mask = mask_from_scores(pooled_scores, keep_ratio, informed=True)
    random_mask = mask_from_scores(
        pooled_scores,
        keep_ratio,
        rng=np.random.default_rng(random_seed),
        informed=False,
    )

    # Oracle: average accuracy using per-train-subject masks on test set
    per_subject_acc: Dict[int, float] = {}
    for sid in train_subjects:
        idx = train_idx & (subject_ids == sid)
        if idx.sum() == 0:
            continue
        scores = per_bit_fisher_scores(query_hvs[idx], labels[idx])
        m = mask_from_scores(scores, keep_ratio, informed=True)
        per_subject_acc[int(sid)] = eval_mask(m)

    return {
        "train_subjects": list(train_subjects),
        "test_subjects": test_set,
        "accuracy_pooled_informed": eval_mask(pooled_mask),
        "accuracy_random": eval_mask(random_mask),
        "accuracy_per_subject_oracle_mean": float(np.mean(list(per_subject_acc.values())))
        if per_subject_acc
        else 0.0,
        "per_subject_oracle": per_subject_acc,
        "pooled_mask_density": float(pooled_mask.mean()),
    }


# ---------------------------------------------------------------------------
# Co-simulation vector export
# ---------------------------------------------------------------------------

def export_bind_permute_vectors(
    out_dir: Path,
    cfg: HDCConfig,
    count: int,
    seed: int,
) -> None:
    """Write random bind+permute test vectors for ModelSim."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    engine = HDCEngine(cfg)
    meta = []

    for i in range(count):
        in_vec = random_bits(rng, cfg.D)
        bind_vec = random_bits(rng, cfg.D)
        mode = int(rng.integers(0, 4))
        param = int(rng.integers(0, cfg.D))
        expected = engine.bind_permute(in_vec, bind_vec, mode, param)

        case_dir = out_dir / f"case_{i:05d}"
        case_dir.mkdir(parents=True, exist_ok=True)
        _write_case(case_dir, in_vec, bind_vec, expected, mode, param, cfg)
        meta.append(
            {
                "case": i,
                "perm_mode": mode,
                "perm_param": param,
                "dir": str(case_dir.name),
            }
        )

    with (out_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def _write_case(
    case_dir: Path,
    in_vec: np.ndarray,
    bind_vec: np.ndarray,
    expected: np.ndarray,
    mode: int,
    param: int,
    cfg: HDCConfig,
) -> None:
    for name, bits in [
        ("in_vec", in_vec),
        ("bind_vec", bind_vec),
        ("expected", expected),
    ]:
        lines = bits_to_hex_lines(bits, cfg.words, cfg.bits_per_word)
        with (case_dir / f"{name}.hex").open("w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    with (case_dir / "ctrl.txt").open("w", encoding="utf-8") as f:
        f.write(f"mode={mode}\nparam={param}\n")


def export_bundle_cosim(
    out_dir: Path,
    cfg: HDCConfig,
    count: int,
    seed: int,
    k_min: int = 2,
    k_max: int = 16,
    cnt_bits: int = 6,
) -> dict:
    """
    Write a flat co-simulation vector set for tb_bundle_cosim.sv.

    Each case bundles K (random, in [k_min, k_max]) random hypervectors using
    the BundleAccumulator (saturating per-bit counters at 2**cnt_bits-1, then
    majority threshold count >= n_accum >> 1) -- i.e. exactly bundle_unit.sv.

    Layout (all under out_dir):
      bundle_in.hex  sum(K_i)*words lines, 16 hex digits each (one 64-bit word)
      expected.hex   count*words lines (the bundled/thresholded result per case)
      kcnt.hex       count lines, one hex value per case = K (vectors in bundle)
      meta.txt       key=value metadata
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    in_lines: List[str] = []
    exp_lines: List[str] = []
    k_lines: List[str] = []

    for _ in range(count):
        K = int(rng.integers(k_min, k_max + 1))
        acc = BundleAccumulator(cfg, cnt_bits=cnt_bits)
        for _ in range(K):
            v = random_bits(rng, cfg.D)
            acc.accumulate(v)
            in_lines.extend(bits_to_hex_lines(v, cfg.words, cfg.bits_per_word))
        out = acc.threshold()
        exp_lines.extend(bits_to_hex_lines(out, cfg.words, cfg.bits_per_word))
        k_lines.append(f"{K:04x}")

    (out_dir / "bundle_in.hex").write_text("\n".join(in_lines) + "\n", encoding="utf-8")
    (out_dir / "expected.hex").write_text("\n".join(exp_lines) + "\n", encoding="utf-8")
    (out_dir / "kcnt.hex").write_text("\n".join(k_lines) + "\n", encoding="utf-8")

    meta = {
        "count": count,
        "D": cfg.D,
        "words": cfg.words,
        "bits_per_word": cfg.bits_per_word,
        "seed": seed,
        "cnt_bits": cnt_bits,
        "k_min": k_min,
        "k_max": k_max,
    }
    (out_dir / "meta.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in meta.items()), encoding="utf-8"
    )
    return meta


def export_am_cosim(
    out_dir: Path,
    cfg: HDCConfig,
    count: int,
    seed: int,
    n_class: int = 8,
    tie_prob: float = 0.12,
    allones_prob: float = 0.2,
) -> dict:
    """
    Write a flat co-simulation vector set for tb_am_cosim.sv (popcount_am).

    Each case holds N_CLASS random prototype hypervectors, a random pruning
    mask, and a random query.  The golden decision is HDCEngine.classify:
    masked Hamming distance to every prototype, then argmin with NumPy's
    first-index-on-tie semantics -- exactly popcount_am.sv (strict '<').

    To exercise the tie-break path, with probability `tie_prob` one prototype
    is duplicated onto another so two classes share the minimum distance; the
    golden (and RTL) must then return the lower index.  With probability
    `allones_prob` the mask is all-ones (unmasked Hamming).

    Layout (all under out_dir):
      am_proto.hex   count*N_CLASS*words lines (all prototypes, class-major)
      am_mask.hex    count*words lines
      am_query.hex   count*words lines
      am_expect.hex  count lines, one 32-bit hex word = (best_idx<<16)|best_dist
      meta.txt       key=value metadata (count, D, words, n_class, seed)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    engine = HDCEngine(cfg)

    proto_lines: List[str] = []
    mask_lines: List[str] = []
    query_lines: List[str] = []
    exp_lines: List[str] = []

    for _ in range(count):
        protos = np.stack([random_bits(rng, cfg.D) for _ in range(n_class)], axis=0)

        if rng.random() < tie_prob and n_class >= 2:
            i = int(rng.integers(0, n_class))
            j = int(rng.integers(0, n_class))
            if i != j:
                protos[j] = protos[i].copy()

        if rng.random() < allones_prob:
            mask = np.ones(cfg.D, dtype=np.uint8)
        else:
            mask = random_bits(rng, cfg.D)

        query = random_bits(rng, cfg.D)
        res = engine.classify(query, protos, mask=mask)

        for k in range(n_class):
            proto_lines.extend(bits_to_hex_lines(protos[k], cfg.words, cfg.bits_per_word))
        mask_lines.extend(bits_to_hex_lines(mask, cfg.words, cfg.bits_per_word))
        query_lines.extend(bits_to_hex_lines(query, cfg.words, cfg.bits_per_word))
        exp_lines.append(f"{((res.class_id << 16) | (res.distance & 0xFFFF)):08x}")

    (out_dir / "am_proto.hex").write_text("\n".join(proto_lines) + "\n", encoding="utf-8")
    (out_dir / "am_mask.hex").write_text("\n".join(mask_lines) + "\n", encoding="utf-8")
    (out_dir / "am_query.hex").write_text("\n".join(query_lines) + "\n", encoding="utf-8")
    (out_dir / "am_expect.hex").write_text("\n".join(exp_lines) + "\n", encoding="utf-8")

    meta = {
        "count": count,
        "D": cfg.D,
        "words": cfg.words,
        "bits_per_word": cfg.bits_per_word,
        "n_class": n_class,
        "seed": seed,
    }
    (out_dir / "meta.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in meta.items()), encoding="utf-8"
    )
    return meta


def export_pruning_mask_hex(mask: np.ndarray, path: Path, cfg: HDCConfig) -> None:
    lines = bits_to_hex_lines(mask, cfg.words, cfg.bits_per_word)
    with path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def export_bind_permute_cosim(
    out_dir: Path,
    cfg: HDCConfig,
    count: int,
    seed: int,
) -> dict:
    """
    Write a flat, $readmemh-friendly co-simulation vector set for tb_cosim.sv.

    Layout (all under out_dir):
      in_vec.hex    count*words lines, 16 hex digits each (one 64-bit word/line)
      bind_vec.hex  same shape
      expected.hex  same shape (RTL-exact golden = bind then permute)
      ctrl.hex      count lines, one 32-bit hex word per case = (mode<<16)|param
      meta.txt      key=value metadata (count, D, words, bits_per_word, seed)

    Word ordering matches bits_to_hex_lines / pack_u64_words: line 0 of a case is
    word 0 = flat bits [63:0]; the testbench reconstructs flat[(w+1)*64-1 -: 64].
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    engine = HDCEngine(cfg)

    in_lines: List[str] = []
    bind_lines: List[str] = []
    exp_lines: List[str] = []
    ctrl_lines: List[str] = []

    for _ in range(count):
        in_vec = random_bits(rng, cfg.D)
        bind_vec = random_bits(rng, cfg.D)
        mode = int(rng.integers(0, 4))
        param = int(rng.integers(0, cfg.D))
        expected = engine.bind_permute(in_vec, bind_vec, mode, param)

        in_lines.extend(bits_to_hex_lines(in_vec, cfg.words, cfg.bits_per_word))
        bind_lines.extend(bits_to_hex_lines(bind_vec, cfg.words, cfg.bits_per_word))
        exp_lines.extend(bits_to_hex_lines(expected, cfg.words, cfg.bits_per_word))
        ctrl_lines.append(f"{((mode << 16) | (param & 0xFFFF)):08x}")

    (out_dir / "in_vec.hex").write_text("\n".join(in_lines) + "\n", encoding="utf-8")
    (out_dir / "bind_vec.hex").write_text("\n".join(bind_lines) + "\n", encoding="utf-8")
    (out_dir / "expected.hex").write_text("\n".join(exp_lines) + "\n", encoding="utf-8")
    (out_dir / "ctrl.hex").write_text("\n".join(ctrl_lines) + "\n", encoding="utf-8")

    meta = {
        "count": count,
        "D": cfg.D,
        "words": cfg.words,
        "bits_per_word": cfg.bits_per_word,
        "seed": seed,
    }
    (out_dir / "meta.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in meta.items()), encoding="utf-8"
    )
    return meta


# ---------------------------------------------------------------------------
# Self-check against permute golden used in tb_xor_permute.sv
# ---------------------------------------------------------------------------

def tb_rotate_right_vec(bits: np.ndarray, r: int, D: int) -> np.ndarray:
    """tb_xor_permute.sv rotate_right_vec (mode 10 golden in testbench)."""
    rr = int(r) % D
    out = zeros(D)
    for i in range(D):
        out[i] = bits[(i + rr) % D]
    return out


def tb_rotate_right_each_word(bits: np.ndarray, r: int, cfg: HDCConfig) -> np.ndarray:
    rr = int(r) % cfg.bits_per_word
    out = zeros(cfg.D)
    for wi in range(cfg.words):
        w = 0
        for bi in range(cfg.bits_per_word):
            if bits[wi * cfg.bits_per_word + bi]:
                w |= 1 << bi
        wr = 0
        for bi in range(cfg.bits_per_word):
            wr_bit = (bi + rr) % cfg.bits_per_word
            if (w >> wr_bit) & 1:
                wr |= 1 << bi
        for bi in range(cfg.bits_per_word):
            out[wi * cfg.bits_per_word + bi] = (wr >> bi) & 1
    return out


def tb_reverse_words(bits: np.ndarray, cfg: HDCConfig) -> np.ndarray:
    out = zeros(cfg.D)
    for wi in range(cfg.words):
        src = cfg.words - 1 - wi
        out[wi * cfg.bits_per_word : (wi + 1) * cfg.bits_per_word] = bits[
            src * cfg.bits_per_word : (src + 1) * cfg.bits_per_word
        ]
    return out


def tb_golden_bind_permute(
    in_vec: np.ndarray,
    bind_vec: np.ndarray,
    mode: int,
    param: int,
    cfg: HDCConfig,
) -> np.ndarray:
    bound = bind(in_vec, bind_vec)
    if mode == 0:
        return tb_reverse_words(bound, cfg)
    if mode == 1:
        return tb_rotate_right_each_word(bound, param, cfg)
    if mode == 2:
        return tb_rotate_right_vec(bound, param, cfg.D)
    return bound


def self_check_permute_modes(cfg: HDCConfig, trials: int = 200, seed: int = 0) -> None:
    """
    Verify permute() against tb_xor_permute.sv golden for modes 0/1/2.
    Mode 2 in RTL (permute_stage) differs from tb rotate_right_vec — this
    function documents any mismatch explicitly.
    """
    rng = np.random.default_rng(seed)
    engine = HDCEngine(cfg)
    for mode in (0, 1, 2):
        for _ in range(trials):
            in_vec = random_bits(rng, cfg.D)
            bind_vec = random_bits(rng, cfg.D)
            param = int(rng.integers(0, cfg.D))
            rtl = engine.bind_permute(in_vec, bind_vec, mode, param)
            tb = tb_golden_bind_permute(in_vec, bind_vec, mode, param, cfg)
            if not np.array_equal(rtl, tb):
                raise AssertionError(
                    f"permute mismatch mode={mode} param={param}: "
                    "RTL permute_stage vs tb_xor_permute golden differ"
                )


if __name__ == "__main__":
    cfg = HDCConfig()
    print("Running hdc_ref self-check...")
    self_check_permute_modes(cfg, trials=50, seed=1)
    print("permute self-check passed (modes 0/1/2 vs tb golden)")
