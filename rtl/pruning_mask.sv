// pruning_mask.sv
// Hook A bit-position pruning mask (research plan Fig 5.1 / §5.3.3).
//
// Holds the D-bit per-bit pruning mask that gates the popcount_am Hamming
// distance: pruned bit positions (mask=0) never contribute to the distance,
// which cuts dynamic energy roughly in proportion to (1 - K/D).  The mask is
// produced offline by the Python training pipeline from a per-bit
// discriminability score (Fisher ratio); see hdc_ref.make_pruning_masks.
//
// The register file matches the Python word packing exactly
// (hdc_ref.pack_u64_words): word i holds mask bits [AXI_W*i +: AXI_W], so
//     mask_out[(i+1)*AXI_W-1 -: AXI_W] = regs[i].
//
// Two write paths (Option 1 — superset of the plan's word-addressed port so the
// existing full-width core/wrapper/board load path is preserved unchanged):
//   * Word-addressed (plan §5.3.3): wr_en + wr_addr + wr_data, one AXI_W word
//     per cycle.  Future AXI-Lite 0x400 mask map / standalone Hook A loads.
//   * Full-width parallel load:     load_full + load_vec, the whole D-bit mask
//     in one cycle.  Drives the legacy mask_we/mask_vec semantics that
//     hdc_core_top / the AXI-Lite + stream wrappers / board software already use.
// load_full takes priority over wr_en in the same cycle.
//
// Reset default is all-ones (unpruned => plain Hamming distance).  Mask storage
// uses synchronous reset to avoid a huge async-reset fanout across D FFs
// (same rationale as popcount_am's prototype/mask registers).

module pruning_mask #(
    parameter int D       = 1024,
    parameter int AXI_W   = 32,
    parameter int N_WORDS = D / AXI_W,
    parameter int ADDR_W  = (N_WORDS <= 1) ? 1 : $clog2(N_WORDS)
) (
    input  logic               clk,
    input  logic               rst_n,

    // Word-addressed write port (plan §5.3.3)
    input  logic               wr_en,
    input  logic [ADDR_W-1:0]  wr_addr,
    input  logic [AXI_W-1:0]   wr_data,

    // Full-width parallel load (legacy mask_we / mask_vec path)
    input  logic               load_full,
    input  logic [D-1:0]       load_vec,

    output logic [D-1:0]       mask_out
);

    // synthesis translate_off
    initial begin
        if (N_WORDS * AXI_W != D)
            $fatal(1, "pruning_mask: N_WORDS*AXI_W (%0d) != D (%0d)",
                   N_WORDS * AXI_W, D);
    end
    // synthesis translate_on

    logic [AXI_W-1:0] regs [0:N_WORDS-1];

    integer i;
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (i = 0; i < N_WORDS; i = i + 1)
                regs[i] <= {AXI_W{1'b1}};   // default: keep all bits (unpruned)
        end else if (load_full) begin
            for (i = 0; i < N_WORDS; i = i + 1)
                regs[i] <= load_vec[i*AXI_W +: AXI_W];
        end else if (wr_en) begin
            regs[wr_addr] <= wr_data;
        end
    end

    genvar g;
    generate
        for (g = 0; g < N_WORDS; g = g + 1) begin : g_mask_out
            assign mask_out[(g+1)*AXI_W-1 -: AXI_W] = regs[g];
        end
    endgenerate

endmodule
