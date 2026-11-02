module majority (clk, rst, din, dout);
  (* AGEMA = "clock" *) input clk;
  (* AGEMA = "reset" *) input rst;
  (* AGEMA = "secure" *) input [2:0] din;
  output [1:0] dout;
  wire n0 = din[0] & din[1];
  wire n1 = din[0] ^ din[1];
  wire n2 = din[2] & n1;
  wire n3 = n0 ^ n2;
  assign dout[0] = n3;
  assign dout[1] = n3;
endmodule
