// bundle_unit.sv
// Streaming majority-bundle of 1024-bit hypervectors (Binary Spatter Code).
//
// Accumulates per-bit "1" counts over a sequence of input vectors, then
// produces the bundled vector by majority threshold.  Matches the Python
// golden reference hdc_ref.BundleAccumulator exactly:
//
//   * per-bit saturating counter, width CNT_W, saturates at 2**CNT_W-1
//   * n_accum counts the number of accumulated vectors
//   * out[i] = (n_accum != 0) && (cnt[i] >= (n_accum >> 1))   // floor(n/2)
//
// Usage: pulse `clear` to start a new bundle, assert `in_valid` with each
// vector on `in_vec_flat`; `out_vec_flat` is the combinational majority result
// of everything accumulated so far.

module bundle_unit #(
    parameter int WORDS         = 16,
    parameter int BITS_PER_WORD = 64,
    parameter int CNT_W         = 6,
    parameter int D             = WORDS * BITS_PER_WORD
) (
    input  logic              clk,
    input  logic              rst_n,

    input  logic              clear,        // synchronous: reset accumulator
    input  logic              in_valid,     // accumulate in_vec_flat this cycle
    input  logic [D-1:0]      in_vec_flat,

    output logic [D-1:0]      out_vec_flat, // combinational majority threshold
    output logic [31:0]       n_accum_out
);

    localparam logic [CNT_W-1:0] CNT_MAX = '1;

    logic [CNT_W-1:0] cnt [0:D-1];
    logic [31:0]      n_accum;

    // Separate module-scope loop variables per process (older-ModelSim safe).
    integer ia;
    integer ic;
    logic [31:0] thr;
    logic [31:0] cnt_ext;

    // ---------------------------------------------------------------
    // Accumulation: saturating per-bit counters
    // ---------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (ia = 0; ia < D; ia = ia + 1) cnt[ia] <= '0;
            n_accum <= 32'd0;
        end else if (clear) begin
            for (ia = 0; ia < D; ia = ia + 1) cnt[ia] <= '0;
            n_accum <= 32'd0;
        end else if (in_valid) begin
            for (ia = 0; ia < D; ia = ia + 1) begin
                if (in_vec_flat[ia] && (cnt[ia] != CNT_MAX)) begin
                    cnt[ia] <= cnt[ia] + 1'b1;
                end
            end
            n_accum <= n_accum + 32'd1;
        end
    end

    // ---------------------------------------------------------------
    // Majority threshold (combinational): cnt >= floor(n_accum/2)
    // ---------------------------------------------------------------
    always_comb begin
        thr = n_accum >> 1;
        for (ic = 0; ic < D; ic = ic + 1) begin
            cnt_ext = {{(32-CNT_W){1'b0}}, cnt[ic]};
            if (n_accum == 32'd0)
                out_vec_flat[ic] = 1'b0;
            else
                out_vec_flat[ic] = (cnt_ext >= thr);
        end
    end

    assign n_accum_out = n_accum;

endmodule
