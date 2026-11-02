#!/usr/bin/env bash
H=/home/wizard-28/h2h
for n in factor square mux adder majority majority_or cmp2 add2 mul2 mux4 ascon_sbox present_sbox; do
  c=${n}_sq
  $H/run_compress.sh $c
  if grep -q "EXIT [1-9]" $H/logs/compress_$c.log && grep -q UNSAT $H/work/circuits/${c}_d2_l2/compress.log 2>/dev/null; then
    rm -rf $H/work/circuits/${c}_d2_l*; LATS="3 4" $H/run_compress.sh $c
  fi
done
echo ALLDONE > $H/logs/sq_done
