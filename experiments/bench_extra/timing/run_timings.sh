#!/usr/bin/env bash
# Re-measure the paper's timing claims one at a time on a quiet machine.
# usage: bash experiments/bench_extra/timing/run_timings.sh  (from the repository root)
set -u
T=experiments/bench_extra/timing
{ echo "machine: $(uname -srm), $(nproc) cores"; echo "date: $(date -Iseconds)"; echo "load before: $(cut -d' ' -f1-3 /proc/loadavg)"; } > $T/machine.txt
uv run python experiments/labeller/measure.py > $T/labeller.txt 2>&1
uv run python experiments/resharing/run.py --scale > $T/scale.txt 2>&1
uv run python experiments/composition/run_composition.py > $T/composition.txt 2>&1
echo "load after: $(cut -d' ' -f1-3 /proc/loadavg)" >> $T/machine.txt
echo DONE >> $T/machine.txt
