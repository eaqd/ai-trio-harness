---
name: trio
description: Get a second opinion, an independent implementation, a long-context read or a blind fact cross-check with the local Trio harness.
---

# Conduct a Trio task

Use Bash to invoke `python trio.py` from the harness checkout. In another project, substitute the absolute path to that checkout's `trio.py` and pass the project's path with `--dir` on commands that take it. Read the project's spec and choose one focused question or check.

- For a second opinion on the working tree, run `python trio.py review --dir . --models codex,gemini`. For one textual question, use `python trio.py ask review "What edge cases follow from this requirement? [include requirement]" --model codex`.
- For an independent rebuild, give the new builder the spec and acceptance check in a separate Git working tree. Run `python trio.py relay --spec SPEC.md --dir ../independent --check "python -m pytest -q" --builder codex --reviewer claude`. Keep the first implementation and its findings out of the builder's starting files.
- For a long-context read, use `python trio.py ask long_context "Read DESIGN.md and list its unresolved constraints." --dir .` with a file-capable CLI. Supply the relevant text in the prompt when using an API.
- For a factual cross-check, run `python trio.py crosscheck "State the claim as a neutral question here."`. Read the report path from stdout and verify disputed points against a primary source.

Use `python trio.py doctor` to see the configured transports. Choose write mode only when the user requested edits. When Trio has invoked you as a respondent, builder, reviewer or judge, complete that role directly to avoid recursive calls.
