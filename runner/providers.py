"""Model adapters.

Each provider takes a plain prompt string and returns a ``Completion``.
API keys and model names come from environment variables so nothing secret
lives in the repo. SDKs are imported lazily, so you only need to install the
ones for the models you actually run.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, Dict, Optional

DEFAULT_MAX_TOKENS = int(os.environ.get("RUNNER_MAX_TOKENS", "8192"))

# Terminal colour codes, e.g. "\x1b[32m", which the anote tool may print.
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# The decorative lines the anote tool prints around its answer.
RULE_LINE_RE = re.compile(r"^\s*─+(\s*Anote\s*─+)?\s*$")
# Progress lines such as "  • Writing /app/add.py" printed while it works.
PROGRESS_LINE_RE = re.compile(r"^\s*•\s")


@dataclass
class Completion:
    text: str
    model_name: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class ProviderNotConfigured(RuntimeError):
    """Raised when a provider is missing its API key or endpoint."""


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ProviderNotConfigured(f"Set the {name} environment variable.")
    return value


def call_claude(prompt: str) -> Completion:
    import anthropic

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
    client = anthropic.Anthropic(api_key=_require_env("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=model,
        max_tokens=DEFAULT_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    return Completion(
        text=text,
        model_name=resp.model,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )


def call_codex(prompt: str) -> Completion:
    from openai import OpenAI

    model = os.environ.get("CODEX_MODEL", "gpt-5-codex")
    client = OpenAI(api_key=_require_env("OPENAI_API_KEY"))
    resp = client.responses.create(model=model, input=prompt)
    usage = getattr(resp, "usage", None)
    return Completion(
        text=resp.output_text,
        model_name=resp.model,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
    )


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


def call_panacea(prompt: str) -> Completion:
    """Panacea, through Anote's ``anote`` command-line tool.

    Runs ``anote ask --no-edit`` in a fresh empty folder and passes the prompt
    on standard input. Install the tool with ``npm install -g @anote-ai/anote``.
    It runs on Anthropic's Claude Agent SDK, so it needs ANTHROPIC_API_KEY.
    """
    command = shlex.split(os.environ.get("PANACEA_CMD", "anote"))
    if shutil.which(command[0]) is None:
        raise ProviderNotConfigured(
            f"'{command[0]}' not found. Install it with: npm install -g @anote-ai/anote"
        )
    _require_env("ANTHROPIC_API_KEY")  # anote refuses to start without it
    timeout = float(os.environ.get("PANACEA_TIMEOUT", "900"))
    with tempfile.TemporaryDirectory() as workdir:
        proc = subprocess.run(
            command + ["ask", "--no-edit", "--dir", workdir],
            input=prompt,
            capture_output=True,
            text=True,
            cwd=workdir,
            timeout=timeout,
            env={**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0"},
        )
    if proc.returncode != 0:
        raise RuntimeError(f"anote exited with code {proc.returncode}: {proc.stderr.strip()[-500:]}")
    return Completion(text=_clean_cli_output(proc.stdout), model_name="anote-cli")


def _clean_cli_output(text: str) -> str:
    """Remove colour codes, the "── Anote ───" lines and the progress lines."""
    text = ANSI_RE.sub("", text)
    kept = [
        line
        for line in text.splitlines()
        if not RULE_LINE_RE.match(line) and not PROGRESS_LINE_RE.match(line)
    ]
    return "\n".join(kept).strip()


def call_echo(prompt: str) -> Completion:
    """Offline provider for testing the pipeline without API keys."""
    return Completion(text=f"[echo] {prompt[:200]}", model_name="echo")


PROVIDERS: Dict[str, Callable[[str], Completion]] = {
    "claude": call_claude,
    "codex": call_codex,
    "gemini": call_gemini,
    "panacea": call_panacea,
    "echo": call_echo,
}

DEFAULT_MODELS = ["claude", "codex", "gemini", "panacea"]
