#!/usr/bin/env bash
# usage: run_compress.sh name   (COMPRESS, 2 shares, latencies 2 3 4, default gadget library)
H=/home/wizard-28/h2h; n=$1
export PYTHONPATH=$H/cocotb211
export PATH=$H/cocotb211/bin:$H/oss/oss-cad-suite/bin:$PATH
cd $H/compress
s=$(date +%s)
make CIRCUIT=$H/circuits/$n.txt LATS="${LATS:-2 3 4}" DS="2" PYTHON=$H/py13.sh WORK=$H/work TIMEOUT_COMPRESS=900 -j3 area > $H/logs/compress_$n.log 2>&1
echo "EXIT $? WALL $(( $(date +%s)-s )) s" >> $H/logs/compress_$n.log
