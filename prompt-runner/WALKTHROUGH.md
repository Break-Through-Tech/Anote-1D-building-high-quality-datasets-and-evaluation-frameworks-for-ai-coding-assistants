# Prompt runner: a beginner's walkthrough

This explains every piece of the prompt runner: what it does, and why it was
written that way. Read it alongside the code files.

---

## Part 0. What was built, in plain English

Your repo has 38 tasks in `data/tasks/`. Each task folder has an
`instruction.md` file. That file is the prompt, for example "Create a Python
package called vectorops...".

The runner does four things:

1. It **finds** every `instruction.md` file.
2. It **sends** the text of each one to each AI model (Claude, Codex, Gemini, Panacea).
3. It **records** what came back: the answer, how long it took, how many tokens it used, and any error.
4. It **saves** everything to a JSON file and a CSV file, so you can calculate metrics later.

There are five files:

| File | Job |
|------|-----|
| `requirements.txt` | Lists the Python libraries to install |
| `runner/__init__.py` | Tells Python that `runner` is a package (a folder of code you can import) |
| `runner/providers.py` | One small function per AI model. Each one sends a prompt and returns the answer |
| `runner/run_prompts.py` | The main loop: finds the tasks, calls the models, saves the results |
| `runner/README.md` | How to set it up and run it |

**Why two code files instead of one?** Talking to each AI company works a
little differently, and that code lives in `providers.py`. The loop over
tasks is the same no matter which model you call, and that lives in
`run_prompts.py`. If Panacea's API changes, you edit one function in
`providers.py` and nothing else. This is called **separation of concerns**.

---

## Part 1. `requirements.txt`

```
anthropic
openai
google-genai
```

These are the official Python libraries (called **SDKs**, software
development kits) from Anthropic (Claude), OpenAI (Codex) and Google
(Gemini). `pip install -r requirements.txt` installs all three.

**Why use SDKs instead of writing raw web requests?** The SDKs handle
logging in, formatting the request and reading the reply for you. There's
less code, so there are fewer bugs.

Panacea has no line here because we don't know its SDK yet. Its stub uses
`urllib`, which is built into Python.

---

## Part 2. `runner/__init__.py`

```python
"""Prompt runner: send task instructions to coding models and save the responses."""
```

This is a single line: a **docstring**, a string that describes the module.
Because the folder contains a file named `__init__.py`, Python treats `runner`
as a package. That is what lets you write `from runner.run_prompts import run`
in Colab, or `python -m runner.run_prompts` in a terminal.

---

## Part 3. `runner/providers.py`, which talks to the models

### 3.1 The top of the file

```python
"""Model adapters.
...
"""
```
This docstring explains the purpose of the file. Anyone who opens it knows
what it does.

```python
from __future__ import annotations
```
This lets type hints like `Optional[int]` work the same way on older Python
versions. It's a safety line and doesn't change how the code behaves.

```python
import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Optional
```
These are **imports**, which bring in tools from Python's standard library:
- `json` converts between Python dicts and JSON text. The Panacea stub needs it.
- `os` reads **environment variables**, which is where the API keys live.
- `urllib.request` makes web requests without installing anything. Panacea uses it.
- `dataclass` is a shortcut for making simple "record" classes (explained below).
- `Callable, Dict, Optional` are **type hints**. They label what kind of value
  something is (a function, a dictionary, "this or None"). Python doesn't
  enforce them. They exist to make the code easier for humans to read.

```python
DEFAULT_MAX_TOKENS = int(os.environ.get("RUNNER_MAX_TOKENS", "8192"))
```
Claude's API requires a limit on how long its answer can be, measured in
**tokens** (pieces of words). `os.environ.get("RUNNER_MAX_TOKENS", "8192")`
means: "use the environment variable if it's set, otherwise use 8192."
`int(...)` converts the text `"8192"` into the number 8192.
**Why 8192?** Coding answers can run long, and 8192 is enough for a full
solution without being wasteful. You can change it without editing any code.
**Why ALL_CAPS?** It's a Python convention for a value that is set once and
never changes (a constant).

