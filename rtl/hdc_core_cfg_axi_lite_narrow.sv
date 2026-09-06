// hdc_core_cfg_axi_lite_narrow.sv
// AXI4-Lite config for narrow stream path: pre-gathered K_BITS prototypes only.
// LOAD_MASK is ignored (mask baked in hdc_sel_pkg).

module hdc_core_cfg_axi_lite_narrow #(
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 12,
    parameter integer K_BITS             = hdc_sel_pkg::K_BITS,
    parameter integer N_CLASS            = 8,
    parameter integer IDX_W              = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS),
    parameter integer VEC_WORDS          = (K_BITS + C_S_AXI_DATA_WIDTH - 1) / C_S_AXI_DATA_WIDTH
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
    input  wire                                s_axi_rready,

    output reg                                 cfg_proto_we,
    output reg  [IDX_W-1:0]                    cfg_proto_idx,
    output reg  [K_BITS-1:0]                   cfg_proto_vec
);

    localparam integer ADDR_LSB    = 2;
    localparam [11:0]  CTRL_ADDR   = 12'h000;
    localparam [11:0]  STATUS_ADDR = 12'h004;
    localparam [11:0]  PIDX_ADDR   = 12'h008;
    localparam [11:0]  STAGE_BASE  = 12'h100;

    reg [K_BITS-1:0]    staging_vec;
    reg [IDX_W-1:0]     proto_idx_reg;

    reg [C_S_AXI_ADDR_WIDTH-1:0] awaddr_latched;
    reg [C_S_AXI_ADDR_WIDTH-1:0] araddr_latched;
    reg                          write_fire;
    reg                          read_fire;
    reg [C_S_AXI_ADDR_WIDTH-1:0] waddr;
    reg [C_S_AXI_DATA_WIDTH-1:0] rdata_next;
    integer                      bidx;
    integer                      sw;
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
            staging_vec    <= {K_BITS{1'b0}};
            proto_idx_reg  <= {IDX_W{1'b0}};
            cfg_proto_we   <= 1'b0;
            cfg_proto_idx  <= {IDX_W{1'b0}};
            cfg_proto_vec  <= {K_BITS{1'b0}};
        end else begin
            cfg_proto_we <= 1'b0;

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
                        if (s_axi_wstrb[0] && s_axi_wdata[1]) begin
                            cfg_proto_we  <= 1'b1;
                            cfg_proto_idx <= proto_idx_reg;
                            cfg_proto_vec <= staging_vec;
                        end
                    end
                    PIDX_ADDR: begin
                        if (s_axi_wstrb[0]) proto_idx_reg <= s_axi_wdata[IDX_W-1:0];
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
                    CTRL_ADDR,
                    STATUS_ADDR: rdata_next = 32'h0;
                    PIDX_ADDR:   rdata_next[IDX_W-1:0] = proto_idx_reg;
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
        end
    end

endmodule
