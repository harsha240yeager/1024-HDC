`timescale 1ns/1ps
//============================================================================
// tb_core_narrow_cosim.sv -- Automated co-simulation of hdc_core_top_narrow
//                            (encoder -> baked gather -> popcount_am_narrow)
//                            against the Python narrow-core golden.
//
// Reads flat $readmemh vector files produced by:
//     python python_ref/generate_vectors.py --narrow-core
//
//   core_proto_narrow.hex  N_CLASS*K_WORDS words  (pre-gathered prototypes)
//   core_levels.hex        NUM_CASES words        (packed level grid per case)
//   core_expect.hex        NUM_CASES words        ((best_idx<<16)|best_dist)
//   item_mem_*.mem         loaded by encoder ROMs
//
// Plusargs:
//   +CASES=<n>     number of cases to run    (default 500)
//   +VECDIR=<path> directory holding the hex (default python_ref/vectors/cosim_core_narrow)
//
// Exit: $finish on full match, $fatal on any mismatch (non-zero sim exit).
//============================================================================

module tb_core_narrow_cosim;

    import hdc_sel_pkg::*;

    parameter int WORDS         = 16;
    parameter int BITS_PER_WORD = 64;
    parameter int N_CH          = 4;
    parameter int N_FEAT        = 5;
    parameter int N_VAL         = 16;
    parameter int N_CLASS       = 8;
    parameter int CNT_W         = 6;
    parameter int MAX_CASES     = 2000;
    parameter     CH_MEM        = "python_ref/vectors/cosim_core_narrow/item_mem_channel.mem";
    parameter     FT_MEM        = "python_ref/vectors/cosim_core_narrow/item_mem_feature.mem";
    parameter     VAL_MEM       = "python_ref/vectors/cosim_core_narrow/item_mem_value.mem";

    localparam int D        = WORDS * BITS_PER_WORD;
    localparam int K_BITS_L = K_BITS;
    localparam int K_WORDS_L = K_WORDS;
    localparam int N_PAIRS  = N_CH * N_FEAT;
    localparam int LEVEL_W  = (N_VAL   <= 1) ? 1 : $clog2(N_VAL);
    localparam int IDX_W    = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS);
    localparam int DIST_W   = $clog2(K_BITS_L + 1);
    localparam int LVL_BITS = N_PAIRS * LEVEL_W;

    logic                     clk, rst_n;
    logic                     proto_we;
    logic [IDX_W-1:0]         proto_idx;
    logic [K_BITS_L-1:0]      proto_vec;
    logic                     start;
    logic [LVL_BITS-1:0]      levels_flat;
    logic                     busy;
    logic                     out_valid;
    logic [IDX_W-1:0]         class_idx;
    logic [DIST_W-1:0]        class_dist;

    hdc_core_top_narrow #(
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
        .N_CH(N_CH), .N_FEAT(N_FEAT), .N_VAL(N_VAL),
        .N_CLASS(N_CLASS), .CNT_W(CNT_W),
        .CH_MEM(CH_MEM), .FT_MEM(FT_MEM), .VAL_MEM(VAL_MEM)
    ) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .proto_we   (proto_we),
        .proto_idx  (proto_idx),
        .proto_vec  (proto_vec),
        .start      (start),
        .levels_flat(levels_flat),
        .busy       (busy),
        .out_valid  (out_valid),
        .class_idx  (class_idx),
        .class_dist (class_dist)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    logic [BITS_PER_WORD-1:0] proto_mem [0:N_CLASS*K_WORDS_L-1];
    logic [LVL_BITS-1:0]      lvl_mem   [0:MAX_CASES-1];
    logic [31:0]              exp_mem   [0:MAX_CASES-1];

    int    num_cases;
    string vecdir;
    int    errors;
    int    checked;

    function automatic logic [K_BITS_L-1:0] assemble_proto_narrow(input int kcls);
        logic [K_BITS_L-1:0] v;
        int w;
        begin
            v = '0;
            for (w = 0; w < K_WORDS_L; w++)
                v[(w+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = proto_mem[kcls*K_WORDS_L + w];
            return v;
        end
    endfunction

    task automatic apply_reset;
        begin
            rst_n       <= 1'b0;
            proto_we    <= 1'b0;
            proto_idx   <= '0;
            proto_vec   <= '0;
            start       <= 1'b0;
            levels_flat <= '0;
            repeat (5) @(posedge clk);
            rst_n <= 1'b1;
            repeat (2) @(posedge clk);
        end
    endtask

    task automatic configure_core;
        int kcls;
        begin
            for (kcls = 0; kcls < N_CLASS; kcls++) begin
                proto_idx <= kcls[IDX_W-1:0];
                proto_vec <= assemble_proto_narrow(kcls);
                proto_we  <= 1'b1;
                @(posedge clk);
            end
            proto_we <= 1'b0;
            @(posedge clk);
        end
    endtask

    task automatic run_case(input int c);
        logic [IDX_W-1:0]  exp_idx;
        logic [DIST_W-1:0] exp_dist;
        begin
            levels_flat <= lvl_mem[c];
            start       <= 1'b1;
            @(posedge clk);
            start       <= 1'b0;
            while (!out_valid) @(posedge clk);

            checked++;
            exp_idx  = exp_mem[c][16 +: IDX_W];
            exp_dist = exp_mem[c][DIST_W-1:0];
            if ((class_idx !== exp_idx) || (class_dist !== exp_dist)) begin
                errors++;
                $display("--------------------------------------------------");
                $display("FAIL case %0d", c);
                $display("  expected idx=%0d dist=%0d", exp_idx, exp_dist);
                $display("  got      idx=%0d dist=%0d", class_idx, class_dist);
                $display("--------------------------------------------------");
            end
            @(posedge clk);
        end
    endtask

    initial begin
        errors  = 0;
        checked = 0;

        if (!$value$plusargs("CASES=%d", num_cases)) num_cases = 500;
        if (!$value$plusargs("VECDIR=%s", vecdir))
            vecdir = "python_ref/vectors/cosim_core_narrow";
        if (num_cases > MAX_CASES) begin
            $display("WARNING: CASES=%0d exceeds MAX_CASES=%0d; clamping.", num_cases, MAX_CASES);
            num_cases = MAX_CASES;
        end

        $display("==================================================");
        $display("tb_core_narrow_cosim: narrow end-to-end vs Python golden");
        $display("  VECDIR = %s", vecdir);
        $display("  CASES  = %0d   (D=%0d, K_BITS=%0d, N_CLASS=%0d)",
                 num_cases, D, K_BITS_L, N_CLASS);
        $display("==================================================");

        $readmemh($sformatf("%s/core_proto_narrow.hex", vecdir), proto_mem);
        $readmemh($sformatf("%s/core_levels.hex",       vecdir), lvl_mem);
        $readmemh($sformatf("%s/core_expect.hex",       vecdir), exp_mem);

        apply_reset();
        configure_core();

        for (int c = 0; c < num_cases; c++) begin
            run_case(c);
            if ((c % 100) == 99)
                $display("  ... %0d / %0d checked (errors so far: %0d)", c+1, num_cases, errors);
        end

        $display("==================================================");
        if (errors == 0) begin
            $display("PASS: all %0d narrow end-to-end cases match the Python golden.", checked);
            $display("==================================================");
            $finish;
        end else begin
            $display("FAIL: %0d / %0d cases mismatched.", errors, checked);
            $display("==================================================");
            $fatal(1, "narrow core co-simulation mismatch");
        end
    end

endmodule
