// hdc_core_axi_lite.sv
// AXI4-Lite slave wrapper exposing the end-to-end HDC inference core
// (hdc_core_top) to the Zynq PS.
//
// Programming model (byte offsets, 32-bit registers):
//   0x000 CTRL   (W)  bit0 START      pulse: classify LEVELS with loaded config
//                     bit1 LOAD_PROTO pulse: STAGING -> prototype[PROTO_IDX]
//                     bit2 LOAD_MASK  pulse: STAGING -> pruning mask
//                     bit3 CLR_DONE   pulse: clear sticky DONE
//   0x004 STATUS (R)  bit0 BUSY, bit1 DONE (sticky)
//   0x008 PROTO_IDX (RW) class index targeted by LOAD_PROTO
//   0x00C RESULT (R)  (class_idx << 16) | class_dist ; bit31 = DONE
//   0x010 LEVELS0 (RW) levels_flat[31:0]
//   0x014 LEVELS1 (RW) levels_flat[63:32]
//   0x018 LEVELS2 (RW) levels_flat[79:64]   (low 16 bits used)
//   0x100..0x17C STAGING (RW) 32 words = one 1024-bit hypervector, word w =
//                     bits [w*32 +: 32].  Fill it then pulse LOAD_PROTO/LOAD_MASK.
//
// Typical sequence: for k in classes { fill STAGING; PROTO_IDX=k; LOAD_PROTO }
//                   fill STAGING; LOAD_MASK
//                   per window: write LEVELS0..2; START; poll STATUS.DONE;
//                               read RESULT; CLR_DONE.

