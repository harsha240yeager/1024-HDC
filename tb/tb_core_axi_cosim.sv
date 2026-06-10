`timescale 1ns/1ps
//============================================================================
// tb_core_axi_cosim.sv -- Co-simulation of hdc_core_axi_lite (AXI4-Lite slave
//                         wrapping hdc_core_top) against the Python golden.
//
// A small AXI4-Lite master model drives the real register-map programming
// sequence used on the Zynq PS:
//   1. for each class: fill STAGING (32 words), set PROTO_IDX, pulse LOAD_PROTO
//   2. fill STAGING with the mask, pulse LOAD_MASK
//   3. per window: write LEVELS0..2, pulse START, poll STATUS.DONE, read RESULT
//
// Golden files (same as the core co-sim): python generate_vectors.py --core
//   core_proto.hex / core_mask.hex / core_levels.hex / core_expect.hex
//   item_mem_*.mem (loaded by the DUT's item_mem ROMs).
//
// Plusargs: +CASES=<n> (default 200), +VECDIR=<path> (default cosim_core).
// Exit: $finish on full match, $fatal on mismatch.
//============================================================================

module tb_core_axi_cosim;

    parameter int WORDS         = 16;
    parameter int BITS_PER_WORD = 64;
    parameter int N_CH          = 4;
    parameter int N_FEAT        = 5;
    parameter int N_VAL         = 16;
    parameter int N_CLASS       = 8;
    parameter int ADDRW         = 12;
    parameter int MAX_CASES     = 2000;
    localparam int D        = WORDS * BITS_PER_WORD;
    localparam int N_PAIRS  = N_CH * N_FEAT;
    localparam int LEVEL_W  = (N_VAL   <= 1) ? 1 : $clog2(N_VAL);
    localparam int IDX_W    = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS);
    localparam int DIST_W   = $clog2(D + 1);
    localparam int LVL_BITS = N_PAIRS * LEVEL_W;
    localparam int VEC_WORDS = D / 32;

    // Register offsets (mirror the wrapper)
    localparam [11:0] CTRL_ADDR   = 12'h000;
    localparam [11:0] STATUS_ADDR = 12'h004;
    localparam [11:0] PIDX_ADDR   = 12'h008;
    localparam [11:0] RESULT_ADDR = 12'h00C;
    localparam [11:0] LVL0_ADDR   = 12'h010;
    localparam [11:0] LVL1_ADDR   = 12'h014;
    localparam [11:0] LVL2_ADDR   = 12'h018;
    localparam [11:0] STAGE_BASE  = 12'h100;
    // CTRL bits
    localparam [31:0] C_START      = 32'h1;
    localparam [31:0] C_LOAD_PROTO = 32'h2;
    localparam [31:0] C_LOAD_MASK  = 32'h4;
    localparam [31:0] C_CLR_DONE   = 32'h8;

    logic                  clk, aresetn;
    logic [ADDRW-1:0]      awaddr;
    logic                  awvalid, awready;
    logic [31:0]           wdata;
    logic [3:0]            wstrb;
    logic                  wvalid, wready;
    logic [1:0]            bresp;
    logic                  bvalid, bready;
    logic [ADDRW-1:0]      araddr;
    logic                  arvalid, arready;
    logic [31:0]           rdata;
    logic [1:0]            rresp;
    logic                  rvalid, rready;

    hdc_core_axi_lite #(
        .C_S_AXI_ADDR_WIDTH(ADDRW),
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
        .N_CH(N_CH), .N_FEAT(N_FEAT), .N_VAL(N_VAL), .N_CLASS(N_CLASS)
    ) dut (
        .s_axi_aclk   (clk),
        .s_axi_aresetn(aresetn),
        .s_axi_awaddr (awaddr),
        .s_axi_awvalid(awvalid),
        .s_axi_awready(awready),
        .s_axi_wdata  (wdata),
        .s_axi_wstrb  (wstrb),
        .s_axi_wvalid (wvalid),
        .s_axi_wready (wready),
        .s_axi_bresp  (bresp),
        .s_axi_bvalid (bvalid),
        .s_axi_bready (bready),
        .s_axi_araddr (araddr),
        .s_axi_arvalid(arvalid),
        .s_axi_arready(arready),
        .s_axi_rdata  (rdata),
        .s_axi_rresp  (rresp),
        .s_axi_rvalid (rvalid),
        .s_axi_rready (rready)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Golden memories
    logic [BITS_PER_WORD-1:0] proto_mem [0:N_CLASS*WORDS-1];
    logic [BITS_PER_WORD-1:0] mask_mem  [0:WORDS-1];
    logic [LVL_BITS-1:0]      lvl_mem   [0:MAX_CASES-1];
    logic [31:0]              exp_mem   [0:MAX_CASES-1];

    int    num_cases, errors, checked;
    string vecdir;

    // --------------------------------------------------------------
    // AXI4-Lite master tasks
    // --------------------------------------------------------------
    task automatic axi_write(input [ADDRW-1:0] addr, input [31:0] data);
        begin
            @(posedge clk);
            awaddr  <= addr; awvalid <= 1'b1;
            wdata   <= data; wstrb   <= 4'hF; wvalid <= 1'b1;
            forever begin
                @(posedge clk);
                if (awready && wready) break;
            end
            awvalid <= 1'b0; wvalid <= 1'b0;
            bready  <= 1'b1;
            forever begin
                @(posedge clk);
                if (bvalid) break;
            end
            bready <= 1'b0;
        end
    endtask

    task automatic axi_read(input [ADDRW-1:0] addr, output [31:0] data);
        begin
            @(posedge clk);
            araddr <= addr; arvalid <= 1'b1;
            forever begin
                @(posedge clk);
                if (arready) break;
            end
            arvalid <= 1'b0;
            rready  <= 1'b1;
            forever begin
                @(posedge clk);
                if (rvalid) begin data = rdata; break; end
            end
            rready <= 1'b0;
        end
    endtask

    // 32-bit AXI word w of a 1024-bit vector held as 64-bit golden words
    function automatic logic [31:0] proto32(input int kcls, input int w);
        logic [BITS_PER_WORD-1:0] w64;
        begin
            w64 = proto_mem[kcls*WORDS + (w >> 1)];
            return (w[0]) ? w64[63:32] : w64[31:0];
        end
    endfunction

    function automatic logic [31:0] mask32(input int w);
        logic [BITS_PER_WORD-1:0] w64;
        begin
            w64 = mask_mem[w >> 1];
            return (w[0]) ? w64[63:32] : w64[31:0];
        end
    endfunction

    task automatic load_staging_proto(input int kcls);
        int w;
        begin
            for (w = 0; w < VEC_WORDS; w++)
                axi_write(STAGE_BASE + w*4, proto32(kcls, w));
        end
    endtask

    task automatic load_staging_mask;
        int w;
        begin
            for (w = 0; w < VEC_WORDS; w++)
                axi_write(STAGE_BASE + w*4, mask32(w));
        end
    endtask

    task automatic configure_core;
        int kcls;
        begin
            for (kcls = 0; kcls < N_CLASS; kcls++) begin
                load_staging_proto(kcls);
                axi_write(PIDX_ADDR, kcls);
                axi_write(CTRL_ADDR, C_LOAD_PROTO);
            end
            load_staging_mask();
            axi_write(CTRL_ADDR, C_LOAD_MASK);
        end
    endtask

    task automatic run_case(input int c);
        logic [LVL_BITS-1:0] lv;
        logic [31:0]         st, res;
        logic [IDX_W-1:0]    exp_idx, got_idx;
        logic [DIST_W-1:0]   exp_dist, got_dist;
        int                  guard;
        begin
            lv = lvl_mem[c];
            axi_write(LVL0_ADDR, lv[31:0]);
            axi_write(LVL1_ADDR, lv[63:32]);
            axi_write(LVL2_ADDR, {16'b0, lv[79:64]});
            axi_write(CTRL_ADDR, C_START);

            guard = 0;
            st    = 0;
            do begin
                axi_read(STATUS_ADDR, st);
                guard++;
            end while (!st[1] && guard < 1000);   // STATUS bit1 = DONE

            axi_read(RESULT_ADDR, res);
            axi_write(CTRL_ADDR, C_CLR_DONE);

            checked++;
            exp_idx  = exp_mem[c][16 +: IDX_W];
            exp_dist = exp_mem[c][DIST_W-1:0];
            got_idx  = res[16 +: IDX_W];
            got_dist = res[DIST_W-1:0];
            if ((got_idx !== exp_idx) || (got_dist !== exp_dist) || !st[1]) begin
                errors++;
                $display("--------------------------------------------------");
                $display("FAIL case %0d  (done=%0b after %0d polls)", c, st[1], guard);
                $display("  expected idx=%0d dist=%0d", exp_idx, exp_dist);
                $display("  got      idx=%0d dist=%0d", got_idx, got_dist);
                $display("--------------------------------------------------");
            end
        end
    endtask

    initial begin
        errors = 0; checked = 0;
        awvalid = 0; wvalid = 0; bready = 0; arvalid = 0; rready = 0;
        awaddr = 0; wdata = 0; wstrb = 0; araddr = 0;

        if (!$value$plusargs("CASES=%d", num_cases)) num_cases = 200;
        if (!$value$plusargs("VECDIR=%s", vecdir))   vecdir = "python_ref/vectors/cosim_core";
        if (num_cases > MAX_CASES) num_cases = MAX_CASES;

        $display("==================================================");
        $display("tb_core_axi_cosim: AXI4-Lite + hdc_core_top vs golden");
        $display("  VECDIR = %s", vecdir);
        $display("  CASES  = %0d   (D=%0d, N_CLASS=%0d)", num_cases, D, N_CLASS);
        $display("==================================================");

        $readmemh($sformatf("%s/core_proto.hex",  vecdir), proto_mem);
        $readmemh($sformatf("%s/core_mask.hex",   vecdir), mask_mem);
        $readmemh($sformatf("%s/core_levels.hex", vecdir), lvl_mem);
        $readmemh($sformatf("%s/core_expect.hex", vecdir), exp_mem);

        aresetn <= 1'b0;
        repeat (8) @(posedge clk);
        aresetn <= 1'b1;
        repeat (2) @(posedge clk);

        configure_core();

        for (int c = 0; c < num_cases; c++) begin
            run_case(c);
            if ((c % 50) == 49)
                $display("  ... %0d / %0d checked (errors so far: %0d)", c+1, num_cases, errors);
        end

        $display("==================================================");
        if (errors == 0) begin
            $display("PASS: all %0d AXI-driven inferences match the Python golden.", checked);
            $display("==================================================");
            $finish;
        end else begin
            $display("FAIL: %0d / %0d cases mismatched.", errors, checked);
            $display("==================================================");
            $fatal(1, "AXI core co-simulation mismatch");
        end
    end

endmodule
