`timescale 1ns/1ps
//============================================================================
// tb_am_cosim.sv -- Automated bit-exact co-simulation of popcount_am
//                   against the Python golden reference (hdc_ref.py).
//
// Reads flat $readmemh vector files produced by:
//     python python_ref/generate_vectors.py --am
//
//   am_proto.hex   NUM_CASES*N_CLASS*WORDS words  (prototypes, class-major)
//   am_mask.hex    NUM_CASES*WORDS words          (per-bit pruning mask)
//   am_query.hex   NUM_CASES*WORDS words          (query hypervector)
//   am_expect.hex  NUM_CASES words                ((best_idx<<16)|best_dist)
//
// Plusargs:
//   +CASES=<n>     number of cases to run    (default 500)
//   +VECDIR=<path> directory holding the hex (default python_ref/vectors/cosim_am)
//
// Exit: $finish on full match, $fatal on any mismatch (non-zero sim exit).
//============================================================================

module tb_am_cosim;

    parameter int WORDS         = 16;
    parameter int BITS_PER_WORD = 64;
    parameter int N_CLASS       = 8;
    parameter int MAX_CASES     = 2000;
    localparam int D      = WORDS * BITS_PER_WORD;
    localparam int IDX_W  = (N_CLASS <= 1) ? 1 : $clog2(N_CLASS);
    localparam int DIST_W = $clog2(D + 1);

    logic               clk, rst_n;
    logic               proto_we;
    logic [IDX_W-1:0]   load_idx;
    logic [D-1:0]       load_vec;
    logic               mask_we;
    logic [D-1:0]       mask_vec;
    logic               q_valid;
    logic [D-1:0]       query_vec;
    logic               out_valid;
    logic [IDX_W-1:0]   best_idx;
    logic [DIST_W-1:0]  best_dist;

    popcount_am #(
        .WORDS(WORDS), .BITS_PER_WORD(BITS_PER_WORD), .N_CLASS(N_CLASS)
    ) dut (
        .clk      (clk),
        .rst_n    (rst_n),
        .proto_we (proto_we),
        .load_idx (load_idx),
        .load_vec (load_vec),
        .mask_we  (mask_we),
        .mask_vec (mask_vec),
        .q_valid  (q_valid),
        .query_vec(query_vec),
        .out_valid(out_valid),
        .best_idx (best_idx),
        .best_dist(best_dist)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Golden memories
    logic [BITS_PER_WORD-1:0] proto_mem [0:MAX_CASES*N_CLASS*WORDS-1];
    logic [BITS_PER_WORD-1:0] mask_mem  [0:MAX_CASES*WORDS-1];
    logic [BITS_PER_WORD-1:0] query_mem [0:MAX_CASES*WORDS-1];
    logic [31:0]              exp_mem   [0:MAX_CASES-1];

    int    num_cases;
    string vecdir;
    int    errors;
    int    checked;

    function automatic logic [D-1:0] assemble_proto(input int c, input int kcls);
        logic [D-1:0] v;
        int w, base;
        begin
            base = (c*N_CLASS + kcls) * WORDS;
            v = '0;
            for (w = 0; w < WORDS; w++)
                v[(w+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = proto_mem[base + w];
            return v;
        end
    endfunction

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

    function automatic logic [D-1:0] assemble_query(input int c);
        logic [D-1:0] v;
        int w;
        begin
            v = '0;
            for (w = 0; w < WORDS; w++)
                v[(w+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = query_mem[c*WORDS + w];
            return v;
        end
    endfunction

    task automatic apply_reset;
        begin
            rst_n     <= 1'b0;
            proto_we  <= 1'b0;
            load_idx  <= '0;
            load_vec  <= '0;
            mask_we   <= 1'b0;
            mask_vec  <= '0;
            q_valid   <= 1'b0;
            query_vec <= '0;
            repeat (5) @(posedge clk);
            rst_n <= 1'b1;
            repeat (2) @(posedge clk);
        end
    endtask

    task automatic run_case(input int c);
        logic [IDX_W-1:0]  exp_idx;
        logic [DIST_W-1:0] exp_dist;
        int kcls;
        begin
            // Load all N_CLASS prototypes
            for (kcls = 0; kcls < N_CLASS; kcls++) begin
                load_idx <= kcls[IDX_W-1:0];
                load_vec <= assemble_proto(c, kcls);
                proto_we <= 1'b1;
                @(posedge clk);
            end
            proto_we <= 1'b0;

            // Load the mask
            mask_vec <= assemble_mask(c);
            mask_we  <= 1'b1;
            @(posedge clk);
            mask_we  <= 1'b0;

            // Issue the query
            query_vec <= assemble_query(c);
            q_valid   <= 1'b1;
            @(posedge clk);
            q_valid   <= 1'b0;
            @(posedge clk);   // out_valid asserted, best_idx/best_dist valid

            checked++;
            exp_idx  = exp_mem[c][16 +: IDX_W];
            exp_dist = exp_mem[c][DIST_W-1:0];
            if ((best_idx !== exp_idx) || (best_dist !== exp_dist)) begin
                errors++;
                $display("--------------------------------------------------");
                $display("FAIL case %0d", c);
                $display("  expected idx=%0d dist=%0d", exp_idx, exp_dist);
                $display("  got      idx=%0d dist=%0d", best_idx, best_dist);
                $display("--------------------------------------------------");
            end
        end
    endtask

    initial begin
        errors  = 0;
        checked = 0;

        if (!$value$plusargs("CASES=%d", num_cases)) num_cases = 500;
        if (!$value$plusargs("VECDIR=%s", vecdir))   vecdir = "python_ref/vectors/cosim_am";
        if (num_cases > MAX_CASES) begin
            $display("WARNING: CASES=%0d exceeds MAX_CASES=%0d; clamping.", num_cases, MAX_CASES);
            num_cases = MAX_CASES;
        end

        $display("==================================================");
        $display("tb_am_cosim: nearest-prototype AM vs Python golden");
        $display("  VECDIR  = %s", vecdir);
        $display("  CASES   = %0d   (D=%0d, N_CLASS=%0d)", num_cases, D, N_CLASS);
        $display("==================================================");

        $readmemh($sformatf("%s/am_proto.hex",  vecdir), proto_mem);
        $readmemh($sformatf("%s/am_mask.hex",   vecdir), mask_mem);
        $readmemh($sformatf("%s/am_query.hex",  vecdir), query_mem);
        $readmemh($sformatf("%s/am_expect.hex", vecdir), exp_mem);

        apply_reset();

        for (int c = 0; c < num_cases; c++) begin
            run_case(c);
            if ((c % 100) == 99)
                $display("  ... %0d / %0d checked (errors so far: %0d)", c+1, num_cases, errors);
        end

        $display("==================================================");
        if (errors == 0) begin
            $display("PASS: all %0d AM cases match the Python golden bit-for-bit.", checked);
            $display("==================================================");
            $finish;
        end else begin
            $display("FAIL: %0d / %0d cases mismatched.", errors, checked);
            $display("==================================================");
            $fatal(1, "AM co-simulation mismatch");
        end
    end

endmodule
