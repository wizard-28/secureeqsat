module factor (clk, rst, din, dout);
  (* AGEMA = "clock" *) input clk;
  (* AGEMA = "reset" *) input rst;
  (* AGEMA = "secure" *) input [2:0] din;
  output [1:0] dout;
  wire n0 = din[0] & din[1];
  wire n1 = din[0] & din[2];
  wire n2 = n0 ^ n1;
  assign dout[0] = n2;
  assign dout[1] = n2;
endmodule
