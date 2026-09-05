// popcount_am_narrow.sv
// Physically narrow associative-memory nearest-prototype classifier (H1, issue #28).
//
// Structurally identical to `popcount_am.sv` except that the datapath is K_BITS
// wide instead of D, and there is no pruning mask:
//
//   dist[k] = popcount( query_narrow ^ proto_narrow[k] )
//   best    = argmin_k dist[k]     // first index wins on a tie (NumPy argmin)
//
// Both operands arrive already gathered to the K_BITS Fisher-selected positions:
//   * query_narrow is wired from the encoder output by a fixed permutation
//     (see hdc_core_top_narrow.sv + hdc_sel_pkg.sv) -- pure routing, 0 LUT
//   * proto_narrow[k] is packed by software, which already applies the mask offline
//
// This is bit-exact to the baseline's masked distance, because popcount is invariant
// to relabeling of bit positions:
//
//   sum_i ( q[SEL[i]] ^ p[SEL[i]] )  ==  popcount( (q ^ p) & mask )
//
// so no mask register, no mask_in port, and no AND term are needed.  Verified against
// the Python golden by scripts/verify_narrow_gather_equivalence.py (0 distance and 0
// prediction mismatches over 20k windows).  See docs/H1_narrow_datapath_design.md.
//
// Classify is fully pipelined, as in the baseline:
//   * one BITS_PER_WORD XOR word per cycle
//   * one popcount + accumulate per cycle
//   * one compare cycle per prototype
//   Total latency after q_valid: N_CLASS * (K_WORDS * 2 + 1) cycles.
//   At K_BITS=128 that is 8*(2*2+1) = 40 cycles, vs 264 for the D=1024 baseline.
//
// NOTE on best_dist scale: DIST_W here is $clog2(K_BITS+1) (8 bits at K_BITS=128),
// not $clog2(D+1).  Distances are out of K_BITS, so host software must not compare
// them numerically against baseline full-width distances.

