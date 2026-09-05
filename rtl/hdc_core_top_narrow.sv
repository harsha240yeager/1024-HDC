// hdc_core_top_narrow.sv
// End-to-end HDC inference core with the H1 narrow AM datapath (issue #28, Option E).
//
//   levels_flat -> encoder_top        (full D-bit encode, unchanged)
//               -> baked gather       (fixed wire permutation, 0 LUT)
//               -> popcount_am_narrow (K_BITS-wide Hamming + argmin)
//               -> class_idx / class_dist
//
// Kept as a separate top from `hdc_core_top.sv` on purpose: the baseline file is left
// byte-identical so the existing co-sim logs stay a valid regression reference.
//
// The gather replaces the runtime pruning mask.  `hdc_sel_pkg::SEL_FLAT` lists the
// Fisher-selected bit positions as synthesis-time constants, so
//
//     query_narrow[i] = enc_query[SEL[i]]
//
// is a constant-indexed bit-select per lane: pure routing, no muxes, no LUTs.  Because
// popcount is invariant to bit relabeling, the resulting distances are identical to the
// baseline's popcount((q ^ p) & mask).  `pruning_mask` is therefore not instantiated.
//
// Configuration (before inference):
//   * load each prototype: proto_we=1 with proto_idx / proto_vec (one/clk).
//     proto_vec is **pre-gathered** to the K_BITS selected positions -- software already
//     applies the mask offline, so this adds no host-side work.
//   * no mask load step exists; the mask is baked at synthesis.
//   * item memories initialise from .mem files via parameters.
//
// Inference: pulse `start` with the level grid on `levels_flat`; `out_valid` pulses with
// class_idx / class_dist.  Latency = encode (N_PAIRS + ~3) + N_CLASS * (2*K_WORDS + 1).
// At D=1024 / K_BITS=128 that is 23 + 40 = 63 cycles, vs 287 for the baseline.
//
// Regenerate the gather table:  python3 scripts/gen_sel_table.py --keep 0.125
// Identity build for regression: python3 scripts/gen_sel_table.py --identity
//   (K_BITS=D, SEL[i]=i -- must be bit-identical to hdc_core_top)

module hdc_core_top_narrow #(
    parameter int WORDS         = 16,
    parameter int BITS_PER_WORD = 64,
    parameter int N_CH          = 4,
    parameter int N_FEAT        = 5,
    parameter int N_VAL         = 16,
    parameter int N_CLASS       = 8,
    parameter int CNT_W         = 6,
    parameter int D             = WORDS * BITS_PER_WORD,
    parameter int K_BITS        = hdc_sel_pkg::K_BITS,
    parameter int K_WORDS       = (K_BITS + BITS_PER_WORD - 1) / BITS_PER_WORD,
    parameter int N_PAIRS       = N_CH * N_FEAT,
    parameter int LEVEL_W       = (N_VAL   <= 1) ? 1 : $clog2(N_VAL),
    parameter int IDX_W         = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS),
    parameter int DIST_W        = $clog2(K_BITS + 1),
    parameter     CH_MEM        = "python_ref/vectors/cosim_core/item_mem_channel.mem",
    parameter     FT_MEM        = "python_ref/vectors/cosim_core/item_mem_feature.mem",
    parameter     VAL_MEM       = "python_ref/vectors/cosim_core/item_mem_value.mem"
) (
    input  logic                       clk,
    input  logic                       rst_n,

    // Configuration: prototype write port (pre-gathered, K_BITS wide).
    // No mask port -- the mask is baked into the gather (see hdc_sel_pkg).
    input  logic                       proto_we,
    input  logic [IDX_W-1:0]           proto_idx,
    input  logic [K_BITS-1:0]          proto_vec,

    // Inference
    input  logic                       start,
    input  logic [N_PAIRS*LEVEL_W-1:0] levels_flat,
    output logic                       busy,
    output logic                       out_valid,
    output logic [IDX_W-1:0]           class_idx,
    output logic [DIST_W-1:0]          class_dist
);

    // synthesis translate_off
    initial begin
        if (hdc_sel_pkg::D != D)
            $fatal(1, "hdc_core_top_narrow: hdc_sel_pkg::D (%0d) != D (%0d) -- regenerate with scripts/gen_sel_table.py",
                   hdc_sel_pkg::D, D);
        if (K_BITS > D)
            $fatal(1, "hdc_core_top_narrow: K_BITS (%0d) > D (%0d)", K_BITS, D);
    end
    // synthesis translate_on

    // ------------------------------------------------------------------
    // Encoder: window -> full D-bit query hypervector (unchanged from baseline)
    // ------------------------------------------------------------------
    logic              enc_out_valid;
    logic              enc_busy;
    logic              am_busy;
    logic [D-1:0]      enc_query;
    logic [K_BITS-1:0] query_narrow;

    assign busy = enc_busy | am_busy;

    encoder_top #(
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
        .N_CH(N_CH), .N_FEAT(N_FEAT), .N_VAL(N_VAL), .CNT_W(CNT_W),
        .CH_MEM(CH_MEM), .FT_MEM(FT_MEM), .VAL_MEM(VAL_MEM)
    ) u_encoder (
        .clk        (clk),
        .rst_n      (rst_n),
        .start      (start),
        .levels_flat(levels_flat),
        .busy       (enc_busy),
        .out_valid  (enc_out_valid),
        .query_vec  (enc_query)
    );

    // ------------------------------------------------------------------
    // Baked gather (replaces pruning_mask).  One constant-indexed bit-select per
    // lane; SRC is a localparam so the constness is explicit to every front-end.
    // The D-K_BITS unselected encoder outputs are left dangling on purpose -- any
    // encoder logic feeding only those may then be pruned by synthesis (see
    // docs/H1_narrow_datapath_design.md §6.2; measured in #29, not assumed).
    // ------------------------------------------------------------------
    genvar gi;
    generate
        for (gi = 0; gi < K_BITS; gi = gi + 1) begin : g_gather
            localparam int SRC =
                hdc_sel_pkg::SEL_FLAT[gi*hdc_sel_pkg::IDX_W +: hdc_sel_pkg::IDX_W];
            assign query_narrow[gi] = enc_query[SRC];
        end
    endgenerate

    // ------------------------------------------------------------------
    // Narrow associative memory: gathered query -> nearest prototype
    // ------------------------------------------------------------------
    popcount_am_narrow #(
        .K_BITS(K_BITS), .BITS_PER_WORD(BITS_PER_WORD), .N_CLASS(N_CLASS)
    ) u_am (
        .clk      (clk),
        .rst_n    (rst_n),
        .proto_we (proto_we),
        .load_idx (proto_idx),
        .load_vec (proto_vec),
        .q_valid  (enc_out_valid),
        .query_vec(query_narrow),
        .am_busy  (am_busy),
        .out_valid(out_valid),
        .best_idx (class_idx),
        .best_dist(class_dist)
    );

endmodule