### 3.2 The `Completion` record

```python
@dataclass
class Completion:
    text: str
    model_name: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
```
Each model's SDK returns its answer in a different shape. This class
defines **one common shape** that every provider function must return:
- `text`: the model's answer.
- `model_name`: the exact model that answered (e.g. `claude-sonnet-5`).
- `input_tokens` / `output_tokens`: how many tokens the prompt and the answer
  used. `Optional[int] = None` means "a number, or None if the model didn't
  report it". Panacea might not report token counts.

`@dataclass` is a **decorator** (a line starting with `@` that adds behavior).
It writes the boring setup code for you, so you can just write
`Completion(text="hi", model_name="x")`.

**Why a common shape?** The main loop in `run_prompts.py` can then handle
every model the same way, without special cases.

### 3.3 A custom error for "not set up"

```python
class ProviderNotConfigured(RuntimeError):
    """Raised when a provider is missing its API key or endpoint."""
```
This creates our own kind of error. It inherits from `RuntimeError`, which
means it is a normal Python error with its own name.
**Why?** "You forgot your API key" is different from "the API failed this
one time". With its own error type, the main loop can tell the two apart.
When a key is missing, it skips that model for the whole run instead of
failing 38 times.

```python
def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ProviderNotConfigured(f"Set the {name} environment variable.")
    return value
```
This is a small helper function. It reads an environment variable and raises
our custom error with a clear message if the variable is missing or empty.
- The leading `_` in `_require_env` is a convention meaning "internal
  helper, not meant to be used from outside this file".
- `-> str` is a type hint saying the function returns a string.
- `f"...{name}..."` is an **f-string**. It inserts the value of `name` into the text.
**Why?** All four providers need this check. Writing it once avoids
repeating the same code four times.

### 3.4 Claude

```python
def call_claude(prompt: str) -> Completion:
    import anthropic
```
The import is placed **inside** the function (a "lazy import") instead of at
the top of the file.
**Why?** If you haven't installed `anthropic` but only want to run Gemini,
the file still loads fine. You only need the libraries for the models you
actually use.

```python
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
```
This picks the model name from an environment variable, with a default.
**Why?** You can switch to another Claude model without touching the code.

```python
    client = anthropic.Anthropic(api_key=_require_env("ANTHROPIC_API_KEY"))
```
This creates a **client**, the object that talks to Anthropic's servers. The
API key comes from the environment, never from the code.
**Why?** If a key is ever committed to GitHub, anyone can use it and bill
your account. Environment variables keep keys out of the code.

```python
    resp = client.messages.create(
        model=model,
        max_tokens=DEFAULT_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
```
This sends the prompt. `messages` is a list of chat turns. We send one turn,
from the `"user"`, containing the task text. This is the "plain prompt"
approach: no system prompt and no tools, just the instruction exactly as
written. That keeps the comparison fair across models.

```python
    text = "".join(block.text for block in resp.content if block.type == "text")
```
Claude's reply comes in **blocks**, a list of pieces. Some may not be text
(for example, thinking blocks). This line keeps only the text blocks and
glues them together into one string.
`"".join(...)` joins a list of strings with nothing between them. The part
inside is a **generator expression**, a compact loop.

```python
    return Completion(
        text=text,
        model_name=resp.model,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )
```
This packs the answer into our common `Completion` shape. `resp.model` is the
exact model version that answered, which is useful if a default name changes
later.

### 3.5 Codex (OpenAI)

