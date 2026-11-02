#!/usr/bin/env bash
# seqc compile time per program, one at a time (quiet machine). Run from the repo root.
F=experiments/frontend; O=experiments/bench_extra/timing/seqc_times.txt; : > $O
for spec in "examples/factor:" "examples/square:" "examples/mux:" "examples/adder:" "examples/majority:" "large/majority_or:" "complex/cmp2:" "complex/add2:" "complex/mul2:" "complex/mux4:--k 2 --iters 4" "complex/ascon_sbox:--k 2 --iters 4" "complex/present_sbox:"; do
  f=${spec%%:*}; a=${spec#*:}
  uv run python experiments/bench_extra/seqc_gadgets.py $F/$f.sec $a >> $O 2>&1
done
echo DONE >> $O
