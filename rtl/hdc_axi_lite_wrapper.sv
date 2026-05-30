module hdc_axi_lite_wrapper #(
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 12,
    parameter integer WORDS = 16,
    parameter integer BITS_PER_WORD = 64,
    parameter integer D = WORDS * BITS_PER_WORD,
    parameter integer VECTOR_WORDS = D / C_S_AXI_DATA_WIDTH
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

    localparam integer ADDR_LSB = 2;
    localparam integer CONTROL_ADDR = 12'h000;
    localparam integer STATUS_ADDR  = 12'h004;
    localparam integer MODE_ADDR    = 12'h008;
    localparam integer PARAM_ADDR   = 12'h00C;
    localparam integer INPUT_BASE   = 12'h100;
    localparam integer BIND_BASE    = 12'h200;
    localparam integer OUTPUT_BASE  = 12'h300;

    reg [C_S_AXI_ADDR_WIDTH-1:0] awaddr_latched;
    reg [C_S_AXI_ADDR_WIDTH-1:0] araddr_latched;
    reg [D-1:0] input_vec_reg;
    reg [D-1:0] bind_vec_reg;
    reg [D-1:0] output_vec_reg;
    reg [1:0] perm_mode_reg;
    reg [$clog2(D)-1:0] perm_param_reg;
    reg start_pulse;
    reg busy_reg;
    reg done_reg;
    reg core_in_valid;

    wire core_rst_n;
    wire core_in_ready;
    wire core_out_valid;
    wire [D-1:0] core_out_vec_flat;

    integer idx;
    integer bit_idx;
    reg [C_S_AXI_DATA_WIDTH-1:0] read_data_next;
    reg write_fire;
    reg read_fire;
    reg [C_S_AXI_ADDR_WIDTH-1:0] write_addr;

    assign core_rst_n = s_axi_aresetn;

    xor_permute_top #(
        .WORDS(WORDS),
        .BITS_PER_WORD(BITS_PER_WORD),
        .D(D)
    ) u_core (
        .clk(s_axi_aclk),
        .rst_n(core_rst_n),
        .in_valid(core_in_valid),
        .in_ready(core_in_ready),
        .in_vec_flat(input_vec_reg),
        .bind_vec_flat(bind_vec_reg),
        .perm_mode(perm_mode_reg),
        .perm_param(perm_param_reg),
        .out_valid(core_out_valid),
        .out_ready(1'b1),
        .out_vec_flat(core_out_vec_flat)
    );

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            s_axi_awready   <= 1'b0;
            s_axi_wready    <= 1'b0;
            s_axi_bvalid    <= 1'b0;
            s_axi_bresp     <= 2'b00;
            s_axi_arready   <= 1'b0;
            s_axi_rvalid    <= 1'b0;
            s_axi_rresp     <= 2'b00;
            s_axi_rdata     <= {C_S_AXI_DATA_WIDTH{1'b0}};
            awaddr_latched  <= {C_S_AXI_ADDR_WIDTH{1'b0}};
            araddr_latched  <= {C_S_AXI_ADDR_WIDTH{1'b0}};
            input_vec_reg   <= {D{1'b0}};
            bind_vec_reg    <= {D{1'b0}};
            output_vec_reg  <= {D{1'b0}};
            perm_mode_reg   <= 2'b00;
            perm_param_reg  <= {$clog2(D){1'b0}};
            start_pulse     <= 1'b0;
            busy_reg        <= 1'b0;
            done_reg        <= 1'b0;
            core_in_valid   <= 1'b0;
        end else begin
            start_pulse   <= 1'b0;
            core_in_valid <= 1'b0;

            if (!s_axi_awready && s_axi_awvalid && s_axi_wvalid) begin
                s_axi_awready  <= 1'b1;
                s_axi_wready   <= 1'b1;
                awaddr_latched <= s_axi_awaddr;
            end else begin
                s_axi_awready <= 1'b0;
                s_axi_wready  <= 1'b0;
            end

            write_fire = (!s_axi_bvalid && s_axi_awready && s_axi_awvalid && s_axi_wready && s_axi_wvalid);
            write_addr = awaddr_latched;
            if (write_fire) begin
                s_axi_bvalid <= 1'b1;
                s_axi_bresp  <= 2'b00;

                case (write_addr)
                    CONTROL_ADDR: begin
                        if (s_axi_wstrb[0]) begin
                            if (s_axi_wdata[0] && !busy_reg && core_in_ready) begin
                                start_pulse   <= 1'b1;
                                core_in_valid <= 1'b1;
                                busy_reg      <= 1'b1;
                                done_reg      <= 1'b0;
                            end
                            if (s_axi_wdata[2]) begin
                                done_reg <= 1'b0;
                            end
                        end
                    end
                    MODE_ADDR: begin
                        if (s_axi_wstrb[0]) begin
                            perm_mode_reg <= s_axi_wdata[1:0];
                        end
                    end
                    PARAM_ADDR: begin
                        for (idx = 0; idx < C_S_AXI_DATA_WIDTH/8; idx = idx + 1) begin
                            if (s_axi_wstrb[idx]) begin
                                perm_param_reg[idx*8 +: 8] <= s_axi_wdata[idx*8 +: 8];
                            end
                        end
                    end
                    default: begin
                        if ((write_addr >= INPUT_BASE) && (write_addr < (INPUT_BASE + VECTOR_WORDS*4))) begin
                            bit_idx = ((write_addr - INPUT_BASE) >> ADDR_LSB) * C_S_AXI_DATA_WIDTH;
                            for (idx = 0; idx < C_S_AXI_DATA_WIDTH/8; idx = idx + 1) begin
                                if (s_axi_wstrb[idx]) begin
                                    input_vec_reg[bit_idx + idx*8 +: 8] <= s_axi_wdata[idx*8 +: 8];
                                end
                            end
                        end else if ((write_addr >= BIND_BASE) && (write_addr < (BIND_BASE + VECTOR_WORDS*4))) begin
                            bit_idx = ((write_addr - BIND_BASE) >> ADDR_LSB) * C_S_AXI_DATA_WIDTH;
                            for (idx = 0; idx < C_S_AXI_DATA_WIDTH/8; idx = idx + 1) begin
                                if (s_axi_wstrb[idx]) begin
                                    bind_vec_reg[bit_idx + idx*8 +: 8] <= s_axi_wdata[idx*8 +: 8];
                                end
                            end
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
                read_data_next = {C_S_AXI_DATA_WIDTH{1'b0}};

                case (araddr_latched)
                    CONTROL_ADDR: begin
                        read_data_next[0] = busy_reg;
                        read_data_next[1] = core_in_ready;
                        read_data_next[2] = done_reg;
                    end
                    STATUS_ADDR: begin
                        read_data_next[0] = done_reg;
                        read_data_next[1] = busy_reg;
                        read_data_next[2] = core_in_ready;
                        read_data_next[3] = core_out_valid;
                    end
                    MODE_ADDR: begin
                        read_data_next[1:0] = perm_mode_reg;
                    end
                    PARAM_ADDR: begin
                        read_data_next[$clog2(D)-1:0] = perm_param_reg;
                    end
                    default: begin
                        if ((araddr_latched >= INPUT_BASE) && (araddr_latched < (INPUT_BASE + VECTOR_WORDS*4))) begin
                            bit_idx = ((araddr_latched - INPUT_BASE) >> ADDR_LSB) * C_S_AXI_DATA_WIDTH;
                            read_data_next = input_vec_reg[bit_idx +: C_S_AXI_DATA_WIDTH];
                        end else if ((araddr_latched >= BIND_BASE) && (araddr_latched < (BIND_BASE + VECTOR_WORDS*4))) begin
                            bit_idx = ((araddr_latched - BIND_BASE) >> ADDR_LSB) * C_S_AXI_DATA_WIDTH;
                            read_data_next = bind_vec_reg[bit_idx +: C_S_AXI_DATA_WIDTH];
                        end else if ((araddr_latched >= OUTPUT_BASE) && (araddr_latched < (OUTPUT_BASE + VECTOR_WORDS*4))) begin
                            bit_idx = ((araddr_latched - OUTPUT_BASE) >> ADDR_LSB) * C_S_AXI_DATA_WIDTH;
                            read_data_next = output_vec_reg[bit_idx +: C_S_AXI_DATA_WIDTH];
                        end
                    end
                endcase

                s_axi_rvalid <= 1'b1;
                s_axi_rresp  <= 2'b00;
                s_axi_rdata  <= read_data_next;
            end else if (s_axi_rvalid && s_axi_rready) begin
                s_axi_rvalid <= 1'b0;
            end

            if (busy_reg && core_out_valid) begin
                output_vec_reg <= core_out_vec_flat;
                busy_reg       <= 1'b0;
                done_reg       <= 1'b1;
            end
        end
    end

endmodule
