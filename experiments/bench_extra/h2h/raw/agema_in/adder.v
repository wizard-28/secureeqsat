module adder (clk, rst, din, dout);
  (* AGEMA = "clock" *) input clk;
  (* AGEMA = "reset" *) input rst;
  (* AGEMA = "secure" *) input [2:0] din;
  output [1:0] dout;
  wire n0 = din[0] ^ din[1];
  wire n1 = n0 ^ din[2];
  wire n2 = din[0] & din[1];
  wire n3 = din[2] & n0;
  wire n4 = n2 ^ n3;
  assign dout[0] = n1;
  assign dout[1] = n4;
endmodule
