`timescale 1ns/1ps
//============================================================================
// tb_cosim.sv  --  Automated bit-exact co-simulation of xor_permute_top
//                  against the Python golden reference (hdc_ref.py).
//
// Reads flat $readmemh vector files produced by:
//     python python_ref/generate_vectors.py --flat
//
//   in_vec.hex    NUM_CASES*WORDS words   (stimulus: input vector)
//   bind_vec.hex  NUM_CASES*WORDS words   (stimulus: bind vector)
//   expected.hex  NUM_CASES*WORDS words   (Python golden = bind then permute)
//   ctrl.hex      NUM_CASES words         (per case: (mode<<16)|param)
//
// Plusargs:
//   +CASES=<n>        number of cases to run        (default 1000)
//   +VECDIR=<path>    directory holding the .hex     (default vectors/cosim)
//
// Exit: $finish on full match, $fatal on any mismatch (non-zero sim exit).
//============================================================================

module tb_cosim;

    parameter int WORDS         = 16;
    parameter int BITS_PER_WORD = 64;
    parameter int MAX_CASES     = 5000;
    localparam int D = WORDS * BITS_PER_WORD;

    // ------------------------------------------------------------------
    // DUT signals
    // ------------------------------------------------------------------
    logic                 clk, rst_n;
    logic                 in_valid, in_ready;
    logic [D-1:0]         in_vec_flat;
    logic [D-1:0]         bind_vec_flat;
    logic [1:0]           perm_mode;
    logic [$clog2(D)-1:0] perm_param;
    logic                 out_valid, out_ready;
    logic [D-1:0]         out_vec_flat;

    xor_permute_top #(WORDS, BITS_PER_WORD) dut (
        .clk          (clk),
        .rst_n        (rst_n),
        .in_valid     (in_valid),
        .in_ready     (in_ready),
        .in_vec_flat  (in_vec_flat),
        .bind_vec_flat(bind_vec_flat),
        .perm_mode    (perm_mode),
        .perm_param   (perm_param),
        .out_valid    (out_valid),
        .out_ready    (out_ready),
        .out_vec_flat (out_vec_flat)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // ------------------------------------------------------------------
    // Golden memories (filled by $readmemh)
    // ------------------------------------------------------------------
    logic [BITS_PER_WORD-1:0] in_mem   [0:MAX_CASES*WORDS-1];
    logic [BITS_PER_WORD-1:0] bind_mem [0:MAX_CASES*WORDS-1];
    logic [BITS_PER_WORD-1:0] exp_mem  [0:MAX_CASES*WORDS-1];
    logic [31:0]              ctrl_mem [0:MAX_CASES-1];

    int    num_cases;
    string vecdir;
    int    errors;
    int    checked;

    // Assemble a flat D-bit vector for case `c` from a per-word memory.
    function automatic logic [D-1:0] assemble(
        ref logic [BITS_PER_WORD-1:0] mem [0:MAX_CASES*WORDS-1],
        input int c
    );
        logic [D-1:0] v;
        int w;
        begin
            v = '0;
            for (w = 0; w < WORDS; w++) begin
                v[(w+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = mem[c*WORDS + w];
            end
            return v;
        end
    endfunction

    // Report the first differing word/bit to make debugging painless.
    task automatic report_mismatch(
        input int c,
        input logic [1:0] mode,
        input int param,
        input logic [D-1:0] expected,
        input logic [D-1:0] actual
    );
        int b;
        int first_bit;
        begin
            first_bit = -1;
            for (b = 0; b < D; b++) begin
                if (expected[b] !== actual[b]) begin
                    first_bit = b;
                    break;
                end
            end
            $display("--------------------------------------------------");
            $display("FAIL case %0d  (mode=%0d param=%0d)", c, mode, param);
            $display("  first differing bit = %0d (word %0d)", first_bit,
                     (first_bit >= 0) ? first_bit / BITS_PER_WORD : -1);
            $display("  expected[%0d +:64] = %016h", (first_bit/BITS_PER_WORD)*BITS_PER_WORD,
                     expected[((first_bit/BITS_PER_WORD)+1)*BITS_PER_WORD-1 -: BITS_PER_WORD]);
            $display("  actual  [%0d +:64] = %016h", (first_bit/BITS_PER_WORD)*BITS_PER_WORD,
                     actual[((first_bit/BITS_PER_WORD)+1)*BITS_PER_WORD-1 -: BITS_PER_WORD]);
            $display("--------------------------------------------------");
        end
    endtask

    task automatic apply_reset;
        begin
            rst_n         <= 1'b0;
            in_valid      <= 1'b0;
            out_ready     <= 1'b1;
            in_vec_flat   <= '0;
            bind_vec_flat <= '0;
            perm_mode     <= 2'b00;
            perm_param    <= '0;
            repeat (5) @(posedge clk);
            rst_n <= 1'b1;
            repeat (2) @(posedge clk);
        end
    endtask

    // Drive one case through the handshake and compare to golden.
    task automatic run_case(input int c);
        logic [D-1:0] in_v;
        logic [D-1:0] bind_v;
        logic [D-1:0] expected;
        logic [1:0]   mode;
        int           param;
        int           timeout;
        begin
            in_v     = assemble(in_mem,   c);
            bind_v   = assemble(bind_mem, c);
            expected = assemble(exp_mem,  c);
            mode     = ctrl_mem[c][17:16];
            param    = ctrl_mem[c][15:0];

            @(posedge clk);
            while (!in_ready) @(posedge clk);

            in_vec_flat   <= in_v;
            bind_vec_flat <= bind_v;
            perm_mode     <= mode;
            perm_param    <= param[$clog2(D)-1:0];
            in_valid      <= 1'b1;
            @(posedge clk);
            in_valid <= 1'b0;

            timeout = 0;
            while (out_valid !== 1'b1) begin
                @(posedge clk);
                timeout++;
                if (timeout > 50) begin
                    $display("FAIL case %0d: timed out waiting for out_valid", c);
                    errors++;
                    return;
                end
            end

            checked++;
            if (out_vec_flat !== expected) begin
                errors++;
                report_mismatch(c, mode, param, expected, out_vec_flat);
            end

            @(posedge clk);  // allow output to clear (out_ready held high)
        end
    endtask

    initial begin
        errors  = 0;
        checked = 0;

        if (!$value$plusargs("CASES=%d", num_cases))   num_cases = 1000;
        if (!$value$plusargs("VECDIR=%s", vecdir))      vecdir    = "python_ref/vectors/cosim";
        if (num_cases > MAX_CASES) begin
            $display("WARNING: CASES=%0d exceeds MAX_CASES=%0d; clamping.", num_cases, MAX_CASES);
            num_cases = MAX_CASES;
        end

        $display("==================================================");
        $display("tb_cosim: bind+permute vs Python golden");
        $display("  VECDIR = %s", vecdir);
        $display("  CASES  = %0d   (D=%0d)", num_cases, D);
        $display("==================================================");

        $readmemh($sformatf("%s/in_vec.hex",   vecdir), in_mem);
        $readmemh($sformatf("%s/bind_vec.hex", vecdir), bind_mem);
        $readmemh($sformatf("%s/expected.hex", vecdir), exp_mem);
        $readmemh($sformatf("%s/ctrl.hex",     vecdir), ctrl_mem);

        apply_reset();

        for (int c = 0; c < num_cases; c++) begin
            run_case(c);
            if ((c % 200) == 199)
                $display("  ... %0d / %0d checked (errors so far: %0d)", c+1, num_cases, errors);
        end

        $display("==================================================");
        if (errors == 0) begin
            $display("PASS: all %0d cases match the Python golden bit-for-bit.", checked);
            $display("==================================================");
            $finish;
        end else begin
            $display("FAIL: %0d / %0d cases mismatched.", errors, checked);
            $display("==================================================");
            $fatal(1, "co-simulation mismatch");
        end
    end

endmodule
