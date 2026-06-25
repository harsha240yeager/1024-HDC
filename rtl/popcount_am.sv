// popcount_am.sv
// Associative-memory nearest-prototype classifier for 1024-bit Binary Spatter
// Codes.  Stores N_CLASS class prototypes and, for each query, computes the
// masked Hamming distance to every prototype and emits the index of the closest
// one.  The per-bit pruning mask is supplied on `mask_in` by the dedicated
// `pruning_mask` module (research plan §5.3.3); this block only applies it.
//   Matches the Python golden reference hdc_ref.HDCEngine.classify exactly:
//
//   dist[k] = popcount( (query ^ proto[k]) & mask )
//   best    = argmin_k dist[k]     // first index wins on a tie (NumPy argmin)
//
// Classify is fully pipelined:
//   * one 64-bit XOR/mask word per cycle
//   * one 64-bit popcount + accumulate per cycle
//   * one compare cycle per prototype
//   Total latency after q_valid: N_CLASS * (WORDS * 2 + 1) cycles.

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

    input  logic               proto_we,
    input  logic [IDX_W-1:0]   load_idx,
    input  logic [D-1:0]       load_vec,

    input  logic [D-1:0]       mask_in,

    input  logic               q_valid,
    input  logic [D-1:0]       query_vec,

    output logic               am_busy,
    output logic               out_valid,
    output logic [IDX_W-1:0]   best_idx,
    output logic [DIST_W-1:0]  best_dist
);

    localparam int WORD_IDX_W = (WORDS <= 1) ? 1 : $clog2(WORDS);
    localparam int POP_W      = $clog2(BITS_PER_WORD + 1);

    // Width-exact terminal indices (cast-free so older SV front-ends that reject
    // parameter-sized casts -- e.g. DIST_W'(x) -- still compile this module).
    localparam logic [WORD_IDX_W-1:0] LAST_WORD  = WORDS   - 1;
    localparam logic [IDX_W-1:0]      LAST_CLASS = N_CLASS - 1;

    typedef enum logic [2:0] { S_IDLE, S_XOR, S_ACC, S_CMP } state_t;

    state_t              state;
    logic [D-1:0]        query_r;
    logic [BITS_PER_WORD-1:0] xor_w;
    logic [WORD_IDX_W-1:0] w_idx;
    logic [IDX_W-1:0]    k_idx;
    logic [IDX_W-1:0]    run_best_idx;
    logic [DIST_W-1:0]   run_best_dist;
    logic [DIST_W-1:0]   acc_dist;
    logic [DIST_W-1:0]   dk_r;

    logic [POP_W-1:0]    word_pop_c;
    logic [DIST_W-1:0]   acc_next_c;
    logic [IDX_W-1:0]    final_idx_c;
    logic [DIST_W-1:0]   final_dist_c;

    assign am_busy = (state != S_IDLE);

    function automatic [POP_W-1:0] popcount64(input logic [BITS_PER_WORD-1:0] v);
        integer b;
        logic [POP_W-1:0] s;
        begin
            s = '0;
            for (b = 0; b < BITS_PER_WORD; b = b + 1)
                s = s + v[b];
            popcount64 = s;
        end
    endfunction

    assign word_pop_c  = popcount64(xor_w);
    assign acc_next_c  = acc_dist + word_pop_c;   // word_pop_c zero-extends to DIST_W

    always_comb begin
        if (dk_r < run_best_dist) begin
            final_idx_c  = k_idx;
            final_dist_c = dk_r;
        end else begin
            final_idx_c  = run_best_idx;
            final_dist_c = run_best_dist;
        end
    end

    // Prototypes use synchronous reset to avoid huge async-reset fanout.
    // The pruning mask is held externally in `pruning_mask` and arrives on mask_in.
    logic [D-1:0] proto [0:N_CLASS-1];

    integer pi;
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (pi = 0; pi < N_CLASS; pi = pi + 1)
                proto[pi] <= '0;
        end else begin
            if (proto_we) proto[load_idx] <= load_vec;
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
                        query_r       <= query_vec;
                        k_idx         <= '0;
                        w_idx         <= '0;
                        acc_dist      <= '0;
                        run_best_idx  <= '0;
                        run_best_dist <= {DIST_W{1'b1}};
                        state         <= S_XOR;
                    end
                end

                S_XOR: begin
                    xor_w <= (query_r[w_idx * BITS_PER_WORD +: BITS_PER_WORD] ^
                              proto[k_idx][w_idx * BITS_PER_WORD +: BITS_PER_WORD]) &
                             mask_in[w_idx * BITS_PER_WORD +: BITS_PER_WORD];
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
