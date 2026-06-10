`timescale 1ns/1ps
//============================================================================
// tb_core_cosim.sv -- Automated bit-exact co-simulation of hdc_core_top
//                     (encoder_top -> popcount_am) against the Python golden.
//
// Reads flat $readmemh vector files produced by:
//     python python_ref/generate_vectors.py --core
//
//   core_proto.hex   N_CLASS*WORDS words  (trained prototypes, class-major)
//   core_mask.hex    WORDS words          (pruning mask)
//   core_levels.hex  NUM_CASES words      (packed level grid per case)
//   core_expect.hex  NUM_CASES words      ((best_idx<<16)|best_dist)
//   item_mem_*.mem   loaded by the DUT's item_mem ROMs (init)
//
// Protocol: prototypes + mask are loaded ONCE (like a real deployment after
// offline training), then every case runs full inference: level grid in ->
// class index + distance out.
//
// Plusargs:
//   +CASES=<n>     number of cases to run    (default 500)
//   +VECDIR=<path> directory holding the hex (default python_ref/vectors/cosim_core)
//
// Exit: $finish on full match, $fatal on any mismatch (non-zero sim exit).
//============================================================================

module tb_core_cosim;

    parameter int WORDS         = 16;
    parameter int BITS_PER_WORD = 64;
    parameter int N_CH          = 4;
    parameter int N_FEAT        = 5;
    parameter int N_VAL         = 16;
    parameter int N_CLASS       = 8;
    parameter int CNT_W         = 6;
    parameter int MAX_CASES     = 2000;
    localparam int D        = WORDS * BITS_PER_WORD;
    localparam int N_PAIRS  = N_CH * N_FEAT;
    localparam int LEVEL_W  = (N_VAL   <= 1) ? 1 : $clog2(N_VAL);
    localparam int IDX_W    = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS);
    localparam int DIST_W   = $clog2(D + 1);
    localparam int LVL_BITS = N_PAIRS * LEVEL_W;

    logic                     clk, rst_n;
    logic                     proto_we;
    logic [IDX_W-1:0]         proto_idx;
    logic [D-1:0]             proto_vec;
    logic                     mask_we;
    logic [D-1:0]             mask_vec;
    logic                     start;
    logic [LVL_BITS-1:0]      levels_flat;
    logic                     busy;
    logic                     out_valid;
    logic [IDX_W-1:0]         class_idx;
    logic [DIST_W-1:0]        class_dist;

    hdc_core_top #(
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
        .N_CH(N_CH), .N_FEAT(N_FEAT), .N_VAL(N_VAL),
        .N_CLASS(N_CLASS), .CNT_W(CNT_W)
    ) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .proto_we   (proto_we),
        .proto_idx  (proto_idx),
        .proto_vec  (proto_vec),
        .mask_we    (mask_we),
        .mask_vec   (mask_vec),
        .start      (start),
        .levels_flat(levels_flat),
        .busy       (busy),
        .out_valid  (out_valid),
        .class_idx  (class_idx),
        .class_dist (class_dist)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Golden memories
    logic [BITS_PER_WORD-1:0] proto_mem [0:N_CLASS*WORDS-1];
    logic [BITS_PER_WORD-1:0] mask_mem  [0:WORDS-1];
    logic [LVL_BITS-1:0]      lvl_mem   [0:MAX_CASES-1];
    logic [31:0]              exp_mem   [0:MAX_CASES-1];

    int    num_cases;
    string vecdir;
    int    errors;
    int    checked;

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

    task automatic apply_reset;
        begin
            rst_n       <= 1'b0;
            proto_we    <= 1'b0;
            proto_idx   <= '0;
            proto_vec   <= '0;
            mask_we     <= 1'b0;
            mask_vec    <= '0;
            start       <= 1'b0;
            levels_flat <= '0;
            repeat (5) @(posedge clk);
            rst_n <= 1'b1;
            repeat (2) @(posedge clk);
        end
    endtask

    // One-time configuration: load trained prototypes + pruning mask
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

    task automatic run_case(input int c);
        logic [IDX_W-1:0]  exp_idx;
        logic [DIST_W-1:0] exp_dist;
        begin
            levels_flat <= lvl_mem[c];
            start       <= 1'b1;
            @(posedge clk);
            start       <= 1'b0;
            while (!out_valid) @(posedge clk);   // class_idx/class_dist valid

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
            @(posedge clk);                      // settle before next case
        end
    endtask

    initial begin
        errors  = 0;
        checked = 0;

        if (!$value$plusargs("CASES=%d", num_cases)) num_cases = 500;
        if (!$value$plusargs("VECDIR=%s", vecdir))   vecdir = "python_ref/vectors/cosim_core";
        if (num_cases > MAX_CASES) begin
            $display("WARNING: CASES=%0d exceeds MAX_CASES=%0d; clamping.", num_cases, MAX_CASES);
            num_cases = MAX_CASES;
        end

        $display("==================================================");
        $display("tb_core_cosim: end-to-end inference vs Python golden");
        $display("  VECDIR = %s", vecdir);
        $display("  CASES  = %0d   (D=%0d, %0dx%0d pairs, N_CLASS=%0d)",
                 num_cases, D, N_CH, N_FEAT, N_CLASS);
        $display("==================================================");

        $readmemh($sformatf("%s/core_proto.hex",  vecdir), proto_mem);
        $readmemh($sformatf("%s/core_mask.hex",   vecdir), mask_mem);
        $readmemh($sformatf("%s/core_levels.hex", vecdir), lvl_mem);
        $readmemh($sformatf("%s/core_expect.hex", vecdir), exp_mem);

        apply_reset();
        configure_core();

        for (int c = 0; c < num_cases; c++) begin
            run_case(c);
            if ((c % 100) == 99)
                $display("  ... %0d / %0d checked (errors so far: %0d)", c+1, num_cases, errors);
        end

        $display("==================================================");
        if (errors == 0) begin
            $display("PASS: all %0d end-to-end inference cases match the Python golden.", checked);
            $display("==================================================");
            $finish;
        end else begin
            $display("FAIL: %0d / %0d cases mismatched.", errors, checked);
            $display("==================================================");
            $fatal(1, "core co-simulation mismatch");
        end
    end

endmodule
