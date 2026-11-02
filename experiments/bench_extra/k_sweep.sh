#!/usr/bin/env bash
# seqc's secure optimum for several frontier widths k (300 s cap per run). From the repo root.
F=experiments/frontend; O=experiments/bench_extra/k_sweep.txt; : > $O
for spec in examples/factor examples/square examples/mux examples/adder examples/majority complex/cmp2 complex/mul2 complex/mux4 complex/ascon_sbox complex/add2 complex/present_sbox large/majority_or; do
  n=$(basename $spec); row="$n"
  for k in 2 4 8 16; do
    r=$(timeout 300 uv run python experiments/bench_extra/seqc_gadgets.py $F/$spec.sec --k $k --iters 4 2>/dev/null | sed -E 's/.*enforced gadgets=([0-9]+) rnd=([0-9]+) cost=([0-9]+).*/\3(\1g)/')
    row="$row  k$k=${r:-TIMEOUT}"
  done
  echo "$row" >> $O
done
echo DONE >> $O
