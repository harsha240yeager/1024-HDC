`timescale 1ns/1ps
//============================================================================
// tb_stream_cosim.sv -- Co-simulation of hdc_stream_wrapper (AXI4-Stream in /
//                       out around hdc_core_top) against the Python golden.
//
// Reuses the end-to-end golden produced by:
//     python python_ref/generate_vectors.py --core
//   core_proto.hex / core_mask.hex / core_levels.hex / core_expect.hex
//   item_mem_*.mem (loaded by the DUT's item_mem ROMs).
//
// Protocol exercised:
//   * prototypes + mask loaded once via the config ports
//   * each window streamed as 3 TDATA beats (TLAST on the final beat) with
//     RANDOM idle gaps between beats (master-side throttling)
//   * the result stream is consumed with RANDOM back-pressure
//     (slave-side m_axis_tready throttling)
//   * every result beat checked: (class_idx << 16) | class_dist
//
// Plusargs: +CASES=<n> (default 200), +VECDIR=<path> (default cosim_core).
// Exit: $finish on full match, $fatal on mismatch.
//============================================================================

module tb_stream_cosim;

    parameter int TDATA_W       = 32;
    parameter int WORDS         = 16;
    parameter int BITS_PER_WORD = 64;
    parameter int N_CH          = 4;
    parameter int N_FEAT        = 5;
    parameter int N_VAL         = 16;
    parameter int N_CLASS       = 8;
    parameter int MAX_CASES     = 2000;
    localparam int D        = WORDS * BITS_PER_WORD;
    localparam int N_PAIRS  = N_CH * N_FEAT;
    localparam int LEVEL_W  = (N_VAL   <= 1) ? 1 : $clog2(N_VAL);
    localparam int IDX_W    = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS);
    localparam int DIST_W   = $clog2(D + 1);
    localparam int LVL_BITS = N_PAIRS * LEVEL_W;
    localparam int IN_BEATS = (LVL_BITS + TDATA_W - 1) / TDATA_W;

    logic               clk, aresetn;
    logic               proto_we;
    logic [IDX_W-1:0]   proto_idx;
    logic [D-1:0]       proto_vec;
    logic               mask_we;
    logic [D-1:0]       mask_vec;
    logic               s_tvalid, s_tready, s_tlast;
    logic [TDATA_W-1:0] s_tdata;
    logic               m_tvalid, m_tready, m_tlast;
    logic [TDATA_W-1:0] m_tdata;

    hdc_stream_wrapper #(
        .TDATA_W(TDATA_W), .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
        .N_CH(N_CH), .N_FEAT(N_FEAT), .N_VAL(N_VAL), .N_CLASS(N_CLASS)
    ) dut (
        .aclk         (clk),
        .aresetn      (aresetn),
        .proto_we     (proto_we),
        .proto_idx    (proto_idx),
        .proto_vec    (proto_vec),
        .mask_we      (mask_we),
        .mask_vec     (mask_vec),
        .s_axis_tvalid(s_tvalid),
        .s_axis_tready(s_tready),
        .s_axis_tdata (s_tdata),
        .s_axis_tlast (s_tlast),
        .m_axis_tvalid(m_tvalid),
        .m_axis_tready(m_tready),
        .m_axis_tdata (m_tdata),
        .m_axis_tlast (m_tlast)
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

    // Random back-pressure on the result stream: ~60% ready duty cycle
    always @(posedge clk) begin
        if (!aresetn) m_tready <= 1'b0;
        else          m_tready <= ($urandom % 10) < 6;
    end

    function automatic logic [D-1:0] assemble_proto(input int kcls);
        logic [D-1:0] v;
        int w;
        begin
            v = '0;
            for (w = 0; w < WORDS; w++)
                v[(w+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = proto_mem[kcls*WORDS + w];
            return v;
        end
    endfunction

    function automatic logic [D-1:0] assemble_mask();
        logic [D-1:0] v;
        int w;
        begin
            v = '0;
            for (w = 0; w < WORDS; w++)
                v[(w+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = mask_mem[w];
            return v;
        end
    endfunction

    task automatic configure_core;
        int kcls;
        begin
            for (kcls = 0; kcls < N_CLASS; kcls++) begin
                proto_idx <= kcls[IDX_W-1:0];
                proto_vec <= assemble_proto(kcls);
                proto_we  <= 1'b1;
                @(posedge clk);
            end
            proto_we <= 1'b0;
            mask_vec <= assemble_mask();
            mask_we  <= 1'b1;
            @(posedge clk);
            mask_we  <= 1'b0;
            @(posedge clk);
        end
    endtask

    // Send one window as IN_BEATS stream beats with random idle gaps
    task automatic send_window(input logic [LVL_BITS-1:0] lv);
        int bt, gap;
        logic [TDATA_W-1:0] beat_data;
        begin
            for (bt = 0; bt < IN_BEATS; bt++) begin
                // random idle gap (0..3 cycles) before offering the beat
                gap = $urandom % 4;
                repeat (gap) @(posedge clk);

                beat_data = '0;
                if (bt == IN_BEATS-1)
                    beat_data[LVL_BITS-1 - (IN_BEATS-1)*TDATA_W : 0]
                        = lv[LVL_BITS-1 : (IN_BEATS-1)*TDATA_W];
                else
                    beat_data = lv[bt*TDATA_W +: TDATA_W];

                s_tdata  <= beat_data;
                s_tlast  <= (bt == IN_BEATS-1);
                s_tvalid <= 1'b1;
                forever begin
                    @(posedge clk);
                    if (s_tready) break;     // beat accepted (tvalid && tready)
                end
                s_tvalid <= 1'b0;
                s_tlast  <= 1'b0;
            end
        end
    endtask

    // Wait for the result beat (handshake = m_tvalid && m_tready) and check it
    task automatic recv_result(input int c);
        logic [IDX_W-1:0]  exp_idx, got_idx;
        logic [DIST_W-1:0] exp_dist, got_dist;
        begin
            forever begin
                @(posedge clk);
                if (m_tvalid && m_tready) break;
            end
            checked++;
            exp_idx  = exp_mem[c][16 +: IDX_W];
            exp_dist = exp_mem[c][DIST_W-1:0];
            got_idx  = m_tdata[16 +: IDX_W];
            got_dist = m_tdata[DIST_W-1:0];
            if ((got_idx !== exp_idx) || (got_dist !== exp_dist) || !m_tlast) begin
                errors++;
                $display("--------------------------------------------------");
                $display("FAIL case %0d  (tlast=%0b)", c, m_tlast);
                $display("  expected idx=%0d dist=%0d", exp_idx, exp_dist);
                $display("  got      idx=%0d dist=%0d", got_idx, got_dist);
                $display("--------------------------------------------------");
            end
        end
    endtask

    initial begin
        errors = 0; checked = 0;
        proto_we = 0; proto_idx = '0; proto_vec = '0;
        mask_we = 0; mask_vec = '0;
        s_tvalid = 0; s_tdata = '0; s_tlast = 0;

        if (!$value$plusargs("CASES=%d", num_cases)) num_cases = 200;
        if (!$value$plusargs("VECDIR=%s", vecdir))   vecdir = "python_ref/vectors/cosim_core";
        if (num_cases > MAX_CASES) num_cases = MAX_CASES;

        $display("==================================================");
        $display("tb_stream_cosim: AXI4-Stream + hdc_core_top vs golden");
        $display("  VECDIR = %s", vecdir);
        $display("  CASES  = %0d   (D=%0d, %0d beats/window, N_CLASS=%0d)",
                 num_cases, D, IN_BEATS, N_CLASS);
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
            fork
                send_window(lvl_mem[c]);
                recv_result(c);
            join
            if ((c % 50) == 49)
                $display("  ... %0d / %0d checked (errors so far: %0d)", c+1, num_cases, errors);
        end

        $display("==================================================");
        if (errors == 0) begin
            $display("PASS: all %0d streamed inferences match the Python golden.", checked);
            $display("==================================================");
            $finish;
        end else begin
            $display("FAIL: %0d / %0d cases mismatched.", errors, checked);
            $display("==================================================");
            $fatal(1, "stream co-simulation mismatch");
        end
    end

endmodule
