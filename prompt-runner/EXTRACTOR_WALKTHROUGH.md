# Code extractor: a beginner's walkthrough

This covers what's new since the first walkthrough: the extractor
(`runner/extract.py`) and the changes to `runner/run_prompts.py`.

---

## Part 0. What changed, in plain English

1. **Every prompt now ends with one formatting line**, the same for every
   model. It asks the model to put each file and each set of shell commands
   in a fenced code block, and to write `File: <path>` above each file.
2. **The model's reply is saved untouched**, in a column now called
   `raw_response` (it used to be called `response`).
3. **A new file, `extract.py`, finds the code in each reply** and saves it in
   `extracted_code`, along with columns that describe how it went.
4. **Extraction also works as a separate command.** If the rules turn out to
   be wrong, you fix them and re-run extraction on saved results for free,
   without calling any model again.

The new columns are:

| Column | Meaning |
|--------|---------|
| `raw_response` | The model's full reply, never changed |
| `extraction_ok` | `True` if code was found |
| `extraction_method` | How it was found, or why not (list below) |
| `n_code_blocks` | How many code blocks were kept |
| `code_languages` | Their labels, e.g. `python,bash` |
| `code_files` | File paths the model named, e.g. `/app/run.py` |
| `extracted_code` | The code, for scoring |

The possible values of `extraction_method` are:
- `fenced`: found normal code blocks
- `fenced_truncated`: found blocks, but the reply was cut off in the middle of the last one
- `whole_reply_python`: there were no code blocks, but the whole reply is valid Python
- `only_output_blocks`: the only blocks were example output
- `no_code_found`: there was no code, for example a refusal or a question
- `empty_reply`: the model returned nothing
- `no_reply`: the call failed or the model wasn't configured

**When you score later**, filter to `extraction_ok == True`. Look at the
other rows by hand, because they are the interesting failures.

---

## Part 1. A quick lesson: regular expressions

The extractor uses **regular expressions** ("regex"). A regex is a pattern
for finding text, a bit like a very powerful "find" box. A few symbols come
up below:

