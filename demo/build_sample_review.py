"""Build the hosted sample release review: Northbound 2.3 -> 2.4 as a static folder GitHub Pages can serve.

    python3 demo/build_sample_review.py            # writes docs/sample-review/ (index.html + the captures it shows)

Owner decision 2026-11-01: publish this one review as the "live product" judges can open. Its URL, once the owner has
turned Pages on (source: main, /docs), is https://jaykay2000.github.io/semantic-auditor/sample-review/ .

Northbound is a fictional travel app built for testing SRA, with synthetic travellers, so the page carries no user
data. The page is SRA's own release review page (semaudit.report.page.build), unchanged except for one thing: the
review embeds the absolute paths of the run, the contract and the adapter, and those are rewritten relative to the
repository. Then the folder is checked, and nothing is written if any check fails:
  * no absolute home or temp path (the same pattern as tests/test_demo_assets_clean.py);
  * no name of a coding agent or a non-Meta model (same pattern; the CSS property "cursor:" is not a name);
  * no network address other than the fictional app's own 127.0.0.1 base URL, and no external script or stylesheet;
  * every capture the page references is in the folder.
tests/test_sample_review.py runs the same checks on the committed folder.
"""
import json
import pathlib
import re
import shutil
import sys
import tempfile

SRA = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRA / 'src'))
sys.path.insert(0, str(SRA / 'tests'))

# The review run with the judge self-check on (docs/evidence/judge-self-check-2026-11-02, run 1): the same
# Northbound 2.3 -> 2.4 review as runs/e2e-2, whose verdicts it matches, plus the self-check result.
REVIEW = SRA / 'runs' / 'sc-live-1' / 'review-2.3-2.4.json'
OUT = SRA / 'docs' / 'sample-review'
URL = 'https://jaykay2000.github.io/semantic-auditor/sample-review/'


def problems(folder):
    """What would make the folder unsafe or broken to publish; [] when it is fine."""
    from test_demo_assets_clean import LOCAL_PATH, NAMES
    out = []
    page = (folder / 'index.html').read_text(encoding='utf-8')
    for n, line in enumerate(page.splitlines(), 1):
        if LOCAL_PATH.search(line):
            out.append(f'index.html:{n}: local path')
        if NAMES.search(re.sub(r'\bcursor\s*:', '', line)):
            out.append(f'index.html:{n}: agent or non-Meta model name: {NAMES.search(re.sub(r"cursor\s*:", "", line)).group(0)}')
    for addr in set(re.findall(r'https?://[^\s"\'<>)]+', page)):
        if not addr.startswith('http://127.0.0.1'):
            out.append(f'index.html: network address {addr}')
    if re.search(r'<(script|link)[^>]+(src|href)=["\']?(https?:)?//', page):
        out.append('index.html: external script or stylesheet')
    refs = set()
    for m in re.finditer(r'"screenshot":\s*"([^"]+\.png)"', page):
        refs.add(m.group(1))
    for rel in sorted(refs):
        if not (folder / rel).is_file():
            out.append(f'missing capture {rel}')
    if (folder / 'MISSING.txt').exists():
        out.append('the page builder reported missing captures (MISSING.txt)')
    return out


def main():
    from semaudit.report.page import build
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp) / 'sample-review'
        index = build(REVIEW, tmp)
        page = index.read_text(encoding='utf-8')
        root = str(SRA) + '/'
        page = page.replace(json.dumps(root)[1:-1], '').replace(root, '')
        index.write_text(page, encoding='utf-8')
        found = problems(tmp)
        if found:
            sys.exit('refusing to write docs/sample-review:\n  ' + '\n  '.join(found))
        if OUT.exists():
            shutil.rmtree(OUT)
        shutil.copytree(tmp, OUT)
    files = [p for p in OUT.rglob('*') if p.is_file()]
    print(f'wrote {OUT.relative_to(SRA)}: {len(files)} files, {sum(p.stat().st_size for p in files) // 1024} KB; will be served at {URL}')


if __name__ == '__main__':
    main()