module hdc_core_axi_lite #(
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 12,
    parameter integer WORDS              = 16,
    parameter integer BITS_PER_WORD      = 64,
    parameter integer N_CH               = 4,
    parameter integer N_FEAT             = 5,
    parameter integer N_VAL              = 16,
    parameter integer N_CLASS            = 8,
    parameter integer CNT_W              = 6,
    parameter integer D                  = WORDS * BITS_PER_WORD,
    parameter integer N_PAIRS            = N_CH * N_FEAT,
    parameter integer LEVEL_W            = (N_VAL   <= 1) ? 1 : $clog2(N_VAL),
    parameter integer IDX_W              = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS),
    parameter integer DIST_W             = $clog2(D + 1),
    parameter integer LVL_BITS           = N_PAIRS * LEVEL_W,
    parameter integer VEC_WORDS          = D / C_S_AXI_DATA_WIDTH
) (
    input  wire                                s_axi_aclk,
    input  wire                                s_axi_aresetn,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0]       s_axi_awaddr,
    input  wire                                s_axi_awvalid,
    output reg                                 s_axi_awready,
    input  wire [C_S_AXI_DATA_WIDTH-1:0]       s_axi_wdata,
    input  wire [(C_S_AXI_DATA_WIDTH/8)-1:0]   s_axi_wstrb,
    input  wire                                s_axi_wvalid,
    output reg                                 s_axi_wready,
    output reg  [1:0]                          s_axi_bresp,
    output reg                                 s_axi_bvalid,
    input  wire                                s_axi_bready,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0]       s_axi_araddr,
    input  wire                                s_axi_arvalid,
    output reg                                 s_axi_arready,
    output reg  [C_S_AXI_DATA_WIDTH-1:0]       s_axi_rdata,
    output reg  [1:0]                          s_axi_rresp,
    output reg                                 s_axi_rvalid,
    input  wire                                s_axi_rready
);

    localparam integer ADDR_LSB    = 2;
    localparam [11:0]  CTRL_ADDR   = 12'h000;
    localparam [11:0]  STATUS_ADDR = 12'h004;
    localparam [11:0]  PIDX_ADDR   = 12'h008;
    localparam [11:0]  RESULT_ADDR = 12'h00C;
    localparam [11:0]  LVL0_ADDR   = 12'h010;
    localparam [11:0]  LVL1_ADDR   = 12'h014;
    localparam [11:0]  LVL2_ADDR   = 12'h018;
    localparam [11:0]  STAGE_BASE  = 12'h100;

    // -------------------------------------------------------------------
    // Software-visible state
    // -------------------------------------------------------------------
    reg [D-1:0]        staging_vec;
    reg [IDX_W-1:0]    proto_idx_reg;
    reg [LVL_BITS-1:0] levels_reg;
    reg                busy_reg;
    reg                done_reg;
    reg [IDX_W-1:0]    result_idx;
    reg [DIST_W-1:0]   result_dist;

    // Core handshake pulses (one cycle each)
    reg                core_start;
    reg                core_proto_we;
    reg                core_mask_we;

    wire               core_busy;
    wire               core_out_valid;
    wire [IDX_W-1:0]   core_class_idx;
    wire [DIST_W-1:0]  core_class_dist;

    hdc_core_top #(
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
        .N_CH(N_CH), .N_FEAT(N_FEAT), .N_VAL(N_VAL),
        .N_CLASS(N_CLASS), .CNT_W(CNT_W)
    ) u_core (
        .clk        (s_axi_aclk),
        .rst_n      (s_axi_aresetn),
        .proto_we   (core_proto_we),
        .proto_idx  (proto_idx_reg),
        .proto_vec  (staging_vec),
        .mask_we    (core_mask_we),
        .mask_vec   (staging_vec),
        .start      (core_start),
        .levels_flat(levels_reg),
        .busy       (core_busy),
        .out_valid  (core_out_valid),
        .class_idx  (core_class_idx),
        .class_dist (core_class_dist)
    );

    // -------------------------------------------------------------------
    // Helpers for AXI transaction sequencing
    // -------------------------------------------------------------------
    reg [C_S_AXI_ADDR_WIDTH-1:0] awaddr_latched;
    reg [C_S_AXI_ADDR_WIDTH-1:0] araddr_latched;
    reg                          write_fire;
    reg                          read_fire;
    reg [C_S_AXI_ADDR_WIDTH-1:0] waddr;
    reg [C_S_AXI_DATA_WIDTH-1:0] rdata_next;
    integer                      bidx;
    integer                      sw;       // staging word index
    integer                      bb;

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            s_axi_awready  <= 1'b0;
            s_axi_wready   <= 1'b0;
            s_axi_bvalid   <= 1'b0;
            s_axi_bresp    <= 2'b00;
            s_axi_arready  <= 1'b0;
            s_axi_rvalid   <= 1'b0;
            s_axi_rresp    <= 2'b00;
            s_axi_rdata    <= {C_S_AXI_DATA_WIDTH{1'b0}};
            awaddr_latched <= {C_S_AXI_ADDR_WIDTH{1'b0}};
            araddr_latched <= {C_S_AXI_ADDR_WIDTH{1'b0}};
            staging_vec    <= {D{1'b0}};
            proto_idx_reg  <= {IDX_W{1'b0}};
            levels_reg     <= {LVL_BITS{1'b0}};
            busy_reg       <= 1'b0;
            done_reg       <= 1'b0;
            result_idx     <= {IDX_W{1'b0}};
            result_dist    <= {DIST_W{1'b0}};
            core_start     <= 1'b0;
            core_proto_we  <= 1'b0;
            core_mask_we   <= 1'b0;
        end else begin
            // Default: deassert one-cycle core pulses every clock
            core_start    <= 1'b0;
            core_proto_we <= 1'b0;
            core_mask_we  <= 1'b0;

            // ---------------- Write address/data handshake -------------
            if (!s_axi_awready && s_axi_awvalid && s_axi_wvalid) begin
                s_axi_awready  <= 1'b1;
                s_axi_wready   <= 1'b1;
                awaddr_latched <= s_axi_awaddr;
            end else begin
                s_axi_awready <= 1'b0;
                s_axi_wready  <= 1'b0;
            end

            write_fire = (!s_axi_bvalid && s_axi_awready && s_axi_awvalid &&
                          s_axi_wready  && s_axi_wvalid);
            waddr = awaddr_latched;

            if (write_fire) begin
                s_axi_bvalid <= 1'b1;
                s_axi_bresp  <= 2'b00;

                case (waddr[11:0])
                    CTRL_ADDR: begin
                        if (s_axi_wstrb[0]) begin
                            if (s_axi_wdata[0] && !busy_reg) begin   // START
                                core_start <= 1'b1;
                                busy_reg   <= 1'b1;
                                done_reg   <= 1'b0;
                            end
                            if (s_axi_wdata[1]) core_proto_we <= 1'b1; // LOAD_PROTO
                            if (s_axi_wdata[2]) core_mask_we  <= 1'b1; // LOAD_MASK
                            if (s_axi_wdata[3]) done_reg      <= 1'b0; // CLR_DONE
                        end
                    end
                    PIDX_ADDR: begin
                        if (s_axi_wstrb[0]) proto_idx_reg <= s_axi_wdata[IDX_W-1:0];
                    end
                    LVL0_ADDR: begin
                        for (bb = 0; bb < C_S_AXI_DATA_WIDTH/8; bb = bb + 1)
                            if (s_axi_wstrb[bb]) levels_reg[bb*8 +: 8] <= s_axi_wdata[bb*8 +: 8];
                    end
                    LVL1_ADDR: begin
                        for (bb = 0; bb < C_S_AXI_DATA_WIDTH/8; bb = bb + 1)
                            if (s_axi_wstrb[bb]) levels_reg[32 + bb*8 +: 8] <= s_axi_wdata[bb*8 +: 8];
                    end
                    LVL2_ADDR: begin
                        for (bb = 0; bb < C_S_AXI_DATA_WIDTH/8; bb = bb + 1)
                            if (s_axi_wstrb[bb] && (64 + bb*8 < LVL_BITS))
                                levels_reg[64 + bb*8 +: 8] <= s_axi_wdata[bb*8 +: 8];
                    end
                    default: begin
                        if ((waddr[11:0] >= STAGE_BASE) &&
                            (waddr[11:0] <  STAGE_BASE + VEC_WORDS*4)) begin
                            sw   = (waddr[11:0] - STAGE_BASE) >> ADDR_LSB;
                            bidx = sw * C_S_AXI_DATA_WIDTH;
                            for (bb = 0; bb < C_S_AXI_DATA_WIDTH/8; bb = bb + 1)
                                if (s_axi_wstrb[bb])
                                    staging_vec[bidx + bb*8 +: 8] <= s_axi_wdata[bb*8 +: 8];
                        end
                    end
                endcase
            end else if (s_axi_bvalid && s_axi_bready) begin
                s_axi_bvalid <= 1'b0;
            end

            // ---------------- Read address handshake -------------------
            if (!s_axi_arready && s_axi_arvalid && !s_axi_rvalid) begin
                s_axi_arready  <= 1'b1;
                araddr_latched <= s_axi_araddr;
            end else begin
                s_axi_arready <= 1'b0;
            end

            read_fire = (!s_axi_rvalid && s_axi_arready && s_axi_arvalid);
            if (read_fire) begin
                rdata_next = {C_S_AXI_DATA_WIDTH{1'b0}};
                case (araddr_latched[11:0])
                    CTRL_ADDR:   rdata_next = {30'b0, done_reg, busy_reg};
                    STATUS_ADDR: rdata_next = {30'b0, done_reg, busy_reg};
                    PIDX_ADDR:   rdata_next[IDX_W-1:0] = proto_idx_reg;
                    RESULT_ADDR: begin
                        rdata_next[DIST_W-1:0] = result_dist;
                        rdata_next[16 +: IDX_W] = result_idx;
                        rdata_next[31]          = done_reg;
                    end
                    LVL0_ADDR:   rdata_next = levels_reg[31:0];
                    LVL1_ADDR:   rdata_next = levels_reg[63:32];
                    LVL2_ADDR:   rdata_next[LVL_BITS-65:0] = levels_reg[LVL_BITS-1:64];
                    default: begin
                        if ((araddr_latched[11:0] >= STAGE_BASE) &&
                            (araddr_latched[11:0] <  STAGE_BASE + VEC_WORDS*4)) begin
                            sw         = (araddr_latched[11:0] - STAGE_BASE) >> ADDR_LSB;
                            rdata_next = staging_vec[sw*C_S_AXI_DATA_WIDTH +: C_S_AXI_DATA_WIDTH];
                        end
                    end
                endcase
                s_axi_rvalid <= 1'b1;
                s_axi_rresp  <= 2'b00;
                s_axi_rdata  <= rdata_next;
            end else if (s_axi_rvalid && s_axi_rready) begin
                s_axi_rvalid <= 1'b0;
            end

            // ---------------- Capture core result ----------------------
            if (busy_reg && core_out_valid) begin
                result_idx  <= core_class_idx;
                result_dist <= core_class_dist;
                busy_reg    <= 1'b0;
                done_reg    <= 1'b1;
            end
        end
    end

endmodule