```python
def call_codex(prompt: str) -> Completion:
    from openai import OpenAI

    model = os.environ.get("CODEX_MODEL", "gpt-5-codex")
    client = OpenAI(api_key=_require_env("OPENAI_API_KEY"))
    resp = client.responses.create(model=model, input=prompt)
```
This follows the same pattern as Claude: lazy import, model name from the
environment, a client with a key from the environment, then one call. It
uses OpenAI's **Responses API**, where you pass the prompt as `input`.
**Why `gpt-5-codex`?** It's OpenAI's coding-focused model, which matches
"Codex". This name is a default I picked. Check it against the models your
OpenAI account can use.

```python
    usage = getattr(resp, "usage", None)
    return Completion(
        text=resp.output_text,
        model_name=resp.model,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
    )
```
`resp.output_text` is a shortcut the SDK provides that returns all the answer
text as one string.
`getattr(obj, "name", None)` means "get `obj.name`, or None if it doesn't
exist".
**Why so careful here?** Token usage can occasionally be missing. This way
a missing value becomes None instead of crashing the run.

### 3.6 Gemini

```python
def call_gemini(prompt: str) -> Completion:
    from google import genai

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
    client = genai.Client(api_key=_require_env("GEMINI_API_KEY"))
    resp = client.models.generate_content(model=model, contents=prompt)
    usage = getattr(resp, "usage_metadata", None)
    return Completion(
        text=resp.text or "",
        model_name=model,
        input_tokens=getattr(usage, "prompt_token_count", None),
        output_tokens=getattr(usage, "candidates_token_count", None),
    )
```
This is the same pattern again, using Google's `google-genai` SDK.
- `generate_content` sends the prompt.
- `resp.text or ""`: if Gemini returns nothing (for example, when it blocks
  an answer), `resp.text` is None. `or ""` turns that into an empty string so
  the CSV stays clean.
- Google names its token fields differently (`prompt_token_count`,
  `candidates_token_count`). Here we translate them into our common names.
  This is exactly why the `Completion` shape exists.

### 3.7 Panacea (the stub)

```python
def call_panacea(prompt: str) -> Completion:
    """Stub for Panacea until its API is known. ..."""
```
A **stub** is a placeholder. I don't know how Panacea's API works, so this
function makes a reasonable guess that is easy to change.

```python
    url = _require_env("PANACEA_API_URL")
    model = os.environ.get("PANACEA_MODEL", "panacea")
```
The web address (URL) comes from the environment. If it isn't set, the run
records `not_configured` for Panacea and moves on.

```python
    headers = {"Content-Type": "application/json"}
    if os.environ.get("PANACEA_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['PANACEA_API_KEY']}"
```
**Headers** are extra information sent with a web request.
`Content-Type: application/json` tells the server "I'm sending JSON".
If a key is set, it is sent as a "Bearer token", which is the most common
way web APIs accept keys.

```python
    body = json.dumps({"prompt": prompt, "model": model}).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
```
`json.dumps` turns the Python dict into JSON text, and `.encode()` turns that
text into bytes, which is what gets sent over the network. The next line
builds a POST request, the usual way to send data to an API.

```python
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode())
```
This sends the request and reads the reply. `timeout=600` gives up after 10
minutes so the run can't hang forever. `with ... as r:` makes sure the
connection is closed afterwards. `json.loads` turns the JSON reply back into
a Python dict.

```python
    text = data.get("response") or data.get("text") or data.get("output") or ""
    return Completion(text=text, model_name=model)
```
This looks for the answer under a few common field names and uses the first
one it finds. No token counts are returned because we don't know whether
Panacea reports them.
**What you'll change later:** once you know Panacea's real format, edit
this function and nothing else.

### 3.8 Echo (for testing)

```python
def call_echo(prompt: str) -> Completion:
    return Completion(text=f"[echo] {prompt[:200]}", model_name="echo")
```
This is a fake model that repeats back the first 200 characters of the
prompt (`prompt[:200]` is **slicing**).
**Why?** You can test the whole pipeline (finding tasks, saving the CSV and
JSON) for free, with no keys and no internet.

### 3.9 The provider table

