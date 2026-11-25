# ai-trio-harness: make Claude, Codex and Gemini work as one team

**Watch it:** the 98-second walkthrough https://youtu.be/-zuHfz561ko and the 25-second Short https://youtube.com/shorts/CCFoWO5aifQ

## Result

One command, three models, one report. A real run on 2026-11-25:

```text
$ python trio.py relay --spec SPEC.md --check "python -m pytest -q test_slugify.py" --dir . --builder codex --reviewer claude
Round 1  builder: codex (48.5 s) -> check: 8 passed -> reviewer: claude (33.1 s), pass: True
Outcome: passed.

$ python trio.py review --dir . --models claude,gemini   # two independent reviews of what Codex wrote
claude: 2 minor findings (one is behaviour the spec asked for: a lead to check, not a bug)
gemini: no findings

$ python trio.py crosscheck "In Python 3.12: is sorted() stable, and what does my_list.sort(key=str.lower) return?"
A, B, C (codex, claude, gemini, shown to the judge in shuffled order) all: stable; returns None.
Verdict from claude: all three correct. Confidence: high
```

The full reports are in [evidence/](evidence/), including the file Codex wrote. Most people use these tools in three
separate windows and copy text between them. Trio gives each one a role, hands work between them, keeps every prompt
and answer on disk, and makes one model check another before you trust the result.

## The pattern (how the team works)

This is the routine the author runs every day, written down so any harness can follow it:

1. **One conductor, one sidekick, one outside check.** The conductor (any of the three) plans, briefs and decides.
   A sidekick does the heavy work: reading a big codebase, writing code against a check, a long fix-and-test loop. A
   third model answers on its own, without seeing the others, when a fact or a number matters.
2. **Brief like a contractor.** Paths, goal, rules, and a done-check command. Nothing else.
3. **The check decides, not the model.** A command (tests, a script, a count) passes or fails. A reviewer's opinion is
   a lead to verify, not a verdict.
4. **Keep work that passes.** If the sidekick's work meets the check, don't redo it or polish it: that throws the
   saving away. If it fails, allow one retry with the findings, then do it yourself.
5. **Anything that matters gets a second model.** A review before you merge, an independent rebuild from the written
   spec before you trust numbers, a cross-check before you publish a fact.
6. **Keep the output.** Every prompt, answer and report lands in `runs/`. When you change a model or a rule, re-run old
   requests and compare.

## Why three models

Trio gives one model a task and brings in another where an independent answer or a fresh review can help. The default build role starts with Codex because its CLI can edit a designated workspace and return a final message. Claude starts the plan and review roles, where the conductor needs a written plan or findings to act on. Gemini starts research and long-context requests and can answer supplied text through an API. These are editable role assignments.

## Setup

From a checkout of this repository, on Windows or POSIX, use a Python 3.10+ interpreter.

1. Check your interpreter with `python --version`.
2. Install the vendor CLIs you want. With Node.js and npm available, `npm install -g @anthropic-ai/claude-code @openai/codex @google/gemini-cli` installs all three.
3. Start each installed CLI (`claude`, `codex`, `gemini`) and complete its sign-in flow. For Gemini API access, supply `GEMINI_API_KEY` or `OPENROUTER_API_KEY` through your environment.
4. Run `python trio.py doctor` to see which transports Trio finds. Doctor checks local executables and environment settings. The first model request checks authentication and quota.
5. For the offline harness suite and the slugify example, install pytest with `python -m pip install -r requirements-dev.txt`. The harness itself uses the standard library.

## Commands

### Doctor

```sh
python trio.py doctor
```

Lists each configured name, its availability, the transport (`cli`, `api` or `missing`) and the reason. The CLI adapters target Claude Code 2.1, Codex CLI 0.167 and Gemini CLI 0.71.

### Ask

```sh
python trio.py ask plan "Read SPEC.md and outline the stopping conditions for relay." --dir .
python trio.py ask build "Implement the supplied slugify spec in this directory." --dir examples/slugify --model codex --write
```

The answer goes to stdout. With a role, Trio tries models in order and explains skipped or failed attempts on stderr. `--model` selects a single configured name. Ask defaults to read-only. `--write` grants a CLI adapter workspace editing permissions.

### Crosscheck

```sh
python trio.py crosscheck "Which properties should a URL slug preserve?" --models claude,codex,gemini --judge claude
```

Each available respondent gets the same question in a fresh directory. The judge receives the question and shuffled answers labelled with letters. The Markdown report restores the model names and records agreement, disagreement, verdict and confidence. An answer can still reveal its own source through its content. Verify disputed facts against primary evidence.

### Relay

```sh
python trio.py relay --spec examples/slugify/SPEC.md --check "python -m pytest -q test_slugify.py" --dir examples/slugify --builder codex --reviewer claude --tries 2
```

The spec path is relative to your starting directory. Within the target Git working tree, the builder edits files, the harness runs your shell command, and a different model reviews the spec, diff and last 60 lines of combined check output. A round passes with exit code zero and no blocking finding. Otherwise the next builder prompt includes the findings and check output. The report gives each round's check result, findings and diff stat.

Use a target whose current changes you intend to share with the reviewers. The harness reads tracked and non-ignored untracked changes under `--dir`. Its Git operations leave the index and working tree intact. The builder has edit access and the check runs with your shell permissions. Choose a trusted check command. Model calls default to a 900-second timeout and shell checks to 300 seconds.

