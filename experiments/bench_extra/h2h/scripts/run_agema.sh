#!/usr/bin/env bash
# usage: run_agema.sh name scheme   (AGEMA, first order = 2 shares, naive method)
H=/home/wizard-28/h2h; n=$1; sc=$2
export PATH=$H/oss/oss-cad-suite/bin:$PATH LD_LIBRARY_PATH=$H/AGEMA/AGEMA/lib
W=$H/agema_work/$n; mkdir -p $W; cp $H/agema_in/$n.v $W/in.v
cd $H/AGEMA/AGEMA
sed -e "s|\$VERILOG_FILES|$W/in.v|" -e "s|\$TOP_MODULE|$n|g" -e "s|result_netlist.v|$W/net.v|" -e "s|LIB/|Yosys/LIB/|g" Yosys/sythesize.ys > $W/synth.ys
yosys -q -s $W/synth.ys -l $W/yosys.log > /dev/null 2>&1 || { echo "YOSYS FAIL"; exit 1; }
sed -i -e "/(\* keep_hierarchy/d" -e "/(\* src =/d" -e "/(\* top =/d" $W/net.v
sed -i -E "/^ *wire (\[[0-9:]+\] )?(clk|rst|din|dout);/d" $W/net.v
s=$(date +%s%3N)
cd $W && $H/AGEMA/AGEMA/bin/release/AGEMA -lf $H/AGEMA/AGEMA/cell/Library.txt -df $W/net.v -mn $n -mt naive -sc $sc -so 1 > $W/agema_$sc.log 2>&1
echo "EXIT $? MS $(( $(date +%s%3N)-s ))" >> $W/agema_$sc.log
