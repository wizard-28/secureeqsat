module cmp2 (clk, rst, din, dout);
  (* AGEMA = "clock" *) input clk;
  (* AGEMA = "reset" *) input rst;
  (* AGEMA = "secure" *) input [3:0] din;
  output [1:0] dout;
  wire n0 = ~din[3];
  wire n1 = din[1] & n0;
  wire n2 = din[1] ^ din[3];
  wire n3 = ~n2;
  wire n4 = ~din[2];
  wire n5 = din[0] & n4;
  wire n6 = n3 & n5;
  wire n7 = n1 ^ n6;
  wire n8 = din[0] ^ din[2];
  wire n9 = ~n8;
  wire n10 = n3 & n9;
  assign dout[0] = n7;
  assign dout[1] = n10;
endmodule
