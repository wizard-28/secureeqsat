module muxr (clk, rst, din, dout);
  (* AGEMA = "clock" *) input clk;
  (* AGEMA = "reset" *) input rst;
  (* AGEMA = "secure" *) input [2:0] din;
  output reg [1:0] dout;
  wire n0 = din[0] & din[1];
  wire n1 = ~din[0];
  wire n2 = n1 & din[2];
  wire n3 = n0 ^ n2;
  always @(posedge clk) begin dout[0] <= n3; dout[1] <= n3; end
endmodule
