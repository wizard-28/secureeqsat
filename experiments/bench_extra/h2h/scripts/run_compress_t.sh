#!/usr/bin/env bash
# quiet timing pass: COMPRESS (sims skipped), one program at a time, solver time from stats.json
H=/home/wizard-28/h2h; n=$1; L=$2
export PYTHONPATH=$H/cocotb211 PATH=$H/cocotb211/bin:$H/oss/oss-cad-suite/bin:$PATH
cd $H/compress
s=$(date +%s%3N)
make CIRCUIT=$H/circuits/$n.txt LATS="$L" DS="2" PYTHON=$H/py13.sh WORK=$H/work_t TIMEOUT_COMPRESS=900 SKIP_BEH_SIMU=1 SKIP_STRUCT_SIMU=1 area > $H/logs/ct_$n.log 2>&1
echo "$n EXIT $? WALL_MS $(( $(date +%s%3N)-s ))" >> $H/logs/ct_all.txt
