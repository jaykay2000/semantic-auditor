#!/bin/bash
# Batch 2 (after restarting the two storefront dev servers): 5 more run-saved runs, the same command and the same
# frozen code as batch 1 (run_c.sh). dispositions.yaml restored before each run. Batch cap $2.50: a run starts only
# if the batch so far plus its cap stays under $2.50; its cap is $0.80 as in batch 1, lowered only if needed to fit.
S=${S:?set S to a scratch folder holding harness2/ (a publish-prep worktree) and sra-frozen/ (an SRA copy)}
H=$S/harness2
export SRA_DIR=$S/sra-frozen
cd $H || exit 1
mkdir -p $S/C2 runs
spent() { python3 - <<PY
import json, glob
t = 0.0
for f in glob.glob("$H/runs/ic-stab-*/saved-checks.json"):
    for c in json.load(open(f))["checks"]:
        for r in c["results"].values():
            t += r.get("cost_usd") or 0
print(round(t, 4))
PY
}
for n in 6 7 8 9 10; do
  total=$(spent)
  cap=$(python3 -c "print(round(min(0.8, 2.5 - $total), 4))")
  python3 -c "import sys; sys.exit(0 if $cap >= 0.5 else 1)" || { echo "stop: batch spent $total, no room for a run" | tee -a $S/C2/driver.log; break; }
  git checkout -q HEAD -- contract-imported/dispositions.yaml
  run=ic-stab-$n
  echo "=== $run start $(date -u +%FT%TZ) cap $cap" | tee -a $S/C2/driver.log
  python3 imported_checks.py run-saved --base current --head candidate --run $run --max-usd $cap > runs/$run.txt 2>&1
  rc=$?
  echo "=== $run exit $rc end $(date -u +%FT%TZ)" | tee -a $S/C2/driver.log
  [ -f runs/$run/saved-checks.json ] || { echo "stop: $run wrote no saved-checks.json" | tee -a $S/C2/driver.log; break; }
  cp contract-imported/dispositions.yaml $S/C2/$run.dispositions.yaml
  echo "batch cost after $run: $(spent)" | tee -a $S/C2/driver.log
done
git checkout -q HEAD -- contract-imported/dispositions.yaml
echo "=== done $(date -u +%FT%TZ)" | tee -a $S/C2/driver.log
