"""Pull the code out of each model reply.

The raw reply is never changed. Extraction adds these columns next to it:

    extracted_code      the code, ready for scoring
    extraction_ok       True if code was found
    extraction_method   how it was found (see extract_code)
    n_code_blocks       how many code blocks were kept
    code_languages      language labels of those blocks, e.g. "python,bash"
    code_files          file paths named above blocks, e.g. "/app/run.py"

run_prompts.py calls this automatically at the end of a run. You can also
re-run it on saved results (no API calls) after changing the rules below:

    python -m runner.extract results/20260926T125640Z
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import List, Optional

# Blocks with these labels are usually example output, not code to run.
SKIP_LANGUAGES = {"text", "txt", "plaintext", "output", "console", "log"}

# A fenced block: ``` or ~~~, an optional label, the code, then the same fence again.
FENCE_RE = re.compile(r"^(```|~~~)[ \t]*([^\n`]*)\n(.*?)^\1[ \t]*$", re.MULTILINE | re.DOTALL)

# The line we ask models to write above each file, e.g. "File: /app/run.py".
FILE_RE = re.compile(r"^\W*File:\s*`?([^\s`*]+)`?\W*$", re.IGNORECASE)


def _file_above(text: str, block_start: int) -> str:
    """Return the file path written on the last non-empty line before a block."""
    lines = [line for line in text[:block_start].splitlines() if line.strip()]
    if lines:
        match = FILE_RE.match(lines[-1])
        if match:
            return match.group(1)
    return ""


def extract_code(text: str) -> dict:
    """Find the code in one reply and describe how it was found."""
    result = {
        "extracted_code": "",
        "extraction_ok": False,
        "extraction_method": "none",
        "n_code_blocks": 0,
        "code_languages": "",
        "code_files": "",
    }
    if not text or not text.strip():
        result["extraction_method"] = "empty_reply"
        return result

    # A reply cut off by the length limit can end inside a block. Closing it
    # lets that last block still count.
    fence_lines = re.findall(r"^(?:```|~~~)", text, re.MULTILINE)
    truncated = len(fence_lines) % 2 == 1
    if truncated:
        text = text.rstrip("\n") + "\n" + fence_lines[-1] + "\n"

    blocks = []  # one (path, language, code) per block we keep
    for match in FENCE_RE.finditer(text):
        language = match.group(2).strip().lower()
        if language in SKIP_LANGUAGES:
            continue
        code = match.group(3).rstrip("\n")
        path = _file_above(text, match.start())
        blocks.append((path, language, code))

    # If the same file is written more than once, keep only its last version.
    last_index = {path: i for i, (path, _, _) in enumerate(blocks) if path}
    blocks = [b for i, b in enumerate(blocks) if not b[0] or last_index[b[0]] == i]

    if blocks:
        pieces = []
        for number, (path, language, code) in enumerate(blocks, start=1):
            header = f"# ---- {path or 'block ' + str(number)} ({language or 'no label'}) ----"
            pieces.append(f"{header}\n{code}")
        # One block needs no header; several are joined in the order they appeared.
        joined = blocks[0][2] if len(blocks) == 1 else "\n\n".join(pieces)
        result.update(
            extracted_code=joined,
            extraction_ok=True,
            extraction_method="fenced_truncated" if truncated else "fenced",
            n_code_blocks=len(blocks),
            code_languages=",".join(language or "none" for _, language, _ in blocks),
            code_files=",".join(path for path, _, _ in blocks if path),
        )
        return result

    if FENCE_RE.search(text):
        result["extraction_method"] = "only_output_blocks"
        return result

    # No fences: accept the whole reply only if it is valid Python on 2+ lines.
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

    result["extraction_method"] = "no_code_found"
    return result


def add_extraction(rows: List[dict]) -> List[dict]:
    """Add the extraction columns to every row. Failed calls get empty values."""
    for row in rows:
        if row.get("status") == "ok":
            row.update(extract_code(row.get("raw_response", "")))
        else:
            row.update(extract_code(""), extraction_method="no_reply")
    return rows


def main(argv: Optional[List[str]] = None) -> None:
    # Imported here, not at the top, because run_prompts imports this file too.
    from .run_prompts import write_outputs

    parser = argparse.ArgumentParser(description="Re-run code extraction on a saved run.")
    parser.add_argument("run_dir", type=Path, help="Folder containing results.json")
    args = parser.parse_args(argv)

    rows = json.loads((args.run_dir / "results.json").read_text())
    add_extraction(rows)
    write_outputs(rows, args.run_dir)
    ok = sum(1 for r in rows if r["extraction_ok"])
    print(f"Extracted code from {ok}/{len(rows)} rows in {args.run_dir}")


if __name__ == "__main__":
    main()
