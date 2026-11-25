## Conducting a Trio task

Run `python trio.py` in the harness checkout, or use the absolute script path from the current project. Use `python trio.py doctor` to inspect the configured transports.

- For a second opinion on a change, run `python trio.py review --dir . --models claude,gemini`. For one question, use `python trio.py ask review "Review this requirement for ambiguity: [include text]" --model claude`.
- For an independent rebuild, prepare a separate Git working tree containing the spec and check. Give Claude the builder role with `python trio.py relay --spec SPEC.md --dir ../independent --check "python -m pytest -q" --builder claude --reviewer codex`. Leave the first implementation out of that tree.
- For a long-context read, use `python trio.py ask long_context "Read DESIGN.md and identify incompatible requirements." --dir .` with a CLI. Include relevant text directly when the selected transport is an API.
- For a disputed fact, run `python trio.py crosscheck "State the factual question here."` before sharing your own answer. Inspect the labelled evidence and verify disagreements against sources.

Use write access for an authorized implementation. Read the report path on stdout and report findings in the task context. When invoked by Trio as a delegate, return the requested answer or edits directly.