| Symbol | Means |
|--------|-------|
| `^` / `$` | start / end of a line (with the MULTILINE setting) |
| `.` | any character |
| `*` | "zero or more of the previous thing" |
| `*?` | same, but as *few* as possible |
| `[ \t]` | a space or a tab |
| `[^\n`]` | any character *except* a newline or a backtick |
| `( ... )` | a **group**: a part of the match we want to pull out later |
| `\1` | "the exact same text that group 1 matched" |
| `\s` / `\W` | whitespace / any character that isn't a letter, digit or underscore |
| `?` after something | that thing is optional |

In Python you write patterns as `r"..."` (a **raw string**) so that
backslashes are passed to the regex engine as they are.

---

## Part 2. `runner/extract.py`, line by line

### 2.1 The docstring and imports

The docstring at the top lists the new columns and shows how to re-run
extraction from the terminal.

```python
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import List, Optional
```
- `argparse`: reads the command-line argument (the run folder).
- `ast`: Python's own parser. We use it to check "is this text valid Python?"
- `json`: reads the saved `results.json`.
- `re`: regular expressions.
- The others you've seen before.

### 2.2 Blocks to skip

```python
SKIP_LANGUAGES = {"text", "txt", "plaintext", "output", "console", "log"}
```
This is a **set** of labels. Models often show sample output in a block
labelled `text` or `output`. That isn't code to run, so we skip it.
**Why a set?** Checking "is this label in the set" is fast, and a set can't
contain duplicates.
**A trade-off to know about:** some models label shell commands `console`
(e.g. `$ ls`). Those get skipped too. If you see that happen in real results,
remove `"console"` from this set and re-run extraction for free.

### 2.3 The pattern that finds code blocks

```python
FENCE_RE = re.compile(r"^(```|~~~)[ \t]*([^\n`]*)\n(.*?)^\1[ \t]*$", re.MULTILINE | re.DOTALL)
```
This is the heart of the extractor. Reading it left to right:
- `^(```|~~~)`: a line starting with three backticks or three tildes (both are
  valid fences in Markdown). This is **group 1**.
- `[ \t]*`: optional spaces after the fence.
- `([^\n`]*)`: the label, e.g. `python`. This is **group 2**, and it may be empty.
- `\n`: the end of the opening line.
- `(.*?)`: the code itself, **group 3**. `*?` takes as little as possible, so
  it stops at the *first* closing fence instead of running on to the last
  one in the reply.
- `^\1[ \t]*$`: a line containing the *same* fence that opened the block (`\1`).

The two flags change how the pattern behaves:
- `re.MULTILINE`: `^` and `$` match at the start and end of every line, not
  just the whole text.
- `re.DOTALL`: `.` also matches newlines, so the code can span many lines.

`re.compile` prepares the pattern once, instead of every time it's used.
**Why ALL_CAPS?** It's a constant, just like `FIELDS`.

### 2.4 The pattern that finds file names

```python
FILE_RE = re.compile(r"^\W*File:\s*`?([^\s`*]+)`?\W*$", re.IGNORECASE)
```
This matches the `File: /app/run.py` line we asked for, even if the model
decorates it:
- `^\W*`: allows leading symbols like `**` (bold) or `#` (heading).
- `File:\s*`: the word "File:" and any spaces after it.
- `` `? ``: an optional backtick around the path.
- `([^\s`*]+)`: the path itself (group 1): one or more characters that
  aren't spaces, backticks or asterisks.
- `\W*$`: allows trailing symbols like `**`.
- `re.IGNORECASE`: "file:" and "FILE:" also match.

So `File: /app/run.py`, `**File: `/app/run.py`**` and `### file: /app/run.py`
all give `/app/run.py`.

### 2.5 `_file_above`

```python
def _file_above(text: str, block_start: int) -> str:
    lines = [line for line in text[:block_start].splitlines() if line.strip()]
    if lines:
        match = FILE_RE.match(lines[-1])
        if match:
            return match.group(1)
    return ""
```
This is given the whole reply and the position where a block starts.
- `text[:block_start]` is all the text *before* the block.
- `.splitlines()` splits it into lines, and `if line.strip()` drops empty ones.
- `lines[-1]` is the last of those lines, the one right above the block.
- If that line matches `FILE_RE`, it returns the path (group 1). Otherwise
  it returns an empty string.

**Why only the line right above?** That's where we asked the model to put
it. Looking further up risks picking up a path that belongs to a different
block.

### 2.6 `extract_code`: the main function

```python
def extract_code(text: str) -> dict:
    result = {
        "extracted_code": "",
        "extraction_ok": False,
        "extraction_method": "none",
        "n_code_blocks": 0,
        "code_languages": "",
        "code_files": "",
    }
```
It starts with a "nothing found" result. Each path through the function
below fills in what it found. Starting from a full set of keys means every
row always has every column.

```python
    if not text or not text.strip():
        result["extraction_method"] = "empty_reply"
        return result
```
If the reply is empty or only whitespace, it stops early and says why.

```python
    fence_lines = re.findall(r"^(?:```|~~~)", text, re.MULTILINE)
    truncated = len(fence_lines) % 2 == 1
    if truncated:
        text = text.rstrip("\n") + "\n" + fence_lines[-1] + "\n"
```
This handles cut-off replies. Every block has an opening and a closing
fence, so a complete reply has an **even** number of fence lines. `% 2 == 1`
means "odd", which is what happens when the model hit its length limit in the
middle of a block. In that case we add a closing fence at the end so the
last block still counts, and remember `truncated = True` so it shows up in
`extraction_method`.
(`(?: ... )` is a group that doesn't capture. We only want to count the
fences here, not pull anything out of them.)
**Why?** Long coding answers are the most likely to hit the limit, and
throwing away almost-complete code would bias scores against thorough models.
This only works on our copy of `text`. The saved `raw_response` isn't changed.

```python
    pieces, languages, files = [], [], []
```
These are three empty lists, filled as we go through the blocks.

```python
    for match in FENCE_RE.finditer(text):
        language = match.group(2).strip().lower()
        if language in SKIP_LANGUAGES:
            continue
```
`finditer` goes through every code block in order. For each one we read
the label (group 2), trim spaces and lowercase it, so `Python` and `python`
count as the same. Output blocks are skipped.

```python
        code = match.group(3).rstrip("\n")
        path = _file_above(text, match.start())
```
`code` is the inside of the block, without trailing blank lines. `path` is
the file name above it, if any. `match.start()` is where the block begins in
the text.

```python
        header = f"# ---- {path or 'block ' + str(len(pieces) + 1)} ({language or 'no label'}) ----"
        pieces.append(f"{header}\n{code}")
        languages.append(language or "none")
        if path:
            files.append(path)
```
This builds a separator line such as `# ---- /app/run.py (python) ----`, or
`# ---- block 2 (bash) ----` when there's no file name. `x or y` means "x if
it isn't empty, otherwise y". Then it stores the block with its header, its
language and its file path.
**Why a header?** When blocks are joined, you can still see where each one
starts and which file it belongs to. It starts with `#` because that's a
comment in both Python and shell.

```python
    if pieces:
        joined = pieces[0].split("\n", 1)[1] if len(pieces) == 1 else "\n\n".join(pieces)
```
If we kept at least one block:
- **exactly one block:** we remove its header line (`split("\n", 1)[1]` means
  "everything after the first line"), so `extracted_code` is just the code.
  That's cleanest for scoring against a single reference solution.
- **several blocks:** we join them with a blank line between them, in the
  order they appeared.

```python
        result.update(
            extracted_code=joined,
            extraction_ok=True,
            extraction_method="fenced_truncated" if truncated else "fenced",
            n_code_blocks=len(pieces),
            code_languages=",".join(languages),
            code_files=",".join(files),
        )
        return result
```
This fills in the result. The lists become comma-separated text, because
CSV cells can't hold lists.

```python
    if FENCE_RE.search(text):
        result["extraction_method"] = "only_output_blocks"
        return result
```
If we get here, no block was kept. If blocks *did* exist, they must all have
been output blocks, so it says so.

```python
    stripped = text.strip()
    if len(stripped.splitlines()) >= 2:
        try:
            ast.parse(stripped)
        except SyntaxError:
            pass
        else:
            result.update(
                extracted_code=stripped,
                extraction_ok=True,
                extraction_method="whole_reply_python",
                n_code_blocks=1,
                code_languages="python",
            )
            return result
```
This is the fallback for replies with no fences at all. `ast.parse` tries to
read the text as Python. If that fails, it raises `SyntaxError`, which means
it isn't Python, so we `pass` (do nothing). `try / except / else` means the
`else` part runs only if **no** error happened.
**Why require 2+ lines?** A one-word reply like `hello` is technically valid
Python (it's just a variable name), but it clearly isn't code. Normal prose
like "I can't do that" fails `ast.parse`, so it isn't mistaken for code.
**Why only Python?** It's the one language Python can check for free. A
bare shell script with no fences is marked `no_code_found` so a person looks
at it. With the formatting line added, this case should be rare.

```python
    result["extraction_method"] = "no_code_found"
    return result
```
Nothing matched: a refusal, a clarifying question or plain prose.

### 2.7 `add_extraction`

```python
def add_extraction(rows: List[dict]) -> List[dict]:
    for row in rows:
        if row.get("status") == "ok":
            row.update(extract_code(row.get("raw_response", "")))
        else:
            row.update(extract_code(""), extraction_method="no_reply")
    return rows
```
This runs `extract_code` on every successful row and adds the result's
columns to the row. Failed rows get the empty columns with the method
`no_reply`, so an API error isn't confused with "the model answered without
code". `dict.update(a, key=value)` adds everything from `a`, then sets
`key`, which overrides `empty_reply` here.

### 2.8 `main`: re-running extraction from the terminal

```python
def main(argv: Optional[List[str]] = None) -> None:
    from .run_prompts import write_outputs
```
This import is inside the function on purpose. `run_prompts.py` imports
`extract.py`, so if `extract.py` also imported `run_prompts.py` at the top,
each would be waiting for the other to load. That's a **circular import**,
and Python fails on it. Importing inside the function delays it until both
files are loaded.
**Why reuse `write_outputs`?** The CSV and JSON are then written exactly the
same way as during a run, with the same columns in the same order.

```python
    parser = argparse.ArgumentParser(description="Re-run code extraction on a saved run.")
    parser.add_argument("run_dir", type=Path, help="Folder containing results.json")
    args = parser.parse_args(argv)
```
This defines one required argument: the run folder. It has no `--` because
it's a **positional** argument, meaning you type just the path.

```python
    rows = json.loads((args.run_dir / "results.json").read_text())
    add_extraction(rows)
    write_outputs(rows, args.run_dir)
    ok = sum(1 for r in rows if r["extraction_ok"])
    print(f"Extracted code from {ok}/{len(rows)} rows in {args.run_dir}")
```
This reads the saved results, re-extracts and overwrites `results.json` and
`results.csv`. It then prints a count, e.g. `Extracted code from 140/152 rows`.
`sum(1 for ...)` counts the rows where extraction worked.
This overwrites only the extraction columns. `raw_response` is copied
through unchanged, and `results.jsonl` (the raw log) isn't touched at all.

```python
if __name__ == "__main__":
    main()
```
As before, this runs `main()` only when the file is run directly.

---

## Part 3. Changes to `runner/run_prompts.py`

```python
from .extract import add_extraction
```
This brings in the extractor.

```python
FORMAT_INSTRUCTION = (
    "\n\n---\n"
    "Format your answer like this: put each file and each set of shell commands "
    "in its own fenced code block (```), with the language after the opening fence. "
    "On the line directly above a file's code block, write its path, "
    "for example: File: /app/run.py"
)
```
This is the line you approved on the card. Python joins strings that sit
next to each other inside parentheses into one string, which lets a long
sentence span several lines of code. `\n\n---\n` adds a blank line and a
divider so the instruction sits clearly apart from the task text.
**Why these exact words?** Each part feeds a rule in the extractor: "fenced
code block" feeds `FENCE_RE`, "language after the fence" gives us
`code_languages`, and "File: path" feeds `FILE_RE`.
**Why `/app/run.py` as the example?** The tasks in this dataset put their
files under `/app`, so the example matches what models will actually write.

```python
    "raw_response",
    "extraction_ok",
    "extraction_method",
    "n_code_blocks",
    "code_languages",
    "code_files",
    "extracted_code",
