// xor_permute_top.sv
// Top-level bit-parallel XOR + Permute pipeline (D = WORDS * BITS_PER_WORD)
// Chunking: WORDS x BITS_PER_WORD (default 16 x 64 = 1024)

module xor_permute_top #(
    parameter int WORDS = 16,
    parameter int BITS_PER_WORD = 64,
    parameter int D = WORDS * BITS_PER_WORD
) (
    input  logic                 clk,
    input  logic                 rst_n,

    // Input interface (flattened)
    input  logic                 in_valid,
    output logic                 in_ready,
    input  logic [D-1:0]         in_vec_flat,

    // Bind vector (can be constant or from host/BRAM). Flat for simplicity.
    input  logic [D-1:0]         bind_vec_flat,

    // Permutation control
    input  logic [1:0]           perm_mode,   // 00=wire,01=per-word rotate,10=full rotate,11=reserved
    input  logic [$clog2(D)-1:0] perm_param,  // rotate amount 0..D-1 (only low bits used per mode)

    // Output interface
    output logic                 out_valid,
    input  logic                 out_ready,
    output logic [D-1:0]         out_vec_flat
) ;

    // -------------------------
    // Stage 0: Input latch
    // -------------------------
    logic                        s0_valid;
    logic [D-1:0]                s0_vec_flat;
    logic [D-1:0]                s0_bind_flat;
    logic [1:0]                  s0_perm_mode;
    logic [$clog2(D)-1:0]        s0_perm_param;

    // -------------------------
    // Stage 1: XOR binding
    // -------------------------
    logic [D-1:0]                s1_vec_flat;
    logic                        s1_valid;
    logic [1:0]                  s1_perm_mode;
    logic [$clog2(D)-1:0]        s1_perm_param;

    logic [BITS_PER_WORD-1:0]    s0_data_w [0:WORDS-1];
    logic [BITS_PER_WORD-1:0]    s0_bind_w [0:WORDS-1];
    logic [BITS_PER_WORD-1:0]    s0_xor_w  [0:WORDS-1];
    logic [D-1:0]                s0_xor_flat;

    // -------------------------
    // Stage 2: Permutation
    // -------------------------
    logic [D-1:0]                s2_vec_flat;
    logic                        s2_valid;

    genvar i;
    generate
        for (i = 0; i < WORDS; i++) begin : XOR_WORDS
            assign s0_data_w[i] = s0_vec_flat[(i+1)*BITS_PER_WORD-1 -: BITS_PER_WORD];
            assign s0_bind_w[i] = s0_bind_flat[(i+1)*BITS_PER_WORD-1 -: BITS_PER_WORD];
            assign s0_xor_w[i]  = s0_data_w[i] ^ s0_bind_w[i];
            assign s0_xor_flat[(i+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = s0_xor_w[i];
        end
    endgenerate

    // Only allow one transaction in flight through this simple pipeline.
    assign in_ready = !(s0_valid || s1_valid || s2_valid || out_valid);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s0_valid      <= 1'b0;
            s0_vec_flat   <= '0;
            s0_bind_flat  <= '0;
            s0_perm_mode  <= '0;
            s0_perm_param <= '0;
        end else begin
            if (in_valid && in_ready) begin
                s0_vec_flat   <= in_vec_flat;
                s0_bind_flat  <= bind_vec_flat;
                s0_perm_mode  <= perm_mode;
                s0_perm_param <= perm_param;
                s0_valid      <= 1'b1;
            end else begin
                s0_valid <= 1'b0;
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s1_valid      <= 1'b0;
            s1_vec_flat   <= '0;
            s1_perm_mode  <= '0;
            s1_perm_param <= '0;
        end else begin
            s1_valid <= s0_valid;
            if (s0_valid) begin
                s1_vec_flat   <= s0_xor_flat;
                s1_perm_mode  <= s0_perm_mode;
                s1_perm_param <= s0_perm_param;
            end
        end
    end

    permute_stage #(
        .WORDS(WORDS),
        .BITS_PER_WORD(BITS_PER_WORD)
    ) perm0 (
        .clk(clk),
        .rst_n(rst_n),
        .in_valid(s1_valid),
        .in_vec_flat(s1_vec_flat),
        .mode(s1_perm_mode),
        .param(s1_perm_param),
        .out_valid(s2_valid),
        .out_vec_flat(s2_vec_flat)
    ) ;

    // -------------------------
    // Stage 3: Output register + handshake
    // -------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid    <= 1'b0;
            out_vec_flat <= '0;
        end else begin
            if (s2_valid && (!out_valid || out_ready)) begin
                out_vec_flat <= s2_vec_flat;
                out_valid    <= 1'b1;
            end else if (out_valid && out_ready) begin
                out_valid <= 1'b0;
            end
        end
    end

endmodule



