# Panacea adapter: a beginner's walkthrough

This covers what's new since the extractor walkthrough:
- `call_panacea` in `runner/providers.py` now runs Anote's `anote` tool instead of the old placeholder.
- One new rule in `runner/extract.py`: if the same file shows up twice, keep only the last version.
- The README has new Panacea setup notes.

---

## Part 0. What changed, in plain English

Panacea isn't reached through a web API like Claude or Gemini. We decided to
test its **command-line tool**, `anote`, the program you'd normally type
commands into in a terminal. So for each task, the runner now:

1. makes a brand-new empty folder
2. runs `anote ask --no-edit` inside it and types the prompt into it
3. collects everything the tool prints
4. cleans off the decoration and keeps the answer

In Python, "run another program and collect what it prints" is done with
the **`subprocess`** module. That's the main new idea in this walkthrough.

**Setup you'll need** (also in the README):
```bash
npm install -g @anote-ai/anote        # installs the anote tool (needs Node.js; Colab has it)
export ANTHROPIC_API_KEY=...          # anote runs on Claude, so it uses your Anthropic key
```

---

## Part 1. New imports and patterns at the top of `providers.py`

```python
import os
import re
import shlex
import shutil
import subprocess
import tempfile
```
- `json` and `urllib.request` were **removed**. Only the old placeholder used them.
- `re`: regular expressions, which you met in the extractor walkthrough.
- `shlex`: splits a command string like `"npx anote"` into `["npx", "anote"]`, the way a terminal would.
- `shutil`: its `which` function checks whether a program is installed.
- `subprocess`: runs another program from Python.
- `tempfile`: creates temporary folders that delete themselves.

```python
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
```
Terminal programs add colour using hidden **ANSI codes**, like `\x1b[32m`
(meaning "switch to green"). `\x1b` is the invisible "escape" character.
Reading the pattern:
- `\x1b\[`: escape, then `[`
- `[0-9;?]*`: any digits, semicolons or question marks
- `[A-Za-z]`: one letter that ends the code

We delete these so the saved answer is plain text.

```python
RULE_LINE_RE = re.compile(r"^\s*─+(\s*Anote\s*─+)?\s*$")
```
This matches the decorative lines the tool prints above and below its answer:
`── Anote ──────────` and a plain `──────────`.
- `─+`: one or more box-drawing line characters (not ordinary dashes)
- `(\s*Anote\s*─+)?`: optionally, the word "Anote" followed by more line characters
- `^\s*` and `\s*$`: nothing else on the line apart from spaces

```python
PROGRESS_LINE_RE = re.compile(r"^\s*•\s")
```
While it works, the tool prints progress notes such as `  • Writing /app/add.py`.
Those aren't part of the answer. This pattern matches a line that starts
with a `•` bullet (after optional spaces) followed by a space.
**Why not remove all bullet points?** Models write lists with `-` or `*`.
The `•` character is the tool's own marker, so this only removes its notes.
**How I found it:** the test run (Part 5) showed this line in the saved
answer, so I added the pattern.

---

## Part 2. `call_panacea`, line by line

```python
def call_panacea(prompt: str) -> Completion:
    """Panacea, through Anote's ``anote`` command-line tool. ..."""
```
It takes the same input and returns the same `Completion` shape as the
other three models, so the main loop doesn't need to know Panacea works
differently. This is the payoff of the design from the first walkthrough.

```python
    command = shlex.split(os.environ.get("PANACEA_CMD", "anote"))
```
This picks which program to run. The default is `anote`. You can set
`PANACEA_CMD="npx anote"` if you installed it without `-g`. `shlex.split`
turns that into the list `["npx", "anote"]`, which is the form `subprocess`
expects.

```python
    if shutil.which(command[0]) is None:
        raise ProviderNotConfigured(
            f"'{command[0]}' not found. Install it with: npm install -g @anote-ai/anote"
        )
```
`shutil.which("anote")` looks for the program the same way your terminal
does. It returns None if the program isn't installed. In that case we raise
our "not configured" error, so the run skips Panacea once with a helpful
message instead of failing 38 times.

```python
    _require_env("ANTHROPIC_API_KEY")  # anote refuses to start without it
```
This reuses the helper from the first walkthrough.
**Why check here?** In my test, the tool stopped with "ANTHROPIC_API_KEY is
not set". Checking first turns that into a clean `not_configured` row.

