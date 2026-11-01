"""Remove each imported-check safeguard in turn and show the test that pins it goes red (then restore the file).

    python3 scripts/mutate_imported_checks.py            # prints one line per safeguard; exit 1 if any survived

A mutation "survives" when its test still passes with the safeguard removed: that test does not guard anything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CV = "src/semaudit/imported/convert.py"
RC = "src/semaudit/imported/recheck.py"
MEM = "src/semaudit/decide/memory.py"
SV = "src/semaudit/imported/saved.py"
RT = "src/semaudit/models/router.py"

# (safeguard, file, original text, mutated text, test that must go red)
MUTATIONS = [
    ("coverage: nothing left out", CV, "    if left and not errs:", "    if False:",
     "test_coverage_refuses_a_dropped_instruction"),
    ("coverage: verbatim clauses", CV, "        at = text.find(piece, pos)\n", "        at = max(text.find(piece, pos), 0)\n",
     "test_coverage_refuses_a_rewritten_clause"),
    ("verbs: adapter has it", CV, "        if do not in usable:", "        if False:", "test_unknown_verb_is_refused"),
    ("verb cues: no fabricated mapping", CV, "        elif do not in spec.implied_ok and not cue_matches(",
     "        elif False and not cue_matches(", "test_fabricated_mapping_is_refused"),
    ("missing verb that exists", CV, '            if reason == "no_verb" and missing in verbs:', "            if False:",
     "test_missing_verb_that_exists_is_refused"),
    ("action maps or is unmapped", CV, "            if not mapped and not reason:", "            if False:",
     "test_action_clause_must_map_or_be_unmapped"),
    ("material field needs a source", CV, "        if ci == -1 and fid in spec.material_fields and",
     "        if False and fid in spec.material_fields and", "test_material_field_needs_a_source"),
    ("catalog", CV, "    if lf is None:\n        return []", "    if True:\n        return []",
     "test_catalog_is_enforced"),
    ("invariant copies no figures", CV, "    if copied:", "    if False:", "test_invariant_may_not_copy_the_quote"),
    ("invariant surface reached", CV, "        elif not reached(inv_surface,", "        elif False and not reached(inv_surface,",
     "test_invariant_surface_must_be_reached"),
    ("suspect observation", CV, "    sus = suspect_observations(clauses, spec)", "    sus = []",
     "test_suspect_observation_is_partially_converted"),
    ("adapter_gap classification", CV, '    if conv.gaps:\n        conv.status = "adapter_gap"',
     '    if False:\n        conv.status = "adapter_gap"', "test_missing_verb_is_an_adapter_gap"),
    ("prerequisites only implied_ok", CV, "            if pre in spec.implied_ok:", "            if True:",
     "test_prerequisite_is_inserted_only_when_implied_ok"),
    ("fail closed: not_converted", CV, '    if errs:\n        conv = Conversion(status="not_converted"',
     '    if False:\n        conv = Conversion(status="not_converted"', "test_a_draft_that_keeps_failing_is_not_converted"),
    ("judge never sees the quote", RC, '            "invariant": check.invariant.statement,',
     '            "invariant": check.invariant.statement, "finding": check.source.shown,',
     "test_judge_never_sees_the_original_quote"),
    ("refused step fails the replay", RC, "            if s.note and re.search(pat, s.note, re.I):",
     "            if False:", "test_replay_fails_when_the_app_refused_a_step"),
    ("surface must be captured", RC, "    if not msgs:\n        reasons.append", "    if False:\n        reasons.append",
     "test_replay_fails_without_the_surface"),
    ("no majority -> not_measurable", RC, '    outcome = top if n * 2 > judgments else "not_measurable"',
     "    outcome = top", "test_no_majority_is_not_measurable"),
    ("quotes checked against capture", RC, "    found, refused, moved = check_citations(f, {story.persona: story})",
     "    found, refused, moved = {story.persona: [(c.event_id, check.invariant.surface, c.event_id, c.quote) "
     "for c in f.cited]}, [], []", "test_quote_not_in_the_capture_is_unverified"),
    ("quotes on the invariant's surface", RC, "    on_surface = [c for c in found.get(story.persona, []) if c[1] == "
     "check.invariant.surface]", "    on_surface = list(found.get(story.persona, []))",
     "test_quote_on_another_surface_is_not_evidence"),
    ("record values checked", RC, "        elif not _same(val, v):", "        elif False:",
     "test_record_value_must_match"),
    ("bare labels neutral, false quotes not", RC, '    bare = [r for r in refused if "states no figure" in r]',
     "    bare = list(refused)", "test_bare_label_is_not_counted_against_the_evidence"),
    ("failed replay never judged", RC, '    if rs["status"] != "succeeded":', "    if False:",
     "test_failed_replay_is_never_judged"),
    ("owner approval before replay", RC, "    if approved_only:", "    if False:",
     "test_replay_refuses_an_unapproved_check"),
    ("fix needs verified evidence", MEM, '        if head["evidence"]["status"] != "verified":', "        if False:",
     "test_fix_needs_verified_evidence_not_an_absence"),
    ("memory keeps checks", MEM, '    if data.get("checks"):                    # imported checks (semaudit',
     '    if False:                    # imported checks (semaudit', "test_memory_keeps_checks_beside_issues"),
 ("saved check runs only at its approved digest", SV, '        if c.digest() != a.get("hash"):',
     "        if False:", "test_saved_checks_load_from_storage_and_refuse_a_changed_check"),
    ("pass needs verified evidence", RC, '    if assertion["outcome"] != "pass" or evidence == "verified":',
     "    if True:", "test_pass_needs_verified_evidence"),
    ("role reply cap applied", RT, '(max_completion_tokens or spec.get("max_completion_tokens")',
     "(max_completion_tokens", "test_role_cap_and_retries_come_from_the_role"),
    ("role retries bounded", RT, '        retries = int(spec.get("unreadable_retries", UNREADABLE_RETRIES))',
     "        retries = 99", "test_role_retries_are_bounded"),
]


def run_test(name: str) -> bool:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                        "tests/test_imported_checks.py", "tests/test_router_providers.py", "-k", name], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    survived = 0
    for what, rel, old, new, test in MUTATIONS:
        p = ROOT / rel
        src = p.read_text()
        if src.count(old) != 1:
            print(f"ERROR   {what}: the original text is not found exactly once in {rel}")
            survived += 1
            continue
        assert run_test(test), f"{test} fails before mutation"
        try:
            p.write_text(src.replace(old, new))
            passed = run_test(test)
        finally:
            p.write_text(src)
        survived += passed
        print(f"{'SURVIVED' if passed else 'red    '} {what:40} {test}")
    print(f"{len(MUTATIONS)} mutations, {survived} survived")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
