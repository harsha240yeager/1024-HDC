`timescale 1ns/1ps
//============================================================================
// tb_stream_cosim.sv -- Co-simulation of hdc_stream_wrapper (AXI4-Stream in /
//                       out around hdc_core_top) against the Python golden.
//
// Reuses the end-to-end golden produced by:
//     python python_ref/generate_vectors.py --core
//
// Plusargs:
//   +CASES=<n>     number of cases (default 200)
//   +VECDIR=<path> golden vector directory (default python_ref/vectors/cosim_core)
//   +DEBUG         print every handshake + FSM transition (verbose event log)
//   +TRACE=<n>     detailed per-case trace for the first n cases (default 0)
//   +WAVE          dump sim/waves/stream_cosim.vcd for GUI waveform review
//
// Key signals to watch in the waveform (all under /tb_stream_cosim/dut/):
//   Stream in : s_axis_tvalid, s_axis_tready, s_axis_tdata, s_axis_tlast
//   Stream out: m_axis_tvalid, m_axis_tready, m_axis_tdata, m_axis_tlast
//   Wrapper   : dbg_fsm_state (0=collect 1=run-core 2=emit-result)
//               dbg_beat, dbg_levels_flat, dbg_core_start
//   Core      : dbg_core_busy, dbg_core_out_valid, dbg_class_idx, dbg_class_dist
//   Encoder   : dut/u_core/u_encoder/busy, .../out_valid  (inside core)
//
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

    logic [BITS_PER_WORD-1:0] proto_mem [0:N_CLASS*WORDS-1];
    logic [BITS_PER_WORD-1:0] mask_mem  [0:WORDS-1];
    logic [LVL_BITS-1:0]      lvl_mem   [0:MAX_CASES-1];
    logic [31:0]              exp_mem   [0:MAX_CASES-1];

    int    num_cases, errors, checked, trace_limit;
    bit    dbg_en, wave_en;
    string vecdir;
    int    active_case;
    logic [1:0] prev_fsm;

    // Random back-pressure on the result stream (~60% ready duty cycle)
    always @(posedge clk) begin
        if (!aresetn) m_tready <= 1'b0;
        else          m_tready <= ($urandom % 10) < 6;
    end

    // ------------------------------------------------------------------
    // Functional-verification monitors (always active when +DEBUG)
    // ------------------------------------------------------------------
    function automatic string fsm_name(input logic [1:0] s);
        case (s)
            0: return "ST_IN (collect beats)";
            1: return "ST_RUN (core busy)";
            2: return "ST_OUT (hold result)";
            default: return "ST_?";
        endcase
    endfunction

    always @(posedge clk) begin
        if (!aresetn) prev_fsm <= 0;
        else if (dbg_en && (dut.dbg_fsm_state !== prev_fsm)) begin
            $display("[DBG %0t] FSM %s -> %s  beat=%0d busy=%0b out_valid=%0b",
                     $time, fsm_name(prev_fsm), fsm_name(dut.dbg_fsm_state),
                     dut.dbg_beat, dut.dbg_core_busy, dut.dbg_core_out_valid);
            prev_fsm <= dut.dbg_fsm_state;
        end
    end

    always @(posedge clk) begin
        if (dbg_en && s_tvalid && s_tready)
            $display("[DBG %0t] S_AXIS beat accepted: tdata=0x%08h tlast=%0b beat=%0d ready=%0b",
                     $time, s_tdata, s_tlast, dut.dbg_beat, s_tready);
    end

    always @(posedge clk) begin
        if (dbg_en && dut.dbg_core_start)
            $display("[DBG %0t] CORE START  levels_flat=0x%0h  (80-bit window latched)",
                     $time, dut.dbg_levels_flat);
    end

    always @(posedge clk) begin
        if (dbg_en && dut.dbg_core_out_valid)
            $display("[DBG %0t] CORE DONE   class_idx=%0d class_dist=%0d",
                     $time, dut.dbg_class_idx, dut.dbg_class_dist);
    end

    always @(posedge clk) begin
        if (dbg_en && m_tvalid && m_tready)
            $display("[DBG %0t] M_AXIS result beat: tdata=0x%08h (idx=%0d dist=%0d) tlast=%0b",
                     $time, m_tdata, m_tdata[16 +: IDX_W], m_tdata[DIST_W-1:0], m_tlast);
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
            if (trace_limit > 0)
                $display("[TRACE] --- loading %0d prototypes + pruning mask ---", N_CLASS);
            for (kcls = 0; kcls < N_CLASS; kcls++) begin
                proto_idx <= kcls[IDX_W-1:0];
                proto_vec <= assemble_proto(kcls);
                proto_we  <= 1'b1;
                @(posedge clk);
                if (trace_limit > 0)
                    $display("[TRACE]   LOAD_PROTO class=%0d", kcls);
            end
            proto_we <= 1'b0;
            mask_vec <= assemble_mask();
            mask_we  <= 1'b1;
            @(posedge clk);
            mask_we  <= 1'b0;
            if (trace_limit > 0)
                $display("[TRACE]   LOAD_MASK done");
            @(posedge clk);
        end
    endtask

    task automatic send_window(input logic [LVL_BITS-1:0] lv);
        int bt, gap;
        logic [TDATA_W-1:0] beat_data;
        begin
            if (active_case < trace_limit)
                $display("[TRACE] case %0d SEND window levels_flat=0x%0h", active_case, lv);
            for (bt = 0; bt < IN_BEATS; bt++) begin
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
                    if (s_tready) break;
                end
                if (active_case < trace_limit)
                    $display("[TRACE]   beat %0d/%0d sent tdata=0x%08h tlast=%0b (gap=%0d)",
                             bt+1, IN_BEATS, beat_data, s_tlast, gap);
                s_tvalid <= 1'b0;
                s_tlast  <= 1'b0;
            end
        end
    endtask

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
            if (c < trace_limit) begin
                $display("[TRACE] case %0d RECV result idx=%0d dist=%0d (golden idx=%0d dist=%0d) %s",
                         c, got_idx, got_dist, exp_idx, exp_dist,
                         ((got_idx === exp_idx) && (got_dist === exp_dist)) ? "OK" : "MISMATCH");
            end
            if ((got_idx !== exp_idx) || (got_dist !== exp_dist) || !m_tlast) begin
                errors++;
                $display("--------------------------------------------------");
                $display("FAIL case %0d  (tlast=%0b)", c, m_tlast);
                $display("  expected idx=%0d dist=%0d", exp_idx, exp_dist);
                $display("  got      idx=%0d dist=%0d", got_idx, got_dist);
                $display("  dbg: fsm=%s levels=0x%0h", fsm_name(dut.dbg_fsm_state), dut.dbg_levels_flat);
                $display("--------------------------------------------------");
            end
        end
    endtask

    task automatic print_signal_guide;
        begin
            $display("");
            $display("--- Functional verification signal guide ---");
            $display("  S_AXIS (window in, 3 beats):");
            $display("    s_axis_tvalid/tready  handshake; transfer when both high");
            $display("    s_axis_tdata          32-bit level chunk (little-endian pack)");
            $display("    s_axis_tlast          1 on final beat of each window");
            $display("  M_AXIS (result out, 1 beat/window):");
            $display("    m_axis_tdata          (class_idx<<16)|class_dist");
            $display("  Wrapper FSM (dbg_fsm_state):");
            $display("    0 ST_IN   collect %0d beats into dbg_levels_flat", IN_BEATS);
            $display("    1 ST_RUN  hdc_core_top running (~24 clk) dbg_core_busy=1");
            $display("    2 ST_OUT  hold result until m_axis_tready");
            $display("  Core pulses:");
            $display("    dbg_core_start      1-cycle: window latched, encode begins");
            $display("    dbg_core_out_valid  1-cycle: AM decision ready");
            $display("  Waveform: add +WAVE or run sim/run_stream_cosim_debug.do");
            $display("    Key paths: dut/dbg_*  dut/u_core/u_encoder/*  dut/u_core/u_am/*");
            $display("---------------------------------------------");
            $display("");
        end
    endtask

    initial begin
        errors = 0; checked = 0; trace_limit = 0; active_case = 0;
        dbg_en = 0; wave_en = 0;
        proto_we = 0; proto_idx = '0; proto_vec = '0;
        mask_we = 0; mask_vec = '0;
        s_tvalid = 0; s_tdata = '0; s_tlast = 0;
        prev_fsm = 0;

        if (!$value$plusargs("CASES=%d", num_cases)) num_cases = 200;
        if (!$value$plusargs("VECDIR=%s", vecdir))   vecdir = "python_ref/vectors/cosim_core";
        if (!$value$plusargs("TRACE=%d", trace_limit)) trace_limit = 0;
        if ($test$plusargs("DEBUG")) dbg_en = 1;
        if ($test$plusargs("WAVE"))  wave_en = 1;
        if (num_cases > MAX_CASES) num_cases = MAX_CASES;

        if (wave_en) begin
            $display("[WAVE] dumping sim/waves/stream_cosim.vcd");
            $dumpfile("sim/waves/stream_cosim.vcd");
            $dumpvars(0, tb_stream_cosim);
        end

        $display("==================================================");
        $display("tb_stream_cosim: AXI4-Stream + hdc_core_top vs golden");
        $display("  VECDIR = %s", vecdir);
        $display("  CASES  = %0d   (D=%0d, %0d beats/window, N_CLASS=%0d)",
                 num_cases, D, IN_BEATS, N_CLASS);
        $display("  DEBUG  = %0d   TRACE(first N cases) = %0d   WAVE = %0d",
                 dbg_en, trace_limit, wave_en);
        $display("==================================================");
        print_signal_guide();

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
            active_case = c;
            fork
                send_window(lvl_mem[c]);
                recv_result(c);
            join
            if (!dbg_en && (c % 50) == 49)
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
