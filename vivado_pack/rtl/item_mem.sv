// item_mem.sv
// Read-only item-memory ROM for HDC hypervectors.  Holds N_ENTRIES D-bit
// hypervectors, initialised from a $readmemh .mem file whose layout matches
// hdc_ref.ItemMemory.export_mem_files: one 64-bit word per line, WORDS lines
// per entry (entry e occupies lines [e*WORDS .. e*WORDS+WORDS-1], word 0 first).
//
// Combinational read: drive rd_idx, get the full D-bit hypervector on rd_vec.
// Used for the channel / feature / value (CiM) tables in encoder_top.

module item_mem #(
    parameter int WORDS         = 16,
    parameter int BITS_PER_WORD = 64,
    parameter int N_ENTRIES     = 16,
    parameter int D             = WORDS * BITS_PER_WORD,
    parameter int IDX_W         = (N_ENTRIES <= 1) ? 1 : $clog2(N_ENTRIES),
    parameter     MEMFILE       = ""
) (
    input  logic [IDX_W-1:0] rd_idx,
    output logic [D-1:0]     rd_vec
);

    logic [BITS_PER_WORD-1:0] rom [0:N_ENTRIES*WORDS-1];

    initial begin
        if (MEMFILE != "") $readmemh(MEMFILE, rom);
    end

    integer w;
    int unsigned base;
    always_comb begin
        rd_vec = '0;
        base   = rd_idx * WORDS;
        for (w = 0; w < WORDS; w = w + 1)
            rd_vec[(w+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = rom[base + w];
    end

endmodule