module popcount_am_narrow #(
    parameter int K_BITS        = 128,
    parameter int BITS_PER_WORD = 64,
    parameter int N_CLASS       = 8,
    parameter int K_WORDS       = (K_BITS + BITS_PER_WORD - 1) / BITS_PER_WORD,
    parameter int IDX_W         = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS),
    parameter int DIST_W        = $clog2(K_BITS + 1)
) (
    input  logic               clk,
    input  logic               rst_n,

    input  logic               proto_we,
    input  logic [IDX_W-1:0]   load_idx,
    input  logic [K_BITS-1:0]  load_vec,     // pre-gathered prototype

    input  logic               q_valid,
    input  logic [K_BITS-1:0]  query_vec,    // pre-gathered query

    output logic               am_busy,
    output logic               out_valid,
    output logic [IDX_W-1:0]   best_idx,
    output logic [DIST_W-1:0]  best_dist
);

    // Padded storage width.  When K_BITS is not a multiple of BITS_PER_WORD the top
    // word is zero-filled; zero bits XOR to zero and so contribute nothing to the
    // popcount, which keeps the word-at-a-time FSM unchanged.  (K_BITS = 128/256/512
    // are exact multiples anyway.)
    localparam int PAD_BITS   = K_WORDS * BITS_PER_WORD;
    localparam int WORD_IDX_W = (K_WORDS <= 1) ? 1 : $clog2(K_WORDS);
    localparam int POP_W      = $clog2(BITS_PER_WORD + 1);

    // Width-exact terminal indices (cast-free, matching popcount_am.sv so older SV
    // front-ends that reject parameter-sized casts still compile this module).
    localparam logic [WORD_IDX_W-1:0] LAST_WORD  = K_WORDS - 1;
    localparam logic [IDX_W-1:0]      LAST_CLASS = N_CLASS - 1;

    // synthesis translate_off
    initial begin
        if (K_BITS > PAD_BITS)
            $fatal(1, "popcount_am_narrow: K_BITS (%0d) > PAD_BITS (%0d)", K_BITS, PAD_BITS);
    end
    // synthesis translate_on

    typedef enum logic [2:0] { S_IDLE, S_XOR, S_ACC, S_CMP } state_t;

    state_t                   state;
    logic [PAD_BITS-1:0]      query_r;
    logic [BITS_PER_WORD-1:0] xor_w;
    logic [WORD_IDX_W-1:0]    w_idx;
    logic [IDX_W-1:0]         k_idx;
    logic [IDX_W-1:0]         run_best_idx;
    logic [DIST_W-1:0]        run_best_dist;
    logic [DIST_W-1:0]        acc_dist;
    logic [DIST_W-1:0]        dk_r;

    logic [POP_W-1:0]         word_pop_c;
    logic [DIST_W-1:0]        acc_next_c;
    logic [IDX_W-1:0]         final_idx_c;
    logic [DIST_W-1:0]        final_dist_c;

    // Zero-extend the gathered operands into padded width.
    logic [PAD_BITS-1:0] query_pad_c;
    logic [PAD_BITS-1:0] load_pad_c;
    assign query_pad_c = {{(PAD_BITS - K_BITS){1'b0}}, query_vec};
    assign load_pad_c  = {{(PAD_BITS - K_BITS){1'b0}}, load_vec};

    assign am_busy = (state != S_IDLE);

    function automatic [POP_W-1:0] popcount_word(input logic [BITS_PER_WORD-1:0] v);
        integer b;
        logic [POP_W-1:0] s;
        begin
            s = '0;
            for (b = 0; b < BITS_PER_WORD; b = b + 1)
                s = s + v[b];
            popcount_word = s;
        end
    endfunction

    assign word_pop_c = popcount_word(xor_w);
    assign acc_next_c = acc_dist + word_pop_c;   // word_pop_c zero-extends to DIST_W

    always_comb begin
        if (dk_r < run_best_dist) begin
            final_idx_c  = k_idx;
            final_dist_c = dk_r;
        end else begin
            final_idx_c  = run_best_idx;
            final_dist_c = run_best_dist;
        end
    end

    // Prototypes use synchronous reset to avoid huge async-reset fanout (as baseline).
    logic [PAD_BITS-1:0] proto [0:N_CLASS-1];

    integer pi;
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (pi = 0; pi < N_CLASS; pi = pi + 1)
                proto[pi] <= '0;
        end else begin
            if (proto_we) proto[load_idx] <= load_pad_c;
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            query_r       <= '0;
            xor_w         <= '0;
            w_idx         <= '0;
            k_idx         <= '0;
            run_best_idx  <= '0;
            run_best_dist <= '0;
            acc_dist      <= '0;
            dk_r          <= '0;
            out_valid     <= 1'b0;
            best_idx      <= '0;
            best_dist     <= '0;
        end else begin
            out_valid <= 1'b0;

            case (state)
                S_IDLE: begin
                    if (q_valid) begin
                        query_r       <= query_pad_c;
                        k_idx         <= '0;
                        w_idx         <= '0;
                        acc_dist      <= '0;
                        run_best_idx  <= '0;
                        run_best_dist <= {DIST_W{1'b1}};
                        state         <= S_XOR;
                    end
                end

                // No `& mask_in` term: the mask is baked into the operand routing.
                S_XOR: begin
                    xor_w <= query_r[w_idx * BITS_PER_WORD +: BITS_PER_WORD] ^
                             proto[k_idx][w_idx * BITS_PER_WORD +: BITS_PER_WORD];
                    state <= S_ACC;
                end

                S_ACC: begin
                    acc_dist <= acc_next_c;

                    if (w_idx == LAST_WORD) begin
                        dk_r  <= acc_next_c;
                        state <= S_CMP;
                    end else begin
                        w_idx <= w_idx + 1'b1;
                        state <= S_XOR;
                    end
                end

                S_CMP: begin
                    if (dk_r < run_best_dist) begin
                        run_best_dist <= dk_r;
                        run_best_idx  <= k_idx;
                    end

                    if (k_idx == LAST_CLASS) begin
                        best_idx  <= final_idx_c;
                        best_dist <= final_dist_c;
                        out_valid <= 1'b1;
                        state     <= S_IDLE;
                    end else begin
                        k_idx    <= k_idx + 1'b1;
                        w_idx    <= '0;
                        acc_dist <= '0;
                        state    <= S_XOR;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
