#!/bin/bash
# Batch 2, runs 9 and 10 (batch cap raised to $3.30 by the orchestrator, 2026-11-01): same command, same $0.80
# per-run cap, same frozen code as runs 1-8; dispositions.yaml restored before each run. A run starts only if the
# batch so far plus $0.80 stays within $3.30.
S=${S:?set S to a scratch folder holding harness2/ and sra-frozen/}
H=$S/harness2
export SRA_DIR=$S/sra-frozen
cd $H || exit 1
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
for n in 9 10; do
  total=$(spent)
  python3 -c "import sys; sys.exit(0 if $total + 0.8 <= 3.3 else 1)" || { echo "stop: batch spent $total" | tee -a $S/C2/driver.log; break; }
  git checkout -q HEAD -- contract-imported/dispositions.yaml
  run=ic-stab-$n
  echo "=== $run start $(date -u +%FT%TZ) cap 0.8" | tee -a $S/C2/driver.log
  python3 imported_checks.py run-saved --base current --head candidate --run $run --max-usd 0.8 > runs/$run.txt 2>&1
  rc=$?
  echo "=== $run exit $rc end $(date -u +%FT%TZ)" | tee -a $S/C2/driver.log
  [ -f runs/$run/saved-checks.json ] || { echo "stop: $run wrote no saved-checks.json" | tee -a $S/C2/driver.log; break; }
  cp contract-imported/dispositions.yaml $S/C2/$run.dispositions.yaml
  echo "batch cost after $run: $(spent)" | tee -a $S/C2/driver.log
done
git checkout -q HEAD -- contract-imported/dispositions.yaml
echo "=== done $(date -u +%FT%TZ)" | tee -a $S/C2/driver.log
