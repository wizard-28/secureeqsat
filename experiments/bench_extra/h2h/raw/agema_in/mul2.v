module mul2 (clk, rst, din, dout);
  (* AGEMA = "clock" *) input clk;
  (* AGEMA = "reset" *) input rst;
  (* AGEMA = "secure" *) input [3:0] din;
  output [3:0] dout;
  wire n0 = din[0] & din[2];
  wire n1 = din[1] & din[2];
  wire n2 = din[0] & din[3];
  wire n3 = n1 ^ n2;
  wire n4 = din[1] & din[3];
  wire n5 = n1 & n2;
  wire n6 = n4 ^ n5;
  wire n7 = n4 & n5;
  assign dout[0] = n0;
  assign dout[1] = n3;
  assign dout[2] = n6;
  assign dout[3] = n7;
endmodule
