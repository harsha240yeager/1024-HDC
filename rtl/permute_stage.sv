module permute_stage #(
    parameter int WORDS = 16,
    parameter int BITS_PER_WORD = 64,
    parameter int D = WORDS * BITS_PER_WORD
) (
    input  logic                         clk,
    input  logic                         rst_n,
    input  logic                         in_valid,
    input  logic [D-1:0]                 in_vec_flat,
    input  logic [1:0]                   mode,
    input  logic [$clog2(D)-1:0]         param,
    output logic                         out_valid,
    output logic [D-1:0]                 out_vec_flat
) ;

    // Unpack
    logic [BITS_PER_WORD-1:0] in_w [0:WORDS-1];
    genvar j;
    generate
        for (j = 0; j < WORDS; j++) begin : UNPACK
            assign in_w[j] = in_vec_flat[(j+1)*BITS_PER_WORD-1 -: BITS_PER_WORD];
        end
    endgenerate

    // Temporary combinational array
    logic [BITS_PER_WORD-1:0] tmp [0:WORDS-1];

    // Module-scope variables for ModelSim compatibility
    integer k;
    integer bitrot;
    integer rot;
    integer word_rot;
    integer bit_rot;
    integer src0;
    integer src1;

    // Example fixed permute map: reverse the word order
    function automatic int fixed_word_map(input int out_word_idx);
        fixed_word_map = (WORDS - 1) - out_word_idx;
    endfunction

    always_comb begin
        // Defaults
        for (k = 0; k < WORDS; k = k + 1) begin
            tmp[k] = in_w[k];
        end

        case (mode)
            2'b00: begin
                // Fixed word reverse
                for (k = 0; k < WORDS; k = k + 1) begin
                    tmp[k] = in_w[fixed_word_map(k)];
                end
            end

            2'b01: begin
                // Rotate each word by param % BITS_PER_WORD
                bitrot = param % BITS_PER_WORD;
                for (k = 0; k < WORDS; k = k + 1) begin
                    if (bitrot == 0) begin
                        tmp[k] = in_w[k];
                    end else begin
                        tmp[k] = (in_w[k] >> bitrot) |
                                 (in_w[k] << (BITS_PER_WORD - bitrot));
                    end
                end
            end

            2'b10: begin
                // Full D-bit rotate
                rot      = param % D;
                word_rot = rot / BITS_PER_WORD;
                bit_rot  = rot % BITS_PER_WORD;

                for (k = 0; k < WORDS; k = k + 1) begin
                    src0 = (k + word_rot) % WORDS;
                    src1 = (k + word_rot + 1) % WORDS;

                    if (bit_rot == 0) begin
                        tmp[k] = in_w[src0];
                    end else begin
                        tmp[k] = (in_w[src0] >> bit_rot) |
                                 (in_w[src1] << (BITS_PER_WORD - bit_rot));
                    end
                end
            end

            default: begin
                for (k = 0; k < WORDS; k = k + 1) begin
                    tmp[k] = in_w[k];
                end
            end
        endcase
    end

    // Pack temporary output
    logic [D-1:0] tmp_flat;
    generate
        for (j = 0; j < WORDS; j++) begin : PACK_TMP
            assign tmp_flat[(j+1)*BITS_PER_WORD-1 -: BITS_PER_WORD] = tmp[j];
        end
    endgenerate

    // Register output
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid    <= 1'b0;
            out_vec_flat <= '0;
        end else begin
            if (in_valid) begin
                out_vec_flat <= tmp_flat;
                out_valid    <= 1'b1;
            end else if (out_valid) begin
                out_valid <= 1'b0;
            end
        end
    end

endmodule


