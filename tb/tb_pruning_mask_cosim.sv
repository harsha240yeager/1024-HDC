`timescale 1ns/1ps
//============================================================================
// tb_pruning_mask_cosim.sv -- Bit-exact co-simulation of pruning_mask.sv
//                             against the Python golden reference (hdc_ref.py).
//
// Verifies that pruning_mask reproduces each golden D-bit mask on mask_out
// through BOTH write paths, and that the reset default is all-ones:
//   * Full-width parallel load (load_full / load_vec).
//   * Word-addressed AXI-style writes (wr_en / wr_addr / wr_data, AXI_W bits).
//
// Reads flat $readmemh vectors produced by:
//     python python_ref/generate_vectors.py --pruning-mask --count <n>
//
//   mask.hex   NUM_CASES*WORDS 64-bit words (one mask after another)
//
// Plusargs:
//   +CASES=<n>     number of masks to run    (default 64)
//   +VECDIR=<path> directory holding the hex  (default
//                  python_ref/vectors/cosim_pruning_mask)
//
// Exit: $finish on full match, $fatal on any mismatch (non-zero sim exit).
//============================================================================

module tb_pruning_mask_cosim;

    parameter int WORDS         = 16;
    parameter int BITS_PER_WORD = 64;
    parameter int AXI_W         = 32;
    parameter int MAX_CASES     = 4096;

    localparam int D        = WORDS * BITS_PER_WORD;
    localparam int N_WORDS  = D / AXI_W;
    localparam int ADDR_W   = (N_WORDS <= 1) ? 1 : $clog2(N_WORDS);

    logic               clk, rst_n;
    logic               wr_en;
    logic [ADDR_W-1:0]  wr_addr;
    logic [AXI_W-1:0]   wr_data;
    logic               load_full;
    logic [D-1:0]       load_vec;
    logic [D-1:0]       mask_out;

    pruning_mask #(
        .D(D), .AXI_W(AXI_W)
    ) dut (
        .clk      (clk),
        .rst_n    (rst_n),
        .wr_en    (wr_en),
        .wr_addr  (wr_addr),
        .wr_data  (wr_data),
        .load_full(load_full),
        .load_vec (load_vec),
        .mask_out (mask_out)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Golden mask words (64-bit), MAX_CASES masks back-to-back.
    logic [BITS_PER_WORD-1:0] mask_mem [0:MAX_CASES*WORDS-1];

    int    num_cases;
    string vecdir;
    int    errors;
    int    checked;

    function automatic logic [D-1:0] assemble_mask(input int c);
        logic [D-1:0] v;
        int w;
        begin
            v = '0;
            for (w = 0; w < WORDS; w++)
                v[(w+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = mask_mem[c*WORDS + w];
            return v;
        end
    endfunction

    task automatic apply_reset;
        begin
            rst_n     <= 1'b0;
            wr_en     <= 1'b0;
            wr_addr   <= '0;
            wr_data   <= '0;
            load_full <= 1'b0;
            load_vec  <= '0;
            repeat (5) @(posedge clk);
            rst_n <= 1'b1;
            repeat (2) @(posedge clk);
        end
    endtask

    // Full-width parallel load, then compare mask_out.
    task automatic check_full_load(input int c, input logic [D-1:0] exp_mask);
        begin
            load_vec  <= exp_mask;
            load_full <= 1'b1;
            @(posedge clk);
            load_full <= 1'b0;
            @(posedge clk);
            checked++;
            if (mask_out !== exp_mask) begin
                errors++;
                $display("--------------------------------------------------");
                $display("FAIL case %0d (full-width load): mask_out mismatch", c);
                $display("--------------------------------------------------");
            end
        end
    endtask

    // Pre-load the complement (so every AXI word must change), then write the
    // mask word-by-word and compare mask_out.
    task automatic check_word_load(input int c, input logic [D-1:0] exp_mask);
        int g;
        begin
            load_vec  <= ~exp_mask;
            load_full <= 1'b1;
            @(posedge clk);
            load_full <= 1'b0;
            @(posedge clk);

            for (g = 0; g < N_WORDS; g++) begin
                wr_en   <= 1'b1;
                wr_addr <= g[ADDR_W-1:0];
                wr_data <= exp_mask[g*AXI_W +: AXI_W];
                @(posedge clk);
            end
            wr_en <= 1'b0;
            @(posedge clk);

            checked++;
            if (mask_out !== exp_mask) begin
                errors++;
                $display("--------------------------------------------------");
                $display("FAIL case %0d (word-addressed load): mask_out mismatch", c);
                $display("--------------------------------------------------");
            end
        end
    endtask

    logic [D-1:0] exp_mask;

    initial begin
        errors  = 0;
        checked = 0;

        if (!$value$plusargs("CASES=%d", num_cases)) num_cases = 64;
        if (!$value$plusargs("VECDIR=%s", vecdir))
            vecdir = "python_ref/vectors/cosim_pruning_mask";
        if (num_cases > MAX_CASES) begin
            $display("WARNING: CASES=%0d exceeds MAX_CASES=%0d; clamping.", num_cases, MAX_CASES);
            num_cases = MAX_CASES;
        end

        $display("==================================================");
        $display("tb_pruning_mask_cosim: pruning_mask vs Python golden");
        $display("  VECDIR  = %s", vecdir);
        $display("  CASES   = %0d   (D=%0d, AXI_W=%0d, N_WORDS=%0d)",
                 num_cases, D, AXI_W, N_WORDS);
        $display("==================================================");

        $readmemh($sformatf("%s/mask.hex", vecdir), mask_mem);

        apply_reset();

        // Reset default must be all-ones (unpruned => plain Hamming).
        checked++;
        if (mask_out !== {D{1'b1}}) begin
            errors++;
            $display("FAIL: reset default mask_out is not all-ones");
        end

        for (int c = 0; c < num_cases; c++) begin
            exp_mask = assemble_mask(c);
            check_full_load(c, exp_mask);
            check_word_load(c, exp_mask);
            if ((c % 16) == 15)
                $display("  ... %0d / %0d masks checked (errors so far: %0d)", c+1, num_cases, errors);
        end

        $display("==================================================");
        if (errors == 0) begin
            $display("PASS: all %0d pruning_mask checks match the Python golden bit-for-bit.", checked);
            $display("==================================================");
            $finish;
        end else begin
            $display("FAIL: %0d / %0d checks mismatched.", errors, checked);
            $display("==================================================");
            $fatal(1, "pruning_mask co-simulation mismatch");
        end
    end

endmodule
