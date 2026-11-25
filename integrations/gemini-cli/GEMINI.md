## Conducting a Trio task

Invoke the harness through the shell with `python trio.py`. Use the absolute script path if the target project is outside the harness checkout. Run `python trio.py doctor` to inspect model availability.

- For a second opinion, ask `python trio.py ask review "Which assumptions need evidence? [include the claim]" --model claude`. Use `python trio.py review --dir . --models claude,codex` when the subject is a diff.
- For an independent rebuild, give Codex a separate Git working tree with the original spec and checks. Run `python trio.py relay --spec SPEC.md --dir ../independent --check "python -m pytest -q" --builder codex --reviewer claude`. Keep the first implementation out of the builder's context.
- For a long-context read, use `python trio.py ask long_context "Read DESIGN.md and extract the constraints on storage." --dir . --model claude`. A file-capable CLI can inspect that directory. Include the relevant text for API-based reads.
- For an independent factual check, run `python trio.py crosscheck "Ask a neutral question about the claim here."`. Use the report to identify where the answers diverge and consult the underlying evidence.

Keep questions and reviews read-only. Give builders edit access when the user requests implementation. When Trio delegates one of these roles to you, complete it directly.
