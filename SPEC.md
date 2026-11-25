# SPEC: ai-trio-harness

## Goal
One small harness that makes Claude, Codex and Gemini work as a team on one task, each in the role it suits, with
cross-checks between them, instead of using three chat windows separately. It is the pattern the author runs daily:
one model plans and supervises, another builds or reviews, a third answers independently so the others can be checked.
Free and open (MIT). It drives each vendor's own CLI with the user's existing plan, or an API key.

## Tool: `trio.py` (one file, Python 3.10+, standard library only)
Subcommands:
- `doctor`: list each model, whether it is available, and how (cli / api / missing), with the reason. Never print a key.
- `ask ROLE "prompt" [--model NAME] [--dir DIR] [--write]`: run on the first available model in ROLE's list in
  `trio.json` (or the named model). Print the answer. `--write` lets the model edit files in DIR (CLI adapters only).
- `crosscheck "question" [--models a,b,c] [--judge NAME]`: ask every available model independently (no model sees
  another's answer). Then the judge gets all answers, labelled A, B, C in a shuffled order (so it can't favour a
  brand), and returns JSON `{"agree": [str], "disagree": [{"point": str, "answers": {"A": str, ...}}],
  "verdict": str, "confidence": "low|medium|high"}`. Write a Markdown report that maps letters back to models and
  says plainly that disagreements are leads to verify, not truth.
- `relay --spec FILE --check "CMD" --dir DIR [--builder NAME] [--reviewer NAME] [--tries 2]`: DIR must be a git repo.
  Loop up to `tries` times:
  1. The builder (write mode) gets the spec (plus the previous round's findings) and edits files in DIR.
  2. The harness runs CMD in DIR (shell, timeout) and keeps the exit code and the last 60 lines.
  3. The reviewer (read-only, a different model from the builder) gets the spec, `git diff` (with untracked files)
     and the check output, and returns JSON `{"pass": bool, "findings": [{"severity": "blocking|minor", "text": str}]}`.
  4. Stop when the check passes and there is no blocking finding.
  Report: rounds, check result, findings, diff stat. The harness never commits, pushes or deletes.
- `review --dir DIR [--base REF] [--models a,b]`: two different models review the same diff independently. Merge the
  findings, marking the ones both models raised (by simple text similarity) as "both".

## Adapters (same interface)
`run(prompt, cwd, write=False, timeout=900) -> Result(ok, text, model, seconds, error)`; `available() -> (bool, how, why)`.
Send long prompts on stdin, not argv (Windows argv limit), where the CLI supports it.
- **claude**: `claude -p --output-format json` (prompt on stdin), read `result` from the JSON. Write mode adds
  `--permission-mode acceptEdits`; read-only mode adds nothing (in print mode, unapproved edit tools are refused).
  Optional `--model` from trio.json.
- **codex**: `codex exec --skip-git-repo-check -C DIR -s read-only|workspace-write -o OUTFILE -` (prompt on stdin;
  `-` means read stdin), then read OUTFILE. Find the binary in `CODEX_BIN`, then PATH, then on Windows
  `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe`. Optional `-m` from trio.json.
- **gemini**, in this order:
  1. `GEMINI_API_KEY` set: Google's REST API `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`,
     key in the `x-goog-api-key` header (never in the URL).
  2. else the `gemini` CLI on PATH: `gemini -p "" -o json --approval-mode plan` (or `auto_edit` in write mode), prompt
     on stdin; read `response` from the JSON. Treat an auth error in the output as "unavailable".
  3. else `OPENROUTER_API_KEY`: OpenRouter chat completions with the model in trio.json (e.g. `google/gemini-3.8-flash`).
  API modes have no file tools: refuse `--write` with a clear message and fall back to the next model in the role.
- An adapter that is missing, has no key, or returns an auth/quota error reports unavailable; routing moves on to the
  next model in the role list and logs why.

## Config: `trio.json`
`models` (name -> adapter + optional model id) and `roles` (ordered lists). Defaults:
plan [claude, codex, gemini], build [codex, claude], review [claude, codex, gemini], research [gemini, claude, codex],
long_context [gemini, claude], judge [claude, gemini, codex]. A `TRIO_CONFIG` env var may point elsewhere.

## Logs = backup of every output
Every call writes `runs/YYYY-MM-DD/HHMMSS-<cmd>-<model>.md`: command, role, model, how, seconds, ok, prompt, output.
Reports go next to them. `runs/` is in .gitignore. Key values must never appear in logs (redact any env value of
`*_API_KEY`/`*_TOKEN` found in text before writing).

## Integrations (docs + ready files)
- `integrations/claude-code/`: `skills/trio/SKILL.md` (when Claude should call `python trio.py ...` through Bash: a
  second opinion, an independent rebuild, a long-context read, a cross-check of a fact), plus a CLAUDE.md snippet.
- `integrations/codex/AGENTS.md`: the same rules for Codex as the conductor.
- `integrations/gemini-cli/GEMINI.md`: the same for Gemini CLI as the conductor.
- `integrations/any-harness.md`: plain scripts and CI (a GitHub Actions example that runs `trio.py review` on a pull
  request with keys from repository secrets; marked as an example).

## Tests (pytest, no network, no real CLIs)
Fake adapters and a mocked subprocess. Cover: routing and fallback order; `--write` refused for API-mode gemini;
crosscheck runs each model without the others' answers, shuffles labels, maps them back, and tolerates the judge's
JSON inside code fences; relay stops on pass, retries with findings, respects `tries`, refuses a non-git DIR and a
builder equal to the reviewer; review merges "both"; log files are written and contain no key values; each adapter
builds the exact command line in the spec; Windows codex discovery; gemini picks API key > CLI > OpenRouter.

## Example
`examples/slugify/`: a tiny task for `relay` (SPEC.md asking for `slugify.py` + `test_slugify.py` exists as the check).

## README (house format)
Result first (a real run excerpt), why three models (roles with honest reasons, no benchmark claims without a
source), setup in at most 5 steps with real commands, every subcommand with an example, using it inside Claude Code /
Codex / Gemini CLI / anything else, cost and limits (each runs on your own plan or key), what was tested and what
wasn't, credits, MIT licence.

## Done-check
`python -m pytest -q` passes; `python trio.py doctor` runs; real runs on the author's PC: `crosscheck` with three
models, `relay` on examples/slugify, `review` on a diff; outputs kept in `evidence/`.