```python
PROVIDERS: Dict[str, Callable[[str], Completion]] = {
    "claude": call_claude,
    "codex": call_codex,
    "gemini": call_gemini,
    "panacea": call_panacea,
    "echo": call_echo,
}

DEFAULT_MODELS = ["claude", "codex", "gemini", "panacea"]
```
`PROVIDERS` is a dictionary that maps a short name to its function. Note
there are no `()` after the function names: we're storing the functions
themselves, not calling them yet.
**Why?** The main loop can do `PROVIDERS["claude"](prompt)` to call any
model by name. Adding a fifth model means writing one function and adding
one line here.
`DEFAULT_MODELS` is what runs if you don't choose. It leaves out `echo`,
because echo is only for testing.

---

## Part 4. `runner/run_prompts.py`, the main loop

### 4.1 The top of the file

The long docstring at the top is the manual: what the file does, where the
output goes, and example commands. It also appears when you run `--help`.

```python
import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional
```
- `argparse` reads command-line options like `--models claude`.
- `csv` and `json` write the two output formats.
- `time` measures latency and pauses between retries.
- `datetime, timezone` create timestamps and run ids in UTC.
- `Path` is a friendlier way to work with file paths than plain strings.

```python
try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None
```
`tomllib` reads `.toml` files (each task has a `task.toml` with its
difficulty). It is built into Python 3.11 and later. `try/except` means "try
this, and if that specific error happens, do this instead". On older Python
the runner still works and just leaves difficulty blank.

```python
from .providers import DEFAULT_MODELS, PROVIDERS, ProviderNotConfigured
```
This imports what we need from `providers.py`. The `.` means "from this same
package".

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "data" / "tasks"
RESULTS_DIR = REPO_ROOT / "results"
```
`__file__` is the path of this file (`.../runner/run_prompts.py`).
`.parent` goes up one folder (`runner/`), and `.parent` again goes up to the
repo root. With `Path`, the `/` operator joins folder names.
**Why?** The paths work no matter which folder you run the command from.

```python
FIELDS = [
    "run_id", "timestamp", "task_id", "category", "difficulty",
    "model", "model_name", "status", "latency_s",
    "input_tokens", "output_tokens", "error", "prompt", "response",
]
```
These are the columns of the results, in order. Defining them once
guarantees that every row, the CSV header and the JSON all match.
**Why these columns?**
- `run_id`, `timestamp`: which run the row came from and when, so you can compare runs.
- `task_id`, `category`, `difficulty`: which task, so you can group metrics (e.g. "accuracy on hard debugging tasks").
- `model`, `model_name`: the short name you chose, plus the exact version that answered.
- `status`: `ok`, `error` or `not_configured`, so you can filter out failures before scoring.
- `latency_s`: seconds taken, which is a metric in itself.
- `input_tokens`, `output_tokens`: for cost and verbosity metrics.
- `error`: what went wrong, if anything.
- `prompt`, `response`: the actual text, which scoring (CodeBLEU, pass@k and so on) will need.

### 4.2 `load_tasks`: finding the prompts

```python
def load_tasks(tasks_dir: Path = TASKS_DIR, only: Optional[Iterable[str]] = None) -> List[dict]:
```
This takes the tasks folder, plus an optional list of specific tasks to
run. It returns a list of dictionaries, one per task. `= TASKS_DIR` and
`= None` are **default values**, used when you don't pass anything.

```python
    wanted = set(only) if only else None
    tasks = []
```
If you asked for specific tasks, they go into a `set`, which makes checking
membership fast. Otherwise `wanted` is None, meaning "all tasks".

```python
    for path in sorted(tasks_dir.glob("*/*/instruction.md")):
