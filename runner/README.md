# Prompt runner

Sends each `data/tasks/<category>/<task>/instruction.md` as a plain prompt to
Claude, Codex (OpenAI), Gemini and Panacea, and saves every response for
scoring later.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...   # Claude
export OPENAI_API_KEY=...      # Codex
export GEMINI_API_KEY=...      # Gemini
npm install -g @anote-ai/anote # Panacea's command-line tool (uses ANTHROPIC_API_KEY too)
```

Model names can be overridden with `CLAUDE_MODEL`, `CODEX_MODEL` and
`GEMINI_MODEL` (defaults: `claude-sonnet-5`, `gpt-5-codex`, `gemini-2.5-pro`). `RUNNER_MAX_TOKENS` caps
Claude's output (default 8192).

A model with no key is recorded once as `not_configured` and skipped, so you
can run with only the keys you have.

## Run

```bash
python -m runner.run_prompts                              # all tasks, all four models
python -m runner.run_prompts --models claude gemini --limit 5
python -m runner.run_prompts --tasks coding_tasks/pypi-server
python -m runner.run_prompts --models echo --limit 3     # offline check, no keys needed
python -m runner.run_prompts --run-id 20260926T130000Z   # resume an interrupted run
```

## Colab

```python
!git clone https://github.com/Break-Through-Tech/Anote-1D-building-high-quality-datasets-and-evaluation-frameworks-for-ai-coding-assistants repo
%cd repo
!pip install -q -r requirements.txt
!npm install -g @anote-ai/anote

import os
from google.colab import userdata   # keys stored in Colab's Secrets panel
for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"]:
    try:
        os.environ[k] = userdata.get(k)
    except Exception:
        pass

from runner.run_prompts import run
import pandas as pd
rows = run(models=["claude", "codex", "gemini", "panacea"], limit=5)
pd.DataFrame(rows)[["task_id", "model", "status", "latency_s", "output_tokens"]]
```

## Output

Each run writes to `results/<run_id>/`:

| File | Contents |
|------|----------|
| `results.jsonl` | One line per call, appended as it finishes (used for resuming) |
| `results.json` | All rows as a JSON list |
| `results.csv` | Same rows as CSV |

Columns: `run_id, timestamp, task_id, category, difficulty, model, model_name,
status (ok | error | not_configured), latency_s, input_tokens, output_tokens,
error, prompt, raw_response, extraction_ok, extraction_method, n_code_blocks,
code_languages, code_files, extracted_code`.

## Code extraction

Every prompt ends with a short formatting line (`FORMAT_INSTRUCTION` in
`run_prompts.py`) that asks for fenced code blocks, with `File: <path>` above
each file. Turn it off with `--no-format-instruction`.

`runner/extract.py` pulls the code out of `raw_response` into `extracted_code`.
It runs automatically at the end of a run. After changing its rules, re-run it
on saved results without calling any model:

```bash
python -m runner.extract results/20260926T130000Z
```

## Panacea

Panacea (https://github.com/anote-ai/Panacea) is run through Anote's `anote`
command-line tool. For each task, `call_panacea` in `runner/providers.py`:

1. makes a new empty folder, so the tool can't read or change anything of yours
2. runs `anote ask --no-edit` there, passing the prompt on standard input
3. removes the tool's decorative and progress lines and keeps the answer

Settings: `PANACEA_CMD` (default `anote`, e.g. `npx anote` if not installed
globally) and `PANACEA_TIMEOUT` in seconds (default 900). The tool doesn't
report token counts, so those columns stay empty for Panacea.