```python
    timeout = float(os.environ.get("PANACEA_TIMEOUT", "900"))
```
This is the maximum number of seconds to wait for one task: 900 seconds is
15 minutes. The tool thinks in steps (plan, explore and so on), so it's
slower than a plain API call. The task files in your dataset also give
agents 900 seconds, so this matches.

```python
    with tempfile.TemporaryDirectory() as workdir:
```
This creates a new empty folder with a random name, e.g. `/tmp/tmpab12cd`,
and stores its path in `workdir`. When the indented block ends, Python
**deletes the folder automatically**, even if an error happened.
**Why?** `--no-edit` stops the tool from *editing* files, but it can still
*read* files and look around. An empty folder means it can't read your
repo or your results, and every task starts from the same clean state,
which keeps the comparison fair.

```python
        proc = subprocess.run(
            command + ["ask", "--no-edit", "--dir", workdir],
```
This runs the program. The full command is
`anote ask --no-edit --dir /tmp/tmpab12cd`:
- `ask`: the tool's "answer a question" command
- `--no-edit`: read-only mode, so no file changes
- `--dir workdir`: tells the tool to treat the empty folder as its project

```python
            input=prompt,
```
This types the prompt into the tool through **standard input** (stdin). The
tool's help text says it reads stdin when no question is given on the
command line.
**Why not put the prompt in the command itself?** Task prompts are long
and full of quotes, backticks and newlines. On a command line those can be
misread or hit length limits. Stdin passes the text through exactly.

```python
            capture_output=True,
            text=True,
```
`capture_output=True` saves what the program prints instead of showing it
on screen. It gives us `proc.stdout` (normal output, where the answer
goes) and `proc.stderr` (the error stream, where the "Thinking…" spinner
goes). `text=True` gives us these as strings rather than raw bytes.

```python
            cwd=workdir,
            timeout=timeout,
```
`cwd` ("current working directory") starts the program inside the empty
folder too, as a second layer of safety. `timeout` stops it if it runs too
long. Python then raises `TimeoutExpired`, which the main loop records as an
`error` row.

```python
            env={**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0"},
        )
```
`env` sets the environment variables the program sees.
`{**os.environ, ...}` means "copy all current variables (including your API
key), then add these two". `NO_COLOR` and `FORCE_COLOR=0` are common
settings that ask terminal programs not to add colour codes. `ANSI_RE` above
is the backup in case they're ignored.

```python
    if proc.returncode != 0:
        raise RuntimeError(f"anote exited with code {proc.returncode}: {proc.stderr.strip()[-500:]}")
```
Every program returns an **exit code** when it finishes: 0 means success,
and anything else means failure. On failure we raise an error that includes
the last 500 characters of the error stream (`[-500:]`), which is usually
where the explanation is, so the `error` column says what went wrong.

```python
    return Completion(text=_clean_cli_output(proc.stdout), model_name="anote-cli")
```
This cleans the output and returns it in the common shape. There are no
token counts, because the tool doesn't print any, so those columns stay
empty for Panacea. The `model_name` is `anote-cli` because the tool doesn't
say which Claude model it used.

### `_clean_cli_output`

```python
def _clean_cli_output(text: str) -> str:
    text = ANSI_RE.sub("", text)
```
`sub("", text)` replaces every colour code with nothing, which removes them.

```python
    kept = [
        line
        for line in text.splitlines()
        if not RULE_LINE_RE.match(line) and not PROGRESS_LINE_RE.match(line)
    ]
    return "\n".join(kept).strip()
```
This is a list comprehension spread over several lines for readability. It
keeps every line that is **not** a decorative line and **not** a progress
line. Then it glues the lines back together with newlines and trims blank
space from the start and end.
**Why a separate function?** It can be tested on its own with fake output
(I did, in Part 5) without running the real tool.

---

## Part 3. The extractor change: repeated files

In the test, Panacea wrote `/app/add.py`, got told it couldn't edit files,
and then showed the same file again for you to copy. The extractor saved
both copies, which would double-count that code during scoring. The new rule
is: **if the same file path appears more than once, keep only the last
version.** The last version is the model's final word.

