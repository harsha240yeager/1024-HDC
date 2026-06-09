// encoder_top.sv
// EMG-window encoder: turns one quantized window into a query hypervector,
// matching hdc_ref.HDCEngine.encode_emg_window exactly.
//
// For each (channel c, feature f) pair the record contribution is
//     pair = channel[c] XOR value[level] XOR permute(feature[f], mode=2, param=f)
// and the query hypervector is the majority bundle of all N_CH*N_FEAT pairs.
//
// The three item memories (channel / feature / value-CiM) are item_mem ROMs
// initialised from .mem files.  The bundle is the verified bundle_unit.
//
// Protocol: pulse `start` with the level grid stable on `levels_flat`
// (pair p = c*N_FEAT + f, level at bits [p*LEVEL_W +: LEVEL_W]); `out_valid`
// pulses with the finished `query_vec`.  Encode latency = N_PAIRS + a few cycles.

module encoder_top #(
    parameter int WORDS         = 16,
    parameter int BITS_PER_WORD = 64,
    parameter int N_CH          = 4,
    parameter int N_FEAT        = 5,
    parameter int N_VAL         = 16,
    parameter int CNT_W         = 6,
    parameter int D             = WORDS * BITS_PER_WORD,
    parameter int N_PAIRS       = N_CH * N_FEAT,
    parameter int LEVEL_W       = (N_VAL <= 1) ? 1 : $clog2(N_VAL),
    parameter     CH_MEM        = "python_ref/vectors/cosim_encoder/item_mem_channel.mem",
    parameter     FT_MEM        = "python_ref/vectors/cosim_encoder/item_mem_feature.mem",
    parameter     VAL_MEM       = "python_ref/vectors/cosim_encoder/item_mem_value.mem"
) (
    input  logic                          clk,
    input  logic                          rst_n,
    input  logic                          start,
    input  logic [N_PAIRS*LEVEL_W-1:0]    levels_flat,
    output logic                          busy,
    output logic                          out_valid,
    output logic [D-1:0]                  query_vec
);

    localparam int CH_IDX_W  = (N_CH   <= 1) ? 1 : $clog2(N_CH);
    localparam int FT_IDX_W  = (N_FEAT <= 1) ? 1 : $clog2(N_FEAT);
    localparam int VAL_IDX_W = (N_VAL  <= 1) ? 1 : $clog2(N_VAL);
    localparam int P_W       = $clog2(N_PAIRS + 1);

    // ------------------------------------------------------------------
    // FSM
    // ------------------------------------------------------------------
    typedef enum logic [1:0] { S_IDLE, S_CLR, S_ACC, S_DONE } state_t;
    state_t        state;
    logic [P_W-1:0] p;

    // ------------------------------------------------------------------
    // Per-pair index decode (combinational from p / levels_flat)
    // ------------------------------------------------------------------
    int                   c, f;
    logic [CH_IDX_W-1:0]  c_idx;
    logic [FT_IDX_W-1:0]  f_idx;
    logic [VAL_IDX_W-1:0] lvl_idx;

    always_comb begin
        c       = p / N_FEAT;
        f       = p - c * N_FEAT;
        c_idx   = c[CH_IDX_W-1:0];
        f_idx   = f[FT_IDX_W-1:0];
        lvl_idx = levels_flat[p*LEVEL_W +: LEVEL_W];
    end

    // ------------------------------------------------------------------
    // Item memories
    // ------------------------------------------------------------------
    logic [D-1:0] ch_hv, ft_hv, val_hv;

    item_mem #(.WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
               .N_ENTRIES(N_CH), .MEMFILE(CH_MEM)) u_ch (
        .rd_idx(c_idx), .rd_vec(ch_hv)
    );
    item_mem #(.WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
               .N_ENTRIES(N_FEAT), .MEMFILE(FT_MEM)) u_ft (
        .rd_idx(f_idx), .rd_vec(ft_hv)
    );
    item_mem #(.WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
               .N_ENTRIES(N_VAL), .MEMFILE(VAL_MEM)) u_val (
        .rd_idx(lvl_idx), .rd_vec(val_hv)
    );

    // ------------------------------------------------------------------
    // permute(feature, mode=2, param=f) -- full-D rotate, word-granular,
    // identical to permute_stage.sv mode 2'b10.
    // ------------------------------------------------------------------
    function automatic logic [D-1:0] perm_feat(input logic [D-1:0] v, input int prm);
        logic [BITS_PER_WORD-1:0] inw [0:WORDS-1];
        logic [BITS_PER_WORD-1:0] ow  [0:WORDS-1];
        int rot, word_rot, bit_rot, src0, src1, kk;
        logic [D-1:0] res;
        begin
            for (kk = 0; kk < WORDS; kk++)
                inw[kk] = v[(kk+1)*BITS_PER_WORD-1 -: BITS_PER_WORD];
            rot      = prm % D;
            word_rot = rot / BITS_PER_WORD;
            bit_rot  = rot % BITS_PER_WORD;
            for (kk = 0; kk < WORDS; kk++) begin
                src0 = (kk + word_rot)     % WORDS;
                src1 = (kk + word_rot + 1) % WORDS;
                if (bit_rot == 0)
                    ow[kk] = inw[src0];
                else
                    ow[kk] = (inw[src0] >> bit_rot) |
                             (inw[src1] << (BITS_PER_WORD - bit_rot));
            end
            res = '0;
            for (kk = 0; kk < WORDS; kk++)
                res[(kk+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = ow[kk];
            return res;
        end
    endfunction

    // ------------------------------------------------------------------
    // Bind: pair = channel ^ value ^ permute(feature, f)
    // ------------------------------------------------------------------
    logic [D-1:0] pair;
    always_comb begin
        pair = ch_hv ^ val_hv ^ perm_feat(ft_hv, f_idx);
    end

    // ------------------------------------------------------------------
    // Bundle (verified bundle_unit) accumulates each pair
    // ------------------------------------------------------------------
    logic              bnd_clear;
    logic              bnd_in_valid;
    logic [D-1:0]      bnd_out;
    logic [31:0]       bnd_n;

    assign bnd_clear    = (state == S_CLR);
    assign bnd_in_valid = (state == S_ACC);

    bundle_unit #(.WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD), .CNT_W(CNT_W)) u_bundle (
        .clk         (clk),
        .rst_n       (rst_n),
        .clear       (bnd_clear),
        .in_valid    (bnd_in_valid),
        .in_vec_flat (pair),
        .out_vec_flat(bnd_out),
        .n_accum_out (bnd_n)
    );

    // ------------------------------------------------------------------
    // Control
    // ------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= S_IDLE;
            p         <= '0;
            busy      <= 1'b0;
            out_valid <= 1'b0;
            query_vec <= '0;
        end else begin
            out_valid <= 1'b0;
            case (state)
                S_IDLE: begin
                    if (start) begin
                        busy  <= 1'b1;
                        p     <= '0;
                        state <= S_CLR;
                    end
                end
                S_CLR: begin
                    p     <= '0;            // bnd_clear asserted this cycle
                    state <= S_ACC;
                end
                S_ACC: begin
                    // bundle accumulates pair[p] on this edge
                    if (p == N_PAIRS-1)
                        state <= S_DONE;
                    p <= p + 1'b1;
                end
                S_DONE: begin
                    query_vec <= bnd_out;   // all N_PAIRS now accumulated
                    out_valid <= 1'b1;
                    busy      <= 1'b0;
                    state     <= S_IDLE;
                end
                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
