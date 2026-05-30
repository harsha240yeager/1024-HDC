// simple_bind_rom.sv
// Example: small ROM that outputs a 1024-bit bind vector. In practice, you will
// provide a streaming bind vector, or multiple bind vectors indexed by an address.

module simple_bind_rom #(
    parameter int D = 1024
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic [7:0]       addr,      // select preloaded vector (optional)
    output logic [D-1:0]     bind_vec
);
    // For simplicity, we output a single constant pattern (synthesizable)
    // You can replace with $readmemh into an array or BRAM in actual design
    // Example filler: repeating 64'hA5A5A5A5...
    assign bind_vec = {16{64'hA5A5_A5A5_A5A5_A5A5}};

endmodule
