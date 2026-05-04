"""Prompt loader. Walks /prompts/*.md once at runtime boot.

Returns a `dict[str, str]` keyed by file stem (e.g., 'editor', 'cinderella_scout').
Voice signatures live in those markdown files — never in Python — per
CONSTITUTION Rule 1.

File-watcher hot-reload (BUILD_SPEC §18.1) is Day-3 work; the backlog entry
is in `Docs/Engineering/backlog.md`.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_prompts(repo_root: Path) -> dict[str, str]:
    """Read all `.md` files under `repo_root/prompts/` into a dict.

    Args:
        repo_root: the directory containing the `prompts/` subdir.

    Returns:
        `{file_stem: file_contents}` — e.g., `{'editor': '...', 'cinderella_scout': '...'}`.

    Raises:
        FileNotFoundError: if `repo_root/prompts/` does not exist.
        ValueError: if no `.md` files found (catches misconfig early).
    """
    prompts_dir = repo_root / "prompts"
    if not prompts_dir.exists():
        raise FileNotFoundError(f"prompts directory not found: {prompts_dir}")
    out: dict[str, str] = {}
    for md_path in sorted(prompts_dir.glob("*.md")):
        out[md_path.stem] = md_path.read_text(encoding="utf-8")
    if not out:
        raise ValueError(f"no .md files found in {prompts_dir}")
    logger.info("prompts: loaded %d prompt(s) from %s", len(out), prompts_dir)
    return out


def repo_root_from(this_file: Path) -> Path:
    """Convenience: walk up from a file to the repo root.

    The runtime calls `load_prompts(repo_root_from(__file__))` from
    `agents/runtime.py`, so this expects the file to live at
    `<repo_root>/agents/<...>.py`.
    """
    return this_file.resolve().parent.parent