```
These are the new columns at the end of `FIELDS`. `response` was renamed to
`raw_response`, as agreed. The long text columns come last so the short
columns are easy to read in a spreadsheet.

```python
    format_instruction: bool = True,
```
This is a new option for `run()`. It's on by default.
**Why an off switch?** If someone later wants to compare "with the format
line" against "task text only", they can.

```python
    suffix = FORMAT_INSTRUCTION if format_instruction else ""
    ...
                    prompt=task["prompt"] + suffix,
    ...
                    result = _call_with_retries(PROVIDERS[model], row["prompt"], retries)
```
This builds the full prompt once and sends exactly that.
**Why save `row["prompt"]` and send it?** The `prompt` column then shows
exactly what the model received, format line included. Your results never
misrepresent the input.

```python
                        raw_response=result.text,
```
The reply is saved under its new name.

```python
    rows = add_extraction(_read_jsonl(jsonl_path))
```
At the end of a run, before writing the JSON and CSV, every row gets its
extraction columns. The `results.jsonl` log keeps only the raw data, which
is why extraction can always be redone later.

```python
    parser.add_argument("--no-format-instruction", action="store_true", help="Send the task text unchanged")
    ...
        format_instruction=not args.no_format_instruction,
```
This is the command-line version of the off switch. `action="store_true"`
makes it a flag that is `True` when present and `False` when absent. It
isn't used by default.

`runner/README.md` also gained a short "Code extraction" section and the
new column list.

---

## Part 4. How it was tested

I ran `extract_code` on ten made-up replies:

| Reply | Result |
|-------|--------|
| One Python block | `fenced`, 1 block |
| A file block + a bash block + an output block | `fenced`, 2 blocks (output skipped), file `/app/a.py` found |
| `**File: `/app/run.py`**` above a block | file path found despite the bold and backticks |
| Plain Python, no fences | `whole_reply_python` |
| A sentence of prose | `no_code_found` |
| The single word `hello` | `no_code_found` (the 2-line rule works) |
| Only an output block | `only_output_blocks` |
| A block cut off mid-way | `fenced_truncated`, code kept |
| A `~~~` block | `fenced` |
| Empty reply | `empty_reply` |

I also ran a full run on 2 tasks with a fake model that returns a
`File: /app/x.py` block, the `echo` model and an unconfigured Panacea. The
fake rows extracted `print('hi')` with the file path, echo got
`no_code_found`, and Panacea got `no_reply`. Every prompt ended with the
format line. Re-running `python -m runner.extract` on that folder gave the
same result.

**Not tested yet:** replies from real models. Once you have a first real
run, look at the rows where `extraction_ok` is false to see whether any rule
needs adjusting.

## Part 5. Known limits

- A code block that *contains* another fenced block (e.g. a Markdown file
  with code inside it) will be cut short at the inner fence.
- Shell blocks labelled `console` are skipped (see 2.2).
- If a reply has code in both fences *and* plain text, only the fenced code is kept.
