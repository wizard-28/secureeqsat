module muxn (clk, din, dout);
  (* AGEMA = "clock" *) input clk;
  (* AGEMA = "secure" *) input [2:0] din;
  output [1:0] dout;
  wire n0 = din[0] & din[1];
  wire n1 = ~din[0];
  wire n2 = n1 & din[2];
  wire n3 = n0 ^ n2;
  assign dout[0] = n3;
  assign dout[1] = n3;
endmodule
