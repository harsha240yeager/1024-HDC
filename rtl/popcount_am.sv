// popcount_am.sv
// Associative-memory nearest-prototype classifier for 1024-bit Binary Spatter
// Codes.  Stores N_CLASS class prototypes and a per-bit pruning mask, then for
// each query computes the masked Hamming distance to every prototype and emits
// the index of the closest one.  Matches the Python golden reference
// hdc_ref.HDCEngine.classify exactly:
//
//   dist[k] = popcount( (query ^ proto[k]) & mask )
//   best    = argmin_k dist[k]     // first index wins on a tie (NumPy argmin)
//
// Protocol
//   * Load each prototype: drive proto_we=1 with load_idx/load_vec (one/clk).
//   * Load the mask:       drive mask_we=1 with mask_vec (one clk).  If never
//                          loaded after reset the mask is all-ones (unmasked).
//   * Classify:            drive q_valid=1 with query_vec; out_valid pulses one
//                          cycle later with best_idx / best_dist for that query.

module popcount_am #(
    parameter int WORDS         = 16,
    parameter int BITS_PER_WORD = 64,
    parameter int N_CLASS       = 8,
    parameter int D             = WORDS * BITS_PER_WORD,
    parameter int IDX_W         = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS),
    parameter int DIST_W        = $clog2(D + 1)
) (
    input  logic               clk,
    input  logic               rst_n,

    // Prototype write port
    input  logic               proto_we,
    input  logic [IDX_W-1:0]   load_idx,
    input  logic [D-1:0]       load_vec,

    // Mask write port
    input  logic               mask_we,
    input  logic [D-1:0]       mask_vec,

    // Query / classify
    input  logic               q_valid,
    input  logic [D-1:0]       query_vec,

    output logic               out_valid,
    output logic [IDX_W-1:0]   best_idx,
    output logic [DIST_W-1:0]  best_dist
);

    // ------------------------------------------------------------------
    // Storage: prototypes + pruning mask
    // ------------------------------------------------------------------
    logic [D-1:0] proto [0:N_CLASS-1];
    logic [D-1:0] mask;

    integer pi;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (pi = 0; pi < N_CLASS; pi = pi + 1) proto[pi] <= '0;
            mask <= '1;                 // default: unmasked (all bits kept)
        end else begin
            if (proto_we) proto[load_idx] <= load_vec;
            if (mask_we)  mask            <= mask_vec;
        end
    end

    // ------------------------------------------------------------------
    // popcount of a D-bit vector (synthesises to an adder tree)
    // ------------------------------------------------------------------
    function automatic [DIST_W-1:0] popcount(input logic [D-1:0] v);
        integer b;
        logic [DIST_W-1:0] s;
        begin
            s = '0;
            for (b = 0; b < D; b = b + 1) s = s + v[b];
            popcount = s;
        end
    endfunction

    // ------------------------------------------------------------------
    // Combinational masked-Hamming + argmin (first index on tie)
    // ------------------------------------------------------------------
    logic [IDX_W-1:0]  best_idx_c;
    logic [DIST_W-1:0] best_dist_c;

    integer k;
    logic [DIST_W-1:0] dk;
    always_comb begin
        best_idx_c  = '0;
        best_dist_c = '1;               // larger than any real distance (<= D)
        for (k = 0; k < N_CLASS; k = k + 1) begin
            dk = popcount((query_vec ^ proto[k]) & mask);
            if (dk < best_dist_c) begin // strict '<' => first index wins ties
                best_dist_c = dk;
                best_idx_c  = k[IDX_W-1:0];
            end
        end
    end

    // ------------------------------------------------------------------
    // Register the decision; out_valid pulses one cycle after q_valid
    // ------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            best_idx  <= '0;
            best_dist <= '0;
        end else begin
            out_valid <= q_valid;
            if (q_valid) begin
                best_idx  <= best_idx_c;
                best_dist <= best_dist_c;
            end
        end
    end

endmodule
