module square (clk, rst, din, dout);
  (* AGEMA = "clock" *) input clk;
  (* AGEMA = "reset" *) input rst;
  (* AGEMA = "secure" *) input [1:0] din;
  output [1:0] dout;
  wire n0 = din[0] ^ din[1];
  wire n1 = n0 & n0;
  assign dout[0] = n1;
  assign dout[1] = n1;
endmodule
