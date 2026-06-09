`timescale 1ns/1ps
//============================================================================
// tb_encoder_cosim.sv -- Automated bit-exact co-simulation of encoder_top
//                        against the Python golden reference (hdc_ref.py).
//
// Reads flat $readmemh vector files produced by:
//     python python_ref/generate_vectors.py --encoder
//
//   enc_levels.hex   NUM_CASES words   (level grid: level[p] at [p*LEVEL_W +: LEVEL_W])
//   enc_expect.hex   NUM_CASES*WORDS   (golden query hypervector per case)
//   item_mem_*.mem   loaded directly by the DUT's item_mem ROMs (init)
//
// Plusargs:
//   +CASES=<n>     number of cases to run    (default 500)
//   +VECDIR=<path> directory holding the hex (default python_ref/vectors/cosim_encoder)
//
// NOTE: the item-memory .mem files are loaded by encoder_top's item_mem ROMs
// via their MEMFILE parameters (default python_ref/vectors/cosim_encoder/...),
// so VECDIR must match that default unless those params are overridden too.
//
// Exit: $finish on full match, $fatal on any mismatch (non-zero sim exit).
//============================================================================

module tb_encoder_cosim;

    parameter int WORDS         = 16;
    parameter int BITS_PER_WORD = 64;
    parameter int N_CH          = 4;
    parameter int N_FEAT        = 5;
    parameter int N_VAL         = 16;
    parameter int CNT_W         = 6;
    parameter int MAX_CASES     = 2000;
    localparam int D       = WORDS * BITS_PER_WORD;
    localparam int N_PAIRS = N_CH * N_FEAT;
    localparam int LEVEL_W = (N_VAL <= 1) ? 1 : $clog2(N_VAL);
    localparam int LVL_BITS = N_PAIRS * LEVEL_W;

    logic                     clk, rst_n;
    logic                     start;
    logic [LVL_BITS-1:0]      levels_flat;
    logic                     busy;
    logic                     out_valid;
    logic [D-1:0]             query_vec;

    encoder_top #(
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD),
        .N_CH(N_CH), .N_FEAT(N_FEAT), .N_VAL(N_VAL), .CNT_W(CNT_W)
    ) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .start      (start),
        .levels_flat(levels_flat),
        .busy       (busy),
        .out_valid  (out_valid),
        .query_vec  (query_vec)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Golden memories
    logic [LVL_BITS-1:0]      lvl_mem [0:MAX_CASES-1];
    logic [BITS_PER_WORD-1:0] exp_mem [0:MAX_CASES*WORDS-1];

    int    num_cases;
    string vecdir;
    int    errors;
    int    checked;

    function automatic logic [D-1:0] assemble_exp(input int c);
        logic [D-1:0] v;
        int w;
        begin
            v = '0;
            for (w = 0; w < WORDS; w++)
                v[(w+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = exp_mem[c*WORDS + w];
            return v;
        end
    endfunction

    task automatic report_mismatch(input int c, input logic [D-1:0] expected);
        int b, first_bit;
        begin
            first_bit = -1;
            for (b = 0; b < D; b++) begin
                if (expected[b] !== query_vec[b]) begin first_bit = b; break; end
            end
            $display("--------------------------------------------------");
            $display("FAIL case %0d", c);
            $display("  first differing bit = %0d (word %0d)", first_bit,
                     (first_bit >= 0) ? first_bit / BITS_PER_WORD : -1);
            $display("--------------------------------------------------");
        end
    endtask

    task automatic apply_reset;
        begin
            rst_n       <= 1'b0;
            start       <= 1'b0;
            levels_flat <= '0;
            repeat (5) @(posedge clk);
            rst_n <= 1'b1;
            repeat (2) @(posedge clk);
        end
    endtask

    task automatic run_case(input int c);
        logic [D-1:0] expected;
        begin
            levels_flat <= lvl_mem[c];
            start       <= 1'b1;
            @(posedge clk);
            start       <= 1'b0;
            while (!out_valid) @(posedge clk);   // query_vec valid this edge

            checked++;
            expected = assemble_exp(c);
            if (query_vec !== expected) begin
                errors++;
                report_mismatch(c, expected);
            end
            @(posedge clk);                      // return to idle before next case
        end
    endtask

    initial begin
        errors  = 0;
        checked = 0;

        if (!$value$plusargs("CASES=%d", num_cases)) num_cases = 500;
        if (!$value$plusargs("VECDIR=%s", vecdir))   vecdir = "python_ref/vectors/cosim_encoder";
        if (num_cases > MAX_CASES) begin
            $display("WARNING: CASES=%0d exceeds MAX_CASES=%0d; clamping.", num_cases, MAX_CASES);
            num_cases = MAX_CASES;
        end

        $display("==================================================");
        $display("tb_encoder_cosim: EMG-window encoder vs Python golden");
        $display("  VECDIR = %s", vecdir);
        $display("  CASES  = %0d   (D=%0d, %0dx%0d pairs)", num_cases, D, N_CH, N_FEAT);
        $display("==================================================");

        $readmemh($sformatf("%s/enc_levels.hex", vecdir), lvl_mem);
        $readmemh($sformatf("%s/enc_expect.hex", vecdir), exp_mem);

        apply_reset();

        for (int c = 0; c < num_cases; c++) begin
            run_case(c);
            if ((c % 100) == 99)
                $display("  ... %0d / %0d checked (errors so far: %0d)", c+1, num_cases, errors);
        end

        $display("==================================================");
        if (errors == 0) begin
            $display("PASS: all %0d encoder cases match the Python golden bit-for-bit.", checked);
            $display("==================================================");
            $finish;
        end else begin
            $display("FAIL: %0d / %0d cases mismatched.", errors, checked);
            $display("==================================================");
            $fatal(1, "encoder co-simulation mismatch");
        end
    end

endmodule
