// hdc_stream_wrapper_narrow.sv
// AXI4-Stream wrapper around hdc_core_top_narrow (H1, issue #28/#29).
//
// Same beat assembly / FIFO / result packing as hdc_stream_wrapper, but the core
// uses the baked gather + narrow AM (no runtime mask load).  Prototypes are
// pre-gathered to K_BITS on proto_vec.

module hdc_stream_wrapper_narrow #(
    parameter int TDATA_W       = 32,
    parameter int WORDS         = 16,
    parameter int BITS_PER_WORD = 64,
    parameter int N_CH          = 4,
    parameter int N_FEAT        = 5,
    parameter int N_VAL         = 16,
    parameter int N_CLASS       = 8,
    parameter int CNT_W         = 6,
    parameter int D             = WORDS * BITS_PER_WORD,
    parameter int K_BITS        = hdc_sel_pkg::K_BITS,
    parameter int N_PAIRS       = N_CH * N_FEAT,
    parameter int LEVEL_W       = (N_VAL   <= 1) ? 1 : $clog2(N_VAL),
    parameter int IDX_W         = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS),
    parameter int DIST_W        = $clog2(K_BITS + 1),
    parameter int LVL_BITS      = N_PAIRS * LEVEL_W,
    parameter int IN_BEATS      = (LVL_BITS + TDATA_W - 1) / TDATA_W,
    parameter int BEAT_W        = (IN_BEATS <= 1) ? 1 : $clog2(IN_BEATS),
    parameter int IN_FIFO_DEPTH = 32,
    parameter     CH_MEM        = "python_ref/vectors/cosim_core/item_mem_channel.mem",
    parameter     FT_MEM        = "python_ref/vectors/cosim_core/item_mem_feature.mem",
    parameter     VAL_MEM       = "python_ref/vectors/cosim_core/item_mem_value.mem"
) (
    input  logic               aclk,
    input  logic               aresetn,

    input  logic               proto_we,
    input  logic [IDX_W-1:0]   proto_idx,
    input  logic [K_BITS-1:0]  proto_vec,

    input  logic               s_axis_tvalid,
    output logic               s_axis_tready,
    input  logic [TDATA_W-1:0] s_axis_tdata,
    input  logic               s_axis_tlast,

    output logic               m_axis_tvalid,
    input  logic               m_axis_tready,
    output logic [TDATA_W-1:0] m_axis_tdata,
    output logic               m_axis_tlast,

    output logic [1:0]         dbg_fsm_state,
    output logic [BEAT_W-1:0]  dbg_beat,
    output logic [LVL_BITS-1:0] dbg_levels_flat,
    output logic               dbg_core_start,
    output logic               dbg_core_busy,
    output logic               dbg_core_out_valid,
    output logic [IDX_W-1:0]   dbg_class_idx,
    output logic [DIST_W-1:0]  dbg_class_dist
);

    localparam int FIFO_PTR_W = (IN_FIFO_DEPTH <= 1) ? 1 : $clog2(IN_FIFO_DEPTH);
    localparam int FIFO_CNT_W = $clog2(IN_FIFO_DEPTH + 1);

    logic                core_start;
    logic [LVL_BITS-1:0] levels_reg;
    logic                core_busy;
    logic                core_out_valid;
    logic [IDX_W-1:0]    core_class_idx;
    logic [DIST_W-1:0]   core_class_dist;

    hdc_core_top_narrow #(
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
        .N_CH(N_CH), .N_FEAT(N_FEAT), .N_VAL(N_VAL),
        .N_CLASS(N_CLASS), .CNT_W(CNT_W),
        .CH_MEM(CH_MEM), .FT_MEM(FT_MEM), .VAL_MEM(VAL_MEM)
    ) u_core (
        .clk        (aclk),
        .rst_n      (aresetn),
        .proto_we   (proto_we),
        .proto_idx  (proto_idx),
        .proto_vec  (proto_vec),
        .start      (core_start),
        .levels_flat(levels_reg),
        .busy       (core_busy),
        .out_valid  (core_out_valid),
        .class_idx  (core_class_idx),
        .class_dist (core_class_dist)
    );

    logic [TDATA_W-1:0] fifo_data [0:IN_FIFO_DEPTH-1];
    logic               fifo_last [0:IN_FIFO_DEPTH-1];
    logic [FIFO_PTR_W-1:0] fifo_wr_ptr, fifo_rd_ptr;
    logic [FIFO_CNT_W-1:0] fifo_cnt;
    logic                  fifo_full, fifo_empty;
    logic [TDATA_W-1:0]    pop_data;
    logic                  pop_last;
    logic                  fifo_pop;

    assign fifo_full  = (fifo_cnt == IN_FIFO_DEPTH[FIFO_CNT_W-1:0]);
    assign fifo_empty = (fifo_cnt == '0);
    assign s_axis_tready = !fifo_full;

    assign pop_data = fifo_data[fifo_rd_ptr];
    assign pop_last = fifo_last[fifo_rd_ptr];

    always_ff @(posedge aclk or negedge aresetn) begin
        if (!aresetn) begin
            fifo_wr_ptr <= '0;
            fifo_rd_ptr <= '0;
            fifo_cnt    <= '0;
        end else begin
            if (s_axis_tvalid && s_axis_tready) begin
                fifo_data[fifo_wr_ptr] <= s_axis_tdata;
                fifo_last[fifo_wr_ptr] <= s_axis_tlast;
                fifo_wr_ptr            <= fifo_wr_ptr + 1'b1;
            end
            if (fifo_pop) begin
                fifo_rd_ptr <= fifo_rd_ptr + 1'b1;
            end
            unique case ({(s_axis_tvalid && s_axis_tready), fifo_pop})
                2'b10: fifo_cnt <= fifo_cnt + 1'b1;
                2'b01: fifo_cnt <= fifo_cnt - 1'b1;
                default: ;
            endcase
        end
    end

    typedef enum logic [1:0] { ST_ASM, ST_RUN, ST_OUT } st_t;
    st_t              st;
    logic [BEAT_W-1:0] beat;

    assign dbg_fsm_state      = st;
    assign dbg_beat           = beat;
    assign dbg_levels_flat    = levels_reg;
    assign dbg_core_start     = core_start;
    assign dbg_core_busy      = core_busy;
    assign dbg_core_out_valid = core_out_valid;
    assign dbg_class_idx      = core_class_idx;
    assign dbg_class_dist     = core_class_dist;

    assign fifo_pop = (st == ST_ASM) && !fifo_empty;

    integer b;
    always_ff @(posedge aclk or negedge aresetn) begin
        if (!aresetn) begin
            st            <= ST_ASM;
            beat          <= '0;
            levels_reg    <= '0;
            core_start    <= 1'b0;
            m_axis_tvalid <= 1'b0;
            m_axis_tdata  <= '0;
            m_axis_tlast  <= 1'b0;
        end else begin
            core_start <= 1'b0;

            case (st)
                ST_ASM: begin
                    if (!fifo_empty) begin
                        for (b = 0; b < TDATA_W; b = b + 1) begin
                            if (beat*TDATA_W + b < LVL_BITS)
                                levels_reg[beat*TDATA_W + b] <= pop_data[b];
                        end
                        if (pop_last || (beat == IN_BEATS-1)) begin
                            beat       <= '0;
                            core_start <= 1'b1;
                            st         <= ST_RUN;
                        end else begin
                            beat <= beat + 1'b1;
                        end
                    end
                end

                ST_RUN: begin
                    if (core_out_valid) begin
                        m_axis_tdata  <= '0;
                        m_axis_tdata[DIST_W-1:0]  <= core_class_dist;
                        m_axis_tdata[16 +: IDX_W] <= core_class_idx;
                        m_axis_tvalid <= 1'b1;
                        m_axis_tlast  <= 1'b1;
                        st            <= ST_OUT;
                    end
                end

                ST_OUT: begin
                    if (m_axis_tvalid && m_axis_tready) begin
                        m_axis_tvalid <= 1'b0;
                        m_axis_tlast  <= 1'b0;
                        st            <= ST_ASM;
                    end
                end

                default: st <= ST_ASM;
            endcase
        end
    end

endmodule
