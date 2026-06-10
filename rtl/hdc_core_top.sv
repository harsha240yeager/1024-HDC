// hdc_core_top.sv
// End-to-end HDC inference core: quantized EMG window in, class label out.
//
// Composes the two verified blocks:
//
//   levels_flat -> encoder_top  (item_mem lookups, bind ^ permute, bundle)
//               -> popcount_am  (masked Hamming to N_CLASS prototypes, argmin)
//               -> class_idx / class_dist
//
// Matches the Python golden end-to-end:
//   query     = HDCEngine.encode_emg_window(levels)
//   idx, dist = HDCEngine.classify(query, protos, mask)
//
// Configuration (before inference):
//   * load each prototype: proto_we=1 with proto_idx / proto_vec (one/clk)
//   * load the mask:       mask_we=1 with mask_vec (one clk); defaults to
//                          all-ones after reset (unmasked Hamming)
//   * item memories initialise from .mem files via parameters
//
// Inference: pulse `start` with the level grid on `levels_flat`; `out_valid`
// pulses with class_idx / class_dist.  Latency = encode (N_PAIRS + ~3) + 1.

module hdc_core_top #(
    parameter int WORDS         = 16,
    parameter int BITS_PER_WORD = 64,
    parameter int N_CH          = 4,
    parameter int N_FEAT        = 5,
    parameter int N_VAL         = 16,
    parameter int N_CLASS       = 8,
    parameter int CNT_W         = 6,
    parameter int D             = WORDS * BITS_PER_WORD,
    parameter int N_PAIRS       = N_CH * N_FEAT,
    parameter int LEVEL_W       = (N_VAL   <= 1) ? 1 : $clog2(N_VAL),
    parameter int IDX_W         = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS),
    parameter int DIST_W        = $clog2(D + 1),
    parameter     CH_MEM        = "python_ref/vectors/cosim_core/item_mem_channel.mem",
    parameter     FT_MEM        = "python_ref/vectors/cosim_core/item_mem_feature.mem",
    parameter     VAL_MEM       = "python_ref/vectors/cosim_core/item_mem_value.mem"
) (
    input  logic                       clk,
    input  logic                       rst_n,

    // Configuration: prototype + mask write ports (popcount_am passthrough)
    input  logic                       proto_we,
    input  logic [IDX_W-1:0]           proto_idx,
    input  logic [D-1:0]               proto_vec,
    input  logic                       mask_we,
    input  logic [D-1:0]               mask_vec,

    // Inference
    input  logic                       start,
    input  logic [N_PAIRS*LEVEL_W-1:0] levels_flat,
    output logic                       busy,
    output logic                       out_valid,
    output logic [IDX_W-1:0]           class_idx,
    output logic [DIST_W-1:0]          class_dist
);

    // ------------------------------------------------------------------
    // Encoder: window -> query hypervector
    // ------------------------------------------------------------------
    logic         enc_out_valid;
    logic [D-1:0] enc_query;

    encoder_top #(
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
        .N_CH(N_CH), .N_FEAT(N_FEAT), .N_VAL(N_VAL), .CNT_W(CNT_W),
        .CH_MEM(CH_MEM), .FT_MEM(FT_MEM), .VAL_MEM(VAL_MEM)
    ) u_encoder (
        .clk        (clk),
        .rst_n      (rst_n),
        .start      (start),
        .levels_flat(levels_flat),
        .busy       (busy),
        .out_valid  (enc_out_valid),
        .query_vec  (enc_query)
    );

    // ------------------------------------------------------------------
    // Associative memory: query -> nearest prototype
    // The encoder's out_valid/query_vec drive the AM's q_valid/query_vec
    // directly; the AM registers its decision, so out_valid here pulses
    // one cycle after the encoder finishes.
    // ------------------------------------------------------------------
    popcount_am #(
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD), .N_CLASS(N_CLASS)
    ) u_am (
        .clk      (clk),
        .rst_n    (rst_n),
        .proto_we (proto_we),
        .load_idx (proto_idx),
        .load_vec (proto_vec),
        .mask_we  (mask_we),
        .mask_vec (mask_vec),
        .q_valid  (enc_out_valid),
        .query_vec(enc_query),
        .out_valid(out_valid),
        .best_idx (class_idx),
        .best_dist(class_dist)
    );

endmodule
