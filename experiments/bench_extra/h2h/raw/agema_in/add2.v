module add2 (clk, rst, din, dout);
  (* AGEMA = "clock" *) input clk;
  (* AGEMA = "reset" *) input rst;
  (* AGEMA = "secure" *) input [4:0] din;
  output [2:0] dout;
  wire n0 = din[0] ^ din[2];
  wire n1 = n0 ^ din[4];
  wire n2 = din[1] ^ din[3];
  wire n3 = din[0] & din[2];
  wire n4 = din[4] & n0;
  wire n5 = n3 ^ n4;
  wire n6 = n2 ^ n5;
  wire n7 = din[1] & din[3];
  wire n8 = n5 & n2;
  wire n9 = n7 ^ n8;
  assign dout[0] = n1;
  assign dout[1] = n6;
  assign dout[2] = n9;
endmodule