```
`glob` finds files matching a pattern. `*/*/instruction.md` means
"category folder / task folder / instruction.md". `sorted` puts the results
in alphabetical order.
**Why sorted?** Every run then processes tasks in the same order, which
makes runs easy to compare and debug.

```python
        task_dir = path.parent
        task_id = f"{task_dir.parent.name}/{task_dir.name}"
```
The task id is `category/task`, for example `coding_tasks/pypi-server`.
**Why include the category?** It keeps ids unique even if two categories
ever contain a task with the same name.

```python
        if wanted and task_id not in wanted and task_dir.name not in wanted:
            continue
```
If you asked for specific tasks and this isn't one of them, skip it.
`continue` jumps to the next file. You can give the full id or just the
folder name (`pypi-server`), whichever is easier to type.

```python
        difficulty = ""
        toml_path = task_dir / "task.toml"
        if tomllib and toml_path.exists():
            try:
                meta = tomllib.loads(toml_path.read_text()).get("metadata", {})
                difficulty = meta.get("difficulty", "")
            except tomllib.TOMLDecodeError:
                pass
```
This reads the difficulty (easy, medium or hard) from `task.toml` if it can.
`.get("metadata", {})` returns an empty dict if the section is missing, so
the next line doesn't crash. If the file is malformed, `pass` means "ignore
it and leave difficulty blank".
**Why?** One broken metadata file shouldn't stop the whole run.

```python
        tasks.append(
            {
                "task_id": task_id,
                "category": task_dir.parent.name,
                "difficulty": difficulty,
                "prompt": path.read_text(),
            }
        )
    return tasks
```
This adds one dictionary per task to the list. `path.read_text()` reads the
whole instruction file as the prompt, exactly as written.

### 4.3 `_call_with_retries`: handling hiccups

```python
def _call_with_retries(fn, prompt: str, retries: int):
    for attempt in range(retries + 1):
```
`fn` is one of the provider functions. With `retries=2`, `range(3)` gives
attempts 0, 1 and 2, so there are up to 3 tries in total.

```python
        try:
            return fn(prompt)
```
This tries the call. If it works, `return` hands back the answer
immediately and the loop ends.

```python
        except ProviderNotConfigured:
            raise
```
If the key is missing, retrying is pointless. `raise` passes the error
straight up to the main loop.

```python
        except ImportError as e:
            raise ProviderNotConfigured(f"{e}. Run: pip install -r requirements.txt") from e
```
If the SDK isn't installed, retrying won't help either. This converts the
error into our "not configured" error and adds a helpful hint.
(I added this after testing: without it, a missing library was retried with
pauses on every task, which wasted time.)

```python
        except Exception:
            if attempt == retries:
                raise
            time.sleep(2 ** (attempt + 1))
```
Any other error, like a network blip or a rate limit, gets retried. On the
last attempt it gives up and passes the error up. Otherwise it waits 2
seconds, then 4 seconds (`2 ** 1`, then `2 ** 2`) before trying again.
**Why wait longer each time?** This is called **exponential backoff**. If a
server is overloaded, hammering it straight away makes things worse. Waiting
a bit longer each time gives it room to recover.

### 4.4 `_done_pairs` and `_read_jsonl`: resuming

```python
def _done_pairs(jsonl_path: Path) -> set:
    done = set()
    if jsonl_path.exists():
        for line in jsonl_path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("status") == "ok":
                    done.add((row["task_id"], row["model"]))
    return done
```
This reads the results saved so far, one JSON object per line, and collects
every (task, model) pair that already **succeeded**. `line.strip()` skips
blank lines. A pair in parentheses is a **tuple**.
**Why?** If Colab disconnects halfway through, you rerun with the same
`--run-id` and the runner skips what's done. You don't pay twice for the
same answers. Failed pairs are not counted as done, so they get retried.

```python
def _read_jsonl(jsonl_path: Path) -> List[dict]:
    latest = {}
    for line in jsonl_path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            latest[(row["task_id"], row["model"])] = row
    return list(latest.values())
```
This reads every saved row, but keeps only the **latest** row for each
(task, model) pair. Later lines overwrite earlier ones in the dictionary.
**Why?** If a pair failed and then succeeded on a resumed run, the final
files show the success, not both.

### 4.5 `write_outputs`: saving JSON and CSV

```python
def write_outputs(rows: List[dict], out_dir: Path) -> None:
    (out_dir / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
```
This writes all rows as one JSON list. `indent=2` makes it readable by
humans. `ensure_ascii=False` keeps characters like é or emoji as they are,
instead of escape codes.

```python
    with open(out_dir / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
```
This writes the same rows as a CSV. `DictWriter` turns each dict into a row,
using `FIELDS` for the column order. `newline=""` stops blank lines from
appearing between rows on Windows. The `csv` module automatically quotes
responses that contain commas or line breaks, which code answers always do.
**Why both formats?** CSV opens in Excel, Google Sheets and pandas. JSON
keeps long, multi-line code answers exactly intact. Your request asked for
either, so the runner writes both.

### 4.6 `run`: the main function

```python
def run(
    models=None, tasks=None, limit=None, run_id=None, retries=2,
    tasks_dir=TASKS_DIR, results_dir=RESULTS_DIR,
) -> List[dict]:
```
(Type hints are left out of this snippet to keep it short.) This is what you call from Colab. Every option has a default, so plain
`run()` works. It returns the list of rows, so you can put it straight into
pandas.

```python
    models = models or DEFAULT_MODELS
    unknown = [m for m in models if m not in PROVIDERS]
    if unknown:
        raise ValueError(f"Unknown model(s) {unknown}; choose from {sorted(PROVIDERS)}")
```
If you didn't choose models, all four are used. Then it checks for typos:
if you wrote `"cluade"`, it stops right away with a clear message instead of
failing silently later. The bracketed loop is a **list comprehension**, a
compact way to build a list.

```python
    task_list = load_tasks(tasks_dir, tasks)[:limit]
```
This loads the tasks and keeps the first `limit` of them. When `limit` is
None, `[:None]` keeps everything. It's handy for a cheap test run with
`limit=3`.

```python
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(results_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "results.jsonl"
```
Each run gets its own folder, named by the current time in UTC (e.g.
`20260926T125640Z`). `mkdir(parents=True, exist_ok=True)` creates the folder
and any missing parent folders, and doesn't complain if it already exists.
**Why a folder per run?** New runs never overwrite old results, so you can
compare runs over time.

```python
    done = _done_pairs(jsonl_path)
    skipped_models = set()
```
`done` holds the pairs that already succeeded (for resuming).
`skipped_models` collects models found to be not configured during this run.

```python
    print(f"Run {run_id}: {len(task_list)} tasks x {len(models)} models -> {out_dir}")
    with open(jsonl_path, "a", encoding="utf-8") as jsonl:
```
This prints a summary line, then opens the JSONL file in **append** mode
(`"a"`), which adds to the end instead of erasing what's there.

```python
        for task in task_list:
            for model in models:
                if (task["task_id"], model) in done or model in skipped_models:
                    continue
```
These are two nested loops: every task, crossed with every model. It skips
pairs that are already done and models that were found to be missing keys.

```python
                row = {k: "" for k in FIELDS}
                row.update(
                    run_id=run_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    task_id=task["task_id"],
                    category=task["category"],
                    difficulty=task["difficulty"],
                    model=model,
                    prompt=task["prompt"],
                )
```
This starts a row with every column empty (a **dict comprehension**), then
fills in what we already know. Starting from every column guarantees that
each row has the same keys, which the CSV writer needs.

```python
                start = time.perf_counter()
```
This starts the stopwatch. `perf_counter` is Python's most precise timer for
measuring durations.

```python
                try:
                    result = _call_with_retries(PROVIDERS[model], task["prompt"], retries)
                    row.update(
                        status="ok",
                        model_name=result.model_name,
                        response=result.text,
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                    )
```
This calls the model (with retries) and, on success, fills in the answer
columns.

```python
                except ProviderNotConfigured as e:
                    row.update(status="not_configured", error=str(e))
                    skipped_models.add(model)
                    print(f"  skipping {model}: {e}")
```
If a key or SDK is missing, it records that once, adds the model to the
skip set and prints why.
**Why?** You can run with only the keys you have today.

```python
                except Exception as e:
                    row.update(status="error", error=f"{type(e).__name__}: {e}")
```
Any other failure is recorded in the row, with the error type and message,
**and the run keeps going**.
**Why not crash?** One bad answer out of 152 calls shouldn't throw away the
other 151. The error column also tells you what went wrong.

```python
                row["latency_s"] = round(time.perf_counter() - start, 3)
```
This stops the stopwatch and rounds to milliseconds. Note that latency
includes any retry waits. For a clean comparison, filter to rows where
`status == "ok"`.

```python
                jsonl.write(json.dumps(row, ensure_ascii=False) + "\n")
                jsonl.flush()
```
This saves the row **immediately**, as one line. `flush()` forces it onto
disk right now instead of waiting in memory.
**Why?** If Colab crashes, every answer received so far is already saved.
This is the reason the runner writes a `.jsonl` file (one JSON object per
line) during the run: appending one line is safe, while rewriting a whole
JSON list each time would be slow and risky.

```python
                print(f"  {task['task_id']:<45} {model:<8} {row['status']:<14} {row['latency_s']}s")
```
This is a progress line. `:<45` pads the text to 45 characters so the
columns line up.

```python
    rows = _read_jsonl(jsonl_path)
    write_outputs(rows, out_dir)
    print(f"Wrote {len(rows)} rows to {out_dir}/results.json and results.csv")
    return rows
```
After the loops, it reads everything back from the JSONL file (including
rows from earlier resumed attempts), writes the final JSON and CSV, and
returns the rows.

### 4.7 `main`: the command line

```python
def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS, choices=sorted(PROVIDERS))
    parser.add_argument("--tasks", nargs="+", help="...")
    parser.add_argument("--limit", type=int, help="Only run the first N tasks")
    parser.add_argument("--run-id", help="Reuse to resume a previous run")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--tasks-dir", type=Path, default=TASKS_DIR)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
```
This defines the command-line options. `nargs="+"` means "one or more
values" (e.g. `--models claude gemini`). `choices=` rejects typos. `type=int`
converts `"5"` into 5. `description=__doc__` reuses the file's docstring as
the `--help` text.

```python
    run(models=args.models, tasks=args.tasks, limit=args.limit, run_id=args.run_id,
        retries=args.retries, tasks_dir=args.tasks_dir, results_dir=args.results_dir)
```
This passes the options straight to `run`.
**Why keep `main` separate from `run`?** `run` is for Python and Colab, and
`main` is for the terminal. Both share the same logic.

```python
if __name__ == "__main__":
    main()
```
This means "only call `main()` when this file is run directly". When Colab
does `from runner.run_prompts import run`, nothing runs automatically.

---

## Part 5. Choices you may want to change

- **Default model names** (`claude-sonnet-5`, `gpt-5-codex`, `gemini-2.5-pro`) are my picks. Override them with env vars.
- **Panacea** is a guess until we have its API details.
- **Plain prompt only.** Each model sees the instruction text once, with no tools and no ability to run code. That tests code *generation*. It is not the agent-in-a-sandbox setup Harbor uses, where a model can run commands in the task's Docker environment.
- **Sequential calls**, one at a time. That's slower, but simple and easy on rate limits. With 38 tasks x 4 models = 152 calls, that's fine.

## Part 6. How it was tested

- With the `echo` model, it found the tasks and wrote correct `results.json` and `results.csv` files. Resuming with the same `--run-id` skipped finished pairs.
- With fake keys, Claude and Gemini reached their real APIs and got "invalid key" errors. That confirms the requests are shaped correctly. Codex couldn't connect from my environment, so it hasn't been checked live. No model has returned a real answer yet.
