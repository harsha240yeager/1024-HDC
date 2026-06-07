`timescale 1ns/1ps
//============================================================================
// tb_bundle_cosim.sv -- Automated bit-exact co-simulation of bundle_unit
//                       against the Python golden reference (hdc_ref.py).
//
// Reads flat $readmemh vector files produced by:
//     python python_ref/generate_vectors.py --bundle
//
//   bundle_in.hex  sum(K_i)*WORDS words   (all input vectors, concatenated)
//   expected.hex   NUM_CASES*WORDS words  (bundled/thresholded result per case)
//   kcnt.hex       NUM_CASES words        (K = #vectors bundled in each case)
//
// Plusargs:
//   +CASES=<n>        number of cases to run        (default 500)
//   +VECDIR=<path>    directory holding the .hex     (default python_ref/vectors/cosim_bundle)
//
// Exit: $finish on full match, $fatal on any mismatch (non-zero sim exit).
//============================================================================

module tb_bundle_cosim;

    parameter int WORDS         = 16;
    parameter int BITS_PER_WORD = 64;
    parameter int CNT_W         = 6;
    parameter int MAX_CASES     = 2000;
    parameter int K_MAX         = 16;
    localparam int D = WORDS * BITS_PER_WORD;

    logic              clk, rst_n;
    logic              clear;
    logic              in_valid;
    logic [D-1:0]      in_vec_flat;
    logic [D-1:0]      out_vec_flat;
    logic [31:0]       n_accum_out;

    bundle_unit #(
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD), .CNT_W(CNT_W)
    ) dut (
        .clk         (clk),
        .rst_n       (rst_n),
        .clear       (clear),
        .in_valid    (in_valid),
        .in_vec_flat (in_vec_flat),
        .out_vec_flat(out_vec_flat),
        .n_accum_out (n_accum_out)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Golden memories
    logic [BITS_PER_WORD-1:0] in_mem  [0:MAX_CASES*K_MAX*WORDS-1];
    logic [BITS_PER_WORD-1:0] exp_mem [0:MAX_CASES*WORDS-1];
    logic [31:0]              k_mem   [0:MAX_CASES-1];

    int    num_cases;
    string vecdir;
    int    errors;
    int    checked;
    int    in_off;   // running word offset into in_mem

    function automatic logic [D-1:0] assemble_in(input int base_word);
        logic [D-1:0] v;
        int w;
        begin
            v = '0;
            for (w = 0; w < WORDS; w++)
                v[(w+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = in_mem[base_word + w];
            return v;
        end
    endfunction

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

    task automatic report_mismatch(
        input int c, input int K,
        input logic [D-1:0] expected, input logic [D-1:0] actual
    );
        int b, first_bit;
        begin
            first_bit = -1;
            for (b = 0; b < D; b++) begin
                if (expected[b] !== actual[b]) begin first_bit = b; break; end
            end
            $display("--------------------------------------------------");
            $display("FAIL case %0d  (K=%0d, n_accum=%0d)", c, K, n_accum_out);
            $display("  first differing bit = %0d (word %0d)", first_bit,
                     (first_bit >= 0) ? first_bit / BITS_PER_WORD : -1);
            $display("--------------------------------------------------");
        end
    endtask

    task automatic apply_reset;
        begin
            rst_n       <= 1'b0;
            clear       <= 1'b0;
            in_valid    <= 1'b0;
            in_vec_flat <= '0;
            repeat (5) @(posedge clk);
            rst_n <= 1'b1;
            repeat (2) @(posedge clk);
        end
    endtask

    task automatic run_case(input int c);
        logic [D-1:0] expected;
        int K, j;
        begin
            K = k_mem[c];

            // start a fresh bundle
            clear <= 1'b1;
            @(posedge clk);
            clear <= 1'b0;

            // accumulate K vectors
            for (j = 0; j < K; j++) begin
                in_vec_flat <= assemble_in(in_off + j*WORDS);
                in_valid    <= 1'b1;
                @(posedge clk);
            end
            in_valid <= 1'b0;
            @(posedge clk);  // let final accumulate register; comb output settles

            checked++;
            expected = assemble_exp(c);
            if (out_vec_flat !== expected) begin
                errors++;
                report_mismatch(c, K, expected, out_vec_flat);
            end

            in_off += K*WORDS;
        end
    endtask

    initial begin
        errors  = 0;
        checked = 0;
        in_off  = 0;

        if (!$value$plusargs("CASES=%d", num_cases)) num_cases = 500;
        if (!$value$plusargs("VECDIR=%s", vecdir))   vecdir = "python_ref/vectors/cosim_bundle";
        if (num_cases > MAX_CASES) begin
            $display("WARNING: CASES=%0d exceeds MAX_CASES=%0d; clamping.", num_cases, MAX_CASES);
            num_cases = MAX_CASES;
        end

        $display("==================================================");
        $display("tb_bundle_cosim: majority bundle vs Python golden");
        $display("  VECDIR = %s", vecdir);
        $display("  CASES  = %0d   (D=%0d, CNT_W=%0d)", num_cases, D, CNT_W);
        $display("==================================================");

        $readmemh($sformatf("%s/bundle_in.hex", vecdir), in_mem);
        $readmemh($sformatf("%s/expected.hex",  vecdir), exp_mem);
        $readmemh($sformatf("%s/kcnt.hex",      vecdir), k_mem);

        apply_reset();

        for (int c = 0; c < num_cases; c++) begin
            run_case(c);
            if ((c % 100) == 99)
                $display("  ... %0d / %0d checked (errors so far: %0d)", c+1, num_cases, errors);
        end

        $display("==================================================");
        if (errors == 0) begin
            $display("PASS: all %0d bundle cases match the Python golden bit-for-bit.", checked);
            $display("==================================================");
            $finish;
        end else begin
            $display("FAIL: %0d / %0d cases mismatched.", errors, checked);
            $display("==================================================");
            $fatal(1, "bundle co-simulation mismatch");
        end
    end

endmodule
