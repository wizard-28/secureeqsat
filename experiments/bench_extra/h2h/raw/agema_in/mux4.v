module mux4 (clk, rst, din, dout);
  (* AGEMA = "clock" *) input clk;
  (* AGEMA = "reset" *) input rst;
  (* AGEMA = "secure" *) input [5:0] din;
  output [1:0] dout;
  wire n0 = din[0] ^ din[1];
  wire n1 = din[4] & n0;
  wire n2 = din[0] ^ n1;
  wire n3 = din[2] ^ din[3];
  wire n4 = din[4] & n3;
  wire n5 = din[2] ^ n4;
  wire n6 = n2 ^ n5;
  wire n7 = din[5] & n6;
  wire n8 = n2 ^ n7;
  assign dout[0] = n8;
  assign dout[1] = n8;
endmodule
