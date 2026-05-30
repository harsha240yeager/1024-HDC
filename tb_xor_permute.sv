`timescale 1ns/1ps

module tb_xor_permute;
    parameter int WORDS = 16;
    parameter int BITS_PER_WORD = 64;
    localparam int D = WORDS * BITS_PER_WORD;

    logic clk, rst_n;
    logic in_valid, in_ready;
    logic [D-1:0] in_vec_flat;
    logic [D-1:0] bind_vec_flat;
    logic [1:0] perm_mode;
    logic [$clog2(D)-1:0] perm_param;
    logic out_valid, out_ready;
    logic [D-1:0] out_vec_flat;

    int test_count = 0;
    int pass_count = 0;
    int random_iterations = 60;

    int mode_seen [0:3];
    int stall_seen [0:3];
    int zero_param_seen;
    int word_width_param_seen;
    int full_width_minus_one_seen;
    int midpoint_param_seen;
    int reset_recovery_seen;
    int accepted_txn_count;
    int completed_txn_count;
    int flushed_txn_count;

    logic prev_out_valid;
    logic prev_out_ready;
    logic [D-1:0] prev_out_vec_flat;
    logic reset_flush_armed;

    xor_permute_top #(WORDS, BITS_PER_WORD) dut (
        .clk(clk),
        .rst_n(rst_n),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_vec_flat(in_vec_flat),
        .bind_vec_flat(bind_vec_flat),
        .perm_mode(perm_mode),
        .perm_param(perm_param),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_vec_flat(out_vec_flat)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    function automatic logic [D-1:0] rotate_right_vec(
        input logic [D-1:0] vec,
        input int unsigned r
    );
        logic [D-1:0] tmp;
        int i;
        int rr;
        begin
            rr = r % D;
            for (i = 0; i < D; i++) begin
                tmp[i] = vec[(i + rr) % D];
            end
            return tmp;
        end
    endfunction

    function automatic logic [D-1:0] rotate_right_each_word(
        input logic [D-1:0] vec,
        input int unsigned r
    );
        logic [D-1:0] tmp;
        logic [BITS_PER_WORD-1:0] w;
        logic [BITS_PER_WORD-1:0] wr;
        int wi;
        int bi;
        int rr;
        begin
            rr = r % BITS_PER_WORD;
            tmp = '0;
            for (wi = 0; wi < WORDS; wi++) begin
                w = vec[wi*BITS_PER_WORD +: BITS_PER_WORD];
                for (bi = 0; bi < BITS_PER_WORD; bi++) begin
                    wr[bi] = w[(bi + rr) % BITS_PER_WORD];
                end
                tmp[wi*BITS_PER_WORD +: BITS_PER_WORD] = wr;
            end
            return tmp;
        end
    endfunction

    function automatic logic [D-1:0] reverse_words(
        input logic [D-1:0] vec
    );
        logic [D-1:0] tmp;
        int wi;
        begin
            tmp = '0;
            for (wi = 0; wi < WORDS; wi++) begin
                tmp[wi*BITS_PER_WORD +: BITS_PER_WORD] =
                    vec[(WORDS-1-wi)*BITS_PER_WORD +: BITS_PER_WORD];
            end
            return tmp;
        end
    endfunction

    function automatic logic [D-1:0] golden_model(
        input logic [D-1:0] in_v,
        input logic [D-1:0] bind_v,
        input logic [1:0] mode,
        input logic [$clog2(D)-1:0] param
    );
        logic [D-1:0] bound;
        begin
            bound = in_v ^ bind_v;
            case (mode)
                2'b00: golden_model = reverse_words(bound);
                2'b01: golden_model = rotate_right_each_word(bound, param);
                2'b10: golden_model = rotate_right_vec(bound, param);
                default: golden_model = bound;
            endcase
        end
    endfunction

    function automatic logic [D-1:0] make_pattern(input int seed_base);
        logic [D-1:0] tmp;
        int wi;
        logic [63:0] word_val;
        begin
            tmp = '0;
            for (wi = 0; wi < WORDS; wi++) begin
                word_val = {
                    $random(seed_base + wi * 13),
                    $random(seed_base + wi * 13 + 1)
                };
                tmp[wi*BITS_PER_WORD +: BITS_PER_WORD] = word_val;
            end
            return tmp;
        end
    endfunction

    task automatic sample_coverage(
        input logic [1:0] mode,
        input logic [$clog2(D)-1:0] param,
        input int stall_cycles
    );
        begin
            mode_seen[mode] = mode_seen[mode] + 1;
            if (stall_cycles >= 0 && stall_cycles <= 3) begin
                stall_seen[stall_cycles] = stall_seen[stall_cycles] + 1;
            end
            if (param == 0) begin
                zero_param_seen = zero_param_seen + 1;
            end
            if (param == BITS_PER_WORD) begin
                word_width_param_seen = word_width_param_seen + 1;
            end
            if (param == D - 1) begin
                full_width_minus_one_seen = full_width_minus_one_seen + 1;
            end
            if (param == D / 2) begin
                midpoint_param_seen = midpoint_param_seen + 1;
            end
        end
    endtask

    task automatic report_result(
        input string testname,
        input logic [D-1:0] expected,
        input logic [D-1:0] actual
    );
        begin
            test_count++;
            if (actual !== expected) begin
                $display("--------------------------------------------------");
                $display("FAIL: %s", testname);
                $display("Expected = %h", expected);
                $display("Actual   = %h", actual);
                $display("Time     = %0t", $time);
                $display("--------------------------------------------------");
                $fatal(1, "Test failed");
            end else begin
                pass_count++;
                $display("PASS: %s", testname);
            end
        end
    endtask

    task automatic check_output_holds_while_stalled(
        input string testname,
        input int stall_cycles
    );
        logic [D-1:0] held_out;
        int k;
        begin
            if (stall_cycles <= 0) begin
                return;
            end

            held_out = out_vec_flat;
            for (k = 0; k < stall_cycles; k++) begin
                @(posedge clk);
                if (out_vec_flat !== held_out) begin
                    $display("FAIL: %s -- output changed while stalled", testname);
                    $display("Held    = %h", held_out);
                    $display("Current = %h", out_vec_flat);
                    $fatal(1, "Output stability under stall failed");
                end
                if (out_valid !== 1'b1) begin
                    $display("FAIL: %s -- out_valid deasserted during stall", testname);
                    $fatal(1, "out_valid stability under stall failed");
                end
            end
        end
    endtask

    task automatic wait_for_output_valid(input string testname);
        int timeout_cycles;
        begin
            timeout_cycles = 0;
            while (out_valid !== 1'b1) begin
                @(posedge clk);
                timeout_cycles = timeout_cycles + 1;
                if (timeout_cycles > 20) begin
                    $display("FAIL: %s -- timed out waiting for output", testname);
                    $fatal(1, "Output timeout");
                end
            end
        end
    endtask

    task automatic run_test(
        input string testname,
        input logic [D-1:0] in_v,
        input logic [D-1:0] bind_v,
        input logic [1:0] mode,
        input logic [$clog2(D)-1:0] param,
        input int stall_cycles = 0
    );
        logic [D-1:0] expected;
        begin
            expected = golden_model(in_v, bind_v, mode, param);
            sample_coverage(mode, param, stall_cycles);

            @(posedge clk);
            while (!in_ready) @(posedge clk);

            in_vec_flat   <= in_v;
            bind_vec_flat <= bind_v;
            perm_mode     <= mode;
            perm_param    <= param;
            in_valid      <= 1'b1;

            if (stall_cycles > 0) begin
                out_ready <= 1'b0;
            end

            @(posedge clk);
            in_valid <= 1'b0;

            wait_for_output_valid(testname);
            check_output_holds_while_stalled(testname, stall_cycles);

            if (stall_cycles > 0) begin
                out_ready <= 1'b1;
                @(posedge clk);
            end

            report_result(testname, expected, out_vec_flat);
            @(posedge clk);
        end
    endtask

    task automatic run_reset_recovery_test;
        begin
            reset_recovery_seen = reset_recovery_seen + 1;
            @(posedge clk);
            while (!in_ready) @(posedge clk);
            in_vec_flat   <= {16{64'hA5A5_5A5A_0123_9876}};
            bind_vec_flat <= {16{64'h0F0F_F0F0_55AA_AA55}};
            perm_mode     <= 2'b10;
            perm_param    <= 11'd31;
            in_valid      <= 1'b1;
            @(posedge clk);
            in_valid <= 1'b0;
            reset_flush_armed <= 1'b1;

            @(posedge clk);
            rst_n <= 1'b0;
            in_valid <= 1'b0;
            out_ready <= 1'b1;
            repeat (3) @(posedge clk);
            rst_n <= 1'b1;
            repeat (2) @(posedge clk);

            if (out_valid !== 1'b0) begin
                $fatal(1, "FAIL: reset_recovery -- out_valid should clear during reset");
            end

            run_test(
                "reset_recovery_post_reset",
                {16{64'hA5A5_5A5A_0123_9876}},
                {16{64'h0F0F_F0F0_55AA_AA55}},
                2'b10,
                11'd31,
                1
            );
        end
    endtask

    task automatic run_random_suite;
        int idx;
        int stall_cycles;
        logic [1:0] mode_sel;
        logic [D-1:0] in_v;
        logic [D-1:0] bind_v;
        logic [$clog2(D)-1:0] param_val;
        string testname;
        begin
            for (idx = 0; idx < random_iterations; idx++) begin
                mode_sel = idx % 4;
                stall_cycles = idx % 4;
                in_v = make_pattern(32'h1000 + idx * 37);
                bind_v = make_pattern(32'h2000 + idx * 53);

                case (idx % 6)
                    0: param_val = '0;
                    1: param_val = BITS_PER_WORD - 1;
                    2: param_val = BITS_PER_WORD;
                    3: param_val = D - 1;
                    4: param_val = D / 2;
                    default: param_val = ($random(32'h3000 + idx * 97) & ((1 << $clog2(D)) - 1));
                endcase

                $sformat(testname, "random_case_%0d_mode_%0d", idx, mode_sel);
                run_test(testname, in_v, bind_v, mode_sel, param_val, stall_cycles);
            end
        end
    endtask

    task automatic check_coverage_summary;
        begin
            if (mode_seen[0] == 0 || mode_seen[1] == 0 || mode_seen[2] == 0 || mode_seen[3] == 0) begin
                $fatal(1, "Coverage failure: not all modes were exercised");
            end
            if (stall_seen[0] == 0 || stall_seen[1] == 0 || stall_seen[2] == 0 || stall_seen[3] == 0) begin
                $fatal(1, "Coverage failure: not all stall depths were exercised");
            end
            if (zero_param_seen == 0 || word_width_param_seen == 0 || full_width_minus_one_seen == 0 || midpoint_param_seen == 0) begin
                $fatal(1, "Coverage failure: missing key parameter corner cases");
            end
            if (reset_recovery_seen == 0) begin
                $fatal(1, "Coverage failure: reset recovery scenario not exercised");
            end
            if (accepted_txn_count != completed_txn_count + flushed_txn_count) begin
                $fatal(1, "Protocol failure: accepted/completed/flushed transaction counts differ");
            end
        end
    endtask

    task automatic print_coverage_summary;
        begin
            $display("Coverage summary:");
            $display("  mode00=%0d mode01=%0d mode10=%0d mode11=%0d",
                mode_seen[0], mode_seen[1], mode_seen[2], mode_seen[3]);
            $display("  stall0=%0d stall1=%0d stall2=%0d stall3=%0d",
                stall_seen[0], stall_seen[1], stall_seen[2], stall_seen[3]);
            $display("  param0=%0d param64=%0d param1023=%0d param512=%0d",
                zero_param_seen, word_width_param_seen, full_width_minus_one_seen, midpoint_param_seen);
            $display("  reset_recovery=%0d accepted=%0d completed=%0d flushed=%0d",
                reset_recovery_seen, accepted_txn_count, completed_txn_count, flushed_txn_count);
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

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            prev_out_valid    <= 1'b0;
            prev_out_ready    <= 1'b1;
            prev_out_vec_flat <= '0;
            if (reset_flush_armed) begin
                flushed_txn_count <= flushed_txn_count + 1;
                reset_flush_armed <= 1'b0;
            end
        end else begin
            if (prev_out_valid && !prev_out_ready) begin
                if (!out_valid) begin
                    $fatal(1, "Protocol assertion failed: out_valid dropped during stall");
                end
                if (out_vec_flat !== prev_out_vec_flat) begin
                    $fatal(1, "Protocol assertion failed: out_vec_flat changed during stall");
                end
            end

            if (in_valid && in_ready) begin
                accepted_txn_count <= accepted_txn_count + 1;
            end
            if (out_valid && out_ready) begin
                completed_txn_count <= completed_txn_count + 1;
            end

            prev_out_valid    <= out_valid;
            prev_out_ready    <= out_ready;
            prev_out_vec_flat <= out_vec_flat;
        end
    end

    initial begin
        mode_seen[0] = 0;
        mode_seen[1] = 0;
        mode_seen[2] = 0;
        mode_seen[3] = 0;
        stall_seen[0] = 0;
        stall_seen[1] = 0;
        stall_seen[2] = 0;
        stall_seen[3] = 0;
        zero_param_seen = 0;
        word_width_param_seen = 0;
        full_width_minus_one_seen = 0;
        midpoint_param_seen = 0;
        reset_recovery_seen = 0;
        accepted_txn_count = 0;
        completed_txn_count = 0;
        flushed_txn_count = 0;
        prev_out_valid = 0;
        prev_out_ready = 1;
        prev_out_vec_flat = '0;
        reset_flush_armed = 0;

        apply_reset();

        run_test(
            "full_rotate_73_basic",
            {16{64'h0123_4567_89AB_CDEF}},
            {16{64'hFFFF_0000_FFFF_0000}},
            2'b10,
            11'd73,
            0
        );

        run_test(
            "mode00_word_reverse",
            {
                64'h000F, 64'h000E, 64'h000D, 64'h000C,
                64'h000B, 64'h000A, 64'h0009, 64'h0008,
                64'h0007, 64'h0006, 64'h0005, 64'h0004,
                64'h0003, 64'h0002, 64'h0001, 64'h0000
            },
            {16{64'h0000_0000_0000_0000}},
            2'b00,
            '0,
            0
        );

        run_test(
            "mode01_per_word_rotate_1",
            {16{64'h8000_0000_0000_0001}},
            {16{64'h0000_0000_0000_0000}},
            2'b01,
            11'd1,
            0
        );

        run_test(
            "mode10_full_rotate_0",
            {16{64'hDEAD_BEEF_CAFE_F00D}},
            {16{64'h1111_2222_3333_4444}},
            2'b10,
            11'd0,
            0
        );

        run_test(
            "mode10_full_rotate_64",
            {
                64'h0011, 64'h2233, 64'h4455, 64'h6677,
                64'h8899, 64'hAABB, 64'hCCDD, 64'hEEFF,
                64'h1111, 64'h3333, 64'h5555, 64'h7777,
                64'h9999, 64'hBBBB, 64'hDDDD, 64'hFFFF
            },
            {16{64'h0}},
            2'b10,
            11'd64,
            0
        );

        run_test(
            "mode10_full_rotate_1023",
            {16{64'h0123_4567_89AB_CDEF}},
            {16{64'hFFFF_FFFF_0000_0000}},
            2'b10,
            11'd1023,
            0
        );

        run_test(
            "stall_output_while_valid",
            {16{64'h1357_9BDF_2468_ACE0}},
            {16{64'hFFFF_0000_AAAA_5555}},
            2'b10,
            11'd17,
            3
        );

        run_test(
            "mode11_passthrough_default",
            {16{64'hCAFE_BABE_FEED_FACE}},
            {16{64'hAAAA_5555_1234_4321}},
            2'b11,
            11'd511,
            2
        );

        run_test(
            "mode01_rotate_by_64_modulo",
            {16{64'h0123_4567_89AB_CDEF}},
            {16{64'h1111_1111_1111_1111}},
            2'b01,
            11'd64,
            1
        );

        run_test(
            "mode10_rotate_by_512_midpoint",
            {16{64'h89AB_CDEF_0123_4567}},
            {16{64'h0F0F_0F0F_F0F0_F0F0}},
            2'b10,
            11'd512,
            2
        );

        run_reset_recovery_test();
        run_random_suite();
        @(posedge clk);
        check_coverage_summary();

        $display("==================================================");
        $display("ALL TESTS PASSED");
        $display("Passed %0d / %0d tests", pass_count, test_count);
        print_coverage_summary();
        $display("==================================================");

        #20;
        $finish;
    end
endmodule
