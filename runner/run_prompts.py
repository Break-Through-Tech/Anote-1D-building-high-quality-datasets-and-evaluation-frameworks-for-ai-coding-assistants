"""Send every task prompt to each model and save the responses.

Reads ``data/tasks/<category>/<task>/instruction.md``, adds one formatting
line (FORMAT_INSTRUCTION) so code is easy to pull out, sends it to each
selected model, and writes one row per (task, model) to:

    results/<run_id>/results.jsonl   appended as each call finishes
    results/<run_id>/results.json    full list, written at the end
    results/<run_id>/results.csv     same rows, for spreadsheets / pandas

Re-running with the same ``--run-id`` skips pairs that already succeeded, so
an interrupted run (e.g. a Colab disconnect) can pick up where it left off.

Each row keeps the model's full reply in ``raw_response`` and the code pulled
out of it in ``extracted_code`` (see extract.py).

CLI:
    python -m runner.run_prompts --models claude codex gemini panacea
    python -m runner.run_prompts --models echo --limit 3      # offline check

Python / Colab:
    from runner.run_prompts import run
    rows = run(models=["claude", "gemini"], limit=5)
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

from .extract import add_extraction
from .providers import DEFAULT_MODELS, PROVIDERS, ProviderNotConfigured

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "data" / "tasks"
RESULTS_DIR = REPO_ROOT / "results"

# Added to the end of every prompt, the same for every model.
FORMAT_INSTRUCTION = (
    "\n\n---\n"
    "Format your answer like this: put each file and each set of shell commands "
    "in its own fenced code block (```), with the language after the opening fence. "
    "On the line directly above a file's code block, write its path, "
    "for example: File: /app/run.py"
)

FIELDS = [
    "run_id",
    "timestamp",
    "task_id",
    "category",
    "difficulty",
    "model",
    "model_name",
    "status",
    "latency_s",
    "input_tokens",
    "output_tokens",
    "error",
    "prompt",
    "raw_response",
    "extraction_ok",
    "extraction_method",
    "n_code_blocks",
    "code_languages",
    "code_files",
    "extracted_code",
]


def load_tasks(tasks_dir: Path = TASKS_DIR, only: Optional[Iterable[str]] = None) -> List[dict]:
    """Return one dict per task folder that has an instruction.md."""
    wanted = set(only) if only else None
    tasks = []
    for path in sorted(tasks_dir.glob("*/*/instruction.md")):
        task_dir = path.parent
        task_id = f"{task_dir.parent.name}/{task_dir.name}"
        if wanted and task_id not in wanted and task_dir.name not in wanted:
            continue
        difficulty = ""
        toml_path = task_dir / "task.toml"
        if tomllib and toml_path.exists():
            try:
                meta = tomllib.loads(toml_path.read_text()).get("metadata", {})
                difficulty = meta.get("difficulty", "")
            except tomllib.TOMLDecodeError:
                pass
        tasks.append(
            {
                "task_id": task_id,
                "category": task_dir.parent.name,
                "difficulty": difficulty,
                "prompt": path.read_text(),
            }
        )
    return tasks


def _call_with_retries(fn, prompt: str, retries: int):
    for attempt in range(retries + 1):
        try:
            return fn(prompt)
        except ProviderNotConfigured:
            raise
        except ImportError as e:
            raise ProviderNotConfigured(f"{e}. Run: pip install -r requirements.txt") from e
        except Exception:
            if attempt == retries:
                raise
            time.sleep(2 ** (attempt + 1))


def _done_pairs(jsonl_path: Path) -> set:
    done = set()
    if jsonl_path.exists():
        for line in jsonl_path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("status") == "ok":
                    done.add((row["task_id"], row["model"]))
    return done


def _read_jsonl(jsonl_path: Path) -> List[dict]:
    """Latest row per (task, model), so retried pairs replace earlier failures."""
    latest = {}
    for line in jsonl_path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            latest[(row["task_id"], row["model"])] = row
    return list(latest.values())


def write_outputs(rows: List[dict], out_dir: Path) -> None:
    (out_dir / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    with open(out_dir / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run(
    models: Optional[List[str]] = None,
    tasks: Optional[List[str]] = None,
    limit: Optional[int] = None,
    run_id: Optional[str] = None,
    retries: int = 2,
    tasks_dir: Path = TASKS_DIR,
    results_dir: Path = RESULTS_DIR,
    format_instruction: bool = True,
) -> List[dict]:
    models = models or DEFAULT_MODELS
    unknown = [m for m in models if m not in PROVIDERS]
    if unknown:
        raise ValueError(f"Unknown model(s) {unknown}; choose from {sorted(PROVIDERS)}")

    task_list = load_tasks(tasks_dir, tasks)[:limit]
    suffix = FORMAT_INSTRUCTION if format_instruction else ""
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(results_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "results.jsonl"
    done = _done_pairs(jsonl_path)
    skipped_models = set()

    print(f"Run {run_id}: {len(task_list)} tasks x {len(models)} models -> {out_dir}")
    with open(jsonl_path, "a", encoding="utf-8") as jsonl:
        for task in task_list:
            for model in models:
                if (task["task_id"], model) in done or model in skipped_models:
                    continue
                row = {k: "" for k in FIELDS}
                row.update(
                    run_id=run_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    task_id=task["task_id"],
                    category=task["category"],
                    difficulty=task["difficulty"],
                    model=model,
                    prompt=task["prompt"] + suffix,
                )
                start = time.perf_counter()
                try:
                    result = _call_with_retries(PROVIDERS[model], row["prompt"], retries)
                    row.update(
                        status="ok",
                        model_name=result.model_name,
                        raw_response=result.text,
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                    )
                except ProviderNotConfigured as e:
                    # Record it once and stop calling this model for the rest of the run.
                    row.update(status="not_configured", error=str(e))
                    skipped_models.add(model)
                    print(f"  skipping {model}: {e}")
                except Exception as e:
                    row.update(status="error", error=f"{type(e).__name__}: {e}")
                row["latency_s"] = round(time.perf_counter() - start, 3)
                jsonl.write(json.dumps(row, ensure_ascii=False) + "\n")
                jsonl.flush()
                print(f"  {task['task_id']:<45} {model:<8} {row['status']:<14} {row['latency_s']}s")

    rows = add_extraction(_read_jsonl(jsonl_path))
    write_outputs(rows, out_dir)
    print(f"Wrote {len(rows)} rows to {out_dir}/results.json and results.csv")
    return rows


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS, choices=sorted(PROVIDERS))
    parser.add_argument("--tasks", nargs="+", help="Task ids (e.g. coding_tasks/pypi-server) or folder names")
    parser.add_argument("--limit", type=int, help="Only run the first N tasks")
    parser.add_argument("--run-id", help="Reuse to resume a previous run")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--tasks-dir", type=Path, default=TASKS_DIR)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--no-format-instruction", action="store_true", help="Send the task text unchanged")
    args = parser.parse_args(argv)
    run(
        models=args.models,
        tasks=args.tasks,
        limit=args.limit,
        run_id=args.run_id,
        retries=args.retries,
        tasks_dir=args.tasks_dir,
        results_dir=args.results_dir,
        format_instruction=not args.no_format_instruction,
    )


if __name__ == "__main__":
    main()
