#!/bin/bash
# 5 stability runs of run-saved; dispositions.yaml restored to publish-prep's before each run so every run starts
# from the same stored state. Stops if the summed result-level cost reaches $3.2 (so a 6th $0.8 cap could not pass $4).
S=${S:?set S to a scratch folder holding harness/ (a publish-prep worktree) and sra-frozen/ (an SRA copy)}
H=$S/harness
export SRA_DIR=$S/sra-frozen
cd $H || exit 1
mkdir -p $S/C runs
for n in 1 2 3 4 5; do
  git checkout -q publish-prep -- contract-imported/dispositions.yaml
  run=ic-stab-$n
  echo "=== $run start $(date -u +%FT%TZ)" | tee -a $S/C/driver.log
  python3 imported_checks.py run-saved --base current --head candidate --run $run --max-usd 0.8 > runs/$run.txt 2>&1
  rc=$?
  echo "=== $run exit $rc end $(date -u +%FT%TZ)" | tee -a $S/C/driver.log
  [ -f runs/$run/saved-checks.json ] || { echo "stop: $run wrote no saved-checks.json" | tee -a $S/C/driver.log; break; }
  cp contract-imported/dispositions.yaml $S/C/$run.dispositions.yaml
  total=$(python3 - <<PY
import json, glob
t = 0.0
for f in glob.glob("$H/runs/ic-stab-*/saved-checks.json"):
    d = json.load(open(f))
    for c in d["checks"]:
        for r in c["results"].values():
            t += r.get("cost_usd") or 0
print(round(t, 4))
PY
)
  echo "summed cost after $run: $total" | tee -a $S/C/driver.log
  python3 -c "import sys; sys.exit(0 if $total < 3.2 else 1)" || { echo "stop: budget" | tee -a $S/C/driver.log; break; }
done
git checkout -q publish-prep -- contract-imported/dispositions.yaml
echo "=== done $(date -u +%FT%TZ)" | tee -a $S/C/driver.log