### Review

```sh
python trio.py review --dir . --base HEAD --models claude,codex
```

Two different models receive the same diff in separate directories. Use a branch, tag or commit for `--base`. The default is HEAD, or the empty tree before the first commit. The report marks similar findings from the two reviewers as **both**, preserves their wording and keeps the higher severity. This text match can miss paraphrases or group issues that need separate fixes.

Reports print their path on stdout. Exit code `0` means completion, `1` means relay reached its round limit or review has a blocking finding, and `2` indicates a usage or execution error.

## Configuration and run files

Edit the ordered role lists in [trio.json](trio.json) or set `TRIO_CONFIG` to another JSON file. Each model entry names its adapter. Its optional `model` selects a vendor model ID, and Gemini's `openrouter_model` selects the OpenRouter ID. Command-line selectors use the model entry names.

Gemini chooses Google REST when `GEMINI_API_KEY` is set, then the Gemini CLI on PATH, then OpenRouter when `OPENROUTER_API_KEY` is set. If the CLI is installed but signed out or failing, a read-only call falls back to OpenRouter (when its key is set), and the run file records the route that was actually used. The API transports see the supplied prompt and have no file tools. Write routing skips an API transport and tries the next model in the role. Codex discovery checks `CODEX_BIN`, PATH and the versioned Windows installation under `%LOCALAPPDATA%\OpenAI\Codex\bin`.

Trio saves prompts, replies, errors, timings and reports beside the script under `runs/YYYY-MM-DD/`. It masks environment values whose names end in `_API_KEY` or `_TOKEN` in terminal output and run files. Run files can still contain private source code or personal information. Git ignores `runs/`.

## Using Trio inside another harness

- **Claude Code** — install the project skill and add the conductor guidance to your project's CLAUDE.md. [Skill](integrations/claude-code/skills/trio/SKILL.md) · [CLAUDE.md snippet](integrations/claude-code/CLAUDE-snippet.md)
- **Codex** — merge the conductor guidance into the project's AGENTS.md. [Codex instructions](integrations/codex/AGENTS.md)
- **Gemini CLI** — merge the conductor guidance into the project's GEMINI.md. [Gemini instructions](integrations/gemini-cli/GEMINI.md)
- **Scripts and CI** — invoke Trio with an argument list, capture its output and retain the report. [Script and GitHub Actions examples](integrations/any-harness.md)

## Cost and limits

Each request uses your CLI account's plan or the API key for its selected transport. Crosscheck adds a judge call to the independent answers. Review needs two successful responses. Each relay round uses a builder and a reviewer, and retries or fallback attempts can add usage. Provider context limits apply to the full prompt, including diffs. An API model needs file contents in its prompt to answer questions about them.

## What I tested

On Windows 11 with Python 3.13, Claude Code 2.1.201, Codex CLI 0.167 and Gemini CLI 0.71.1, on 2026-11-25:

- `python -m pytest -q`: 43 passed (no network, no real CLIs).
- `doctor`: found all three CLIs.
- `crosscheck` with all three models answering and Claude judging: all correct, as above. Answers took 7.5-9.7 s each,
  the judge 20 s. Gemini ran through OpenRouter (`google/gemini-3.8-flash`).
- `relay` on [examples/slugify](examples/slugify/): Codex built `slugify.py` in one round (48.5 s), the 8 acceptance
  tests passed, and Claude reviewed it read-only (33.1 s) and passed it.
- `review` of that code by Claude (38.1 s) and Gemini (11.0 s): Claude raised 2 minor points (a docstring wording, and
  that letters with no ASCII form are dropped: `slugify("Søren")` gives `s-ren`, which I confirmed and which the
  spec allows), Gemini none.
- A read-only Claude call asked to create a file could not: it had only Read, Grep and Glob.
- `ask research` routed to Gemini, which answered correctly.

The first real runs found two bugs that the mocked tests had missed: an installed but signed-out Gemini CLI made Gemini
"unavailable" even with an OpenRouter key set, and the check's own `__pycache__` files showed up in the reviewer's
diff. Then Trio reviewed itself before publishing (Codex and Gemini on the whole repo) and found two more: a
"read-only" Claude call could still edit files if the user's own settings allowed it, and a timed-out builder's child
processes could keep running. All four are fixed, with tests.

Not tested: the Gemini CLI signed in with a Google account, the direct `GEMINI_API_KEY` route, Linux and macOS, and
the GitHub Actions example. Those paths follow each vendor's documented flags and are covered by the mocked tests only.

## Verification commands

Use `python -m pytest -q` for the mocked suite. The unfinished slugify task has a separate acceptance check shown in the relay example. For author-run evidence, use doctor, a three-model crosscheck, the slugify relay and a review on a diff. Inspect the resulting Markdown before copying selected real reports into `evidence/`.

## Credits and licence

Ayobami Erinle wrote the team workflow. This repo was built the way it describes: Codex (GPT-6.2 Astra) wrote the first version from [SPEC.md](SPEC.md), Claude ran the tests and the real three-model runs, fixed what they found, and checked every claim in this README. Claude Code, Codex CLI and Gemini CLI are provided by their respective vendors. Released under the [MIT licence](LICENSE).