```python
    blocks = []  # one (path, language, code) per block we keep
    for match in FENCE_RE.finditer(text):
        language = match.group(2).strip().lower()
        if language in SKIP_LANGUAGES:
            continue
        code = match.group(3).rstrip("\n")
        path = _file_above(text, match.start())
        blocks.append((path, language, code))
```
This is the same loop as before, but instead of building the output text
right away, it first collects each block as a **tuple** `(path, language, code)`.
**Why the change?** We need to see *all* the blocks before we can tell which
ones are repeats.

```python
    last_index = {path: i for i, (path, _, _) in enumerate(blocks) if path}
```
This is a dictionary comprehension. `enumerate` gives each block's position
`i` (0, 1, 2…). `(path, _, _)` unpacks the tuple. `_` is a convention for
"I don't need this value". For every block that has a path, we store
`path → position`. When a path repeats, the later position overwrites the
earlier one, so each path ends up pointing at its **last** block.
Example: blocks at positions 0 and 1 are both `/app/add.py`, so
`last_index = {"/app/add.py": 1}`.

```python
    blocks = [b for i, b in enumerate(blocks) if not b[0] or last_index[b[0]] == i]
```
This keeps a block if **either** it has no path (`not b[0]`, where `b[0]` is
the path), because unnamed blocks are never treated as repeats, **or** it's
the last block for its path. Everything else is dropped, and the order stays
the same.

```python
    if blocks:
        pieces = []
        for number, (path, language, code) in enumerate(blocks, start=1):
            header = f"# ---- {path or 'block ' + str(number)} ({language or 'no label'}) ----"
            pieces.append(f"{header}\n{code}")
```
Now we build the headers, as before. `enumerate(..., start=1)` numbers the
blocks 1, 2, 3 instead of 0, 1, 2, so unnamed blocks are labelled `block 2`
and so on.

```python
        joined = blocks[0][2] if len(blocks) == 1 else "\n\n".join(pieces)
```
If there's one block, we keep just its code (`blocks[0][2]` is the third
item, the code) with no header. If there are several, we join them with
their headers. This is the same behaviour as before, written for the new
tuple format.

```python
            n_code_blocks=len(blocks),
            code_languages=",".join(language or "none" for _, language, _ in blocks),
            code_files=",".join(path for path, _, _ in blocks if path),
```
These fill the same columns as before, now worked out from the tuples. These
are **generator expressions**: loops inside `join`. Because repeats were
removed first, `code_files` lists each file once.

---

## Part 4. README changes

- Setup: the placeholder's `PANACEA_API_URL` and `PANACEA_API_KEY` are gone. You now run `npm install -g @anote-ai/anote`.
- Colab: a new `!npm install -g @anote-ai/anote` line, and `"panacea"` is added to the example run.
- A rewritten Panacea section explains the three steps and the two settings (`PANACEA_CMD`, `PANACEA_TIMEOUT`).
- `PANACEA_MODEL` was removed, because the tool doesn't let us choose a model.

---

## Part 5. How it was tested

1. **No key set:** the Panacea row was `not_configured` with the message "Set the ANTHROPIC_API_KEY environment variable".
2. **A real run** on a small practice task ("Write a Python function `add(a, b)` in /app/add.py"): the tool answered in **17 seconds**, the row was `ok`, and extraction found `/app/add.py`. That run showed the two problems fixed above: a `• Writing /app/add.py` line in the answer, and the same file extracted twice.
3. **After the fixes**, I tested with fake tool output: colour codes, decorative lines and progress lines were all removed, and a file written twice was kept once (the last version). I re-ran the earlier extractor test cases and they give the same results as before.

**Something to know:** the real run used this cloud environment's own Claude
login, because the tool sits on top of Claude Code, which found that login.
On your computer or in Colab it will use your `ANTHROPIC_API_KEY`. I haven't
run it on one of the 38 real tasks, since those are much bigger.

## Part 6. Things to keep in mind when comparing results

- **Panacea is Claude underneath.** The `anote` tool uses Anthropic's Claude Agent SDK, so its results are "Claude plus Anote's system prompt and workflow". Differences from the plain Claude rows show what Anote's layer adds or loses.
- **It behaves like an agent.** Even with `--no-edit`, it may try to write files, be told no, and then show the code instead (as in the test). The extractor handles that.
- **It's slower.** Expect tens of seconds per task instead of a few. Latency comparisons should keep this in mind.
- **A timeout counts as an error, and the error is retried.** With the default of 2 retries, one stuck task could take up to 45 minutes. If that happens, lower `PANACEA_TIMEOUT` or run with `--retries 0`.
