"""Prompt loader. Walks /prompts/*.md once at runtime boot.

Returns a `dict[str, str]` keyed by file stem (e.g., 'editor', 'cinderella_scout').
Voice signatures live in those markdown files — never in Python — per
CONSTITUTION Rule 1.

**Placeholder sanitization (HOE-DEC-032):** ADK 2.0 Beta's `LlmAgent.instruction`
treats `{name}` patterns as session-state context variables and raises
`KeyError: 'Context variable not found'` at Runner invocation time when those
slots aren't pre-populated. Our prompt files contain `{place}`, `{region}`, etc.
as voice-fragment EXAMPLES (the LLM imitates the pattern; nothing literal is
substituted). To keep the prompts readable for humans AND survive ADK's
template engine, we transform `{snake_case}` → `[snake_case]` at load time.
The transform is idempotent — already-bracketed slots are untouched.

File-watcher hot-reload (BUILD_SPEC §18.1) is deferred; backlog has the entry.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


# Match `{snake_case_identifier}` or `{kebab-case-identifier}`; lowercase only
# (uppercase or mixed = probably a different intent we don't want to touch).
# Allows underscores AND hyphens inside the identifier (e.g., `{sport-era}`).
_PLACEHOLDER_PATTERN = re.compile(r"\{([a-z][a-z0-9_-]*)\}")


def _sanitize_for_adk(text: str) -> str:
    """Replace `{slot}` with `[slot]` so ADK's instruction template engine
    doesn't try to resolve them as session-state variables.

    Idempotent — `[slot]` patterns are not matched by the regex.
    """
    return _PLACEHOLDER_PATTERN.sub(r"[\1]", text)


def load_prompts(repo_root: Path) -> dict[str, str]:
    """Read all `.md` files under `repo_root/prompts/` into a dict.

    Args:
        repo_root: the directory containing the `prompts/` subdir.

    Returns:
        `{file_stem: sanitized_file_contents}` — e.g., `{'editor': '...',
        'cinderella_scout': '...'}`. Each value has `{slot}` placeholders
        rewritten to `[slot]` per HOE-DEC-032.

    Raises:
        FileNotFoundError: if `repo_root/prompts/` does not exist.
        ValueError: if no `.md` files found (catches misconfig early).
    """
    prompts_dir = repo_root / "prompts"
    if not prompts_dir.exists():
        raise FileNotFoundError(f"prompts directory not found: {prompts_dir}")
    out: dict[str, str] = {}
    for md_path in sorted(prompts_dir.glob("*.md")):
        raw = md_path.read_text(encoding="utf-8")
        out[md_path.stem] = _sanitize_for_adk(raw)
    if not out:
        raise ValueError(f"no .md files found in {prompts_dir}")
    logger.info("prompts: loaded %d prompt(s) from %s (ADK-sanitized)", len(out), prompts_dir)
    return out


def repo_root_from(this_file: Path) -> Path:
    """Convenience: walk up from a file to the repo root.

    The runtime calls `load_prompts(repo_root_from(__file__))` from
    `agents/runtime.py`, so this expects the file to live at
    `<repo_root>/agents/<...>.py`.
    """
    return this_file.resolve().parent.parent
