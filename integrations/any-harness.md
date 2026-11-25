# Scripts and CI

Invoke Trio through the Python interpreter running your script. Pass each argument separately so multiword prompts and paths survive shell quoting. Set the harness path for your checkout.

```python
from pathlib import Path
import subprocess
import sys

harness = Path("path/to/ai-trio-harness/trio.py").resolve()
call = subprocess.run(
    [sys.executable, str(harness), "review", "--dir", str(Path.cwd())],
    encoding="utf-8",
    capture_output=True,
)
print(call.stdout, end="")
if call.stderr:
    print(call.stderr, file=sys.stderr, end="")
raise SystemExit(call.returncode)
```

Ask routes a single question. Crosscheck collects independent answers and a judge's verdict. Relay takes a spec, a Git working directory and a shell check, and grants the builder edit access. Review reads a diff and combines two assessments. Reports go under `runs/` beside the script. Exit code 1 identifies blocking review findings or an exhausted relay. Exit code 2 identifies an execution error.

## GitHub Actions example

This example reviews a same-repository pull request with Claude Code and Google's Gemini API. Set repository secrets named `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`. The workflow uses the base revision's harness and config. It checks out the proposed revision separately and compares it with the merge base. The review step receives the credentials and sends the diff to both providers.

```yaml
name: Trio review

on:
  pull_request:

permissions:
  contents: read

jobs:
  review:
    if: github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.sha }}
          path: harness
          persist-credentials: false
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          path: candidate
          fetch-depth: 0
          persist-credentials: false
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - run: npm install --global @anthropic-ai/claude-code@2.1
      - name: Review the proposed changes
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
        run: |
          base=$(git -C candidate merge-base "$BASE_SHA" HEAD)
          python harness/trio.py review --dir candidate --base "$base" --models claude,gemini
      - name: Keep the review report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: trio-review
          path: harness/runs/**/*-review-report*.md
          if-no-files-found: ignore
```
