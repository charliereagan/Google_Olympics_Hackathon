#!/usr/bin/env python3
"""CI lint: forbid direct firestore writes to wire_events from /agents/.

Every Wire emit must route through wire.emit(event) so the in-process write-through
proxy invokes the NIL Redaction Layer. Any direct firestore.add('wire_events', ...)
or .collection('wire_events').add(/.set(/.update( bypasses the layer and is a DQ risk.

Allowed write paths:
  - /agents/wire/emit.py              (the proxy itself)
  - test files matching test_*.py     (fixtures may seed wire_events)

Exits 1 on any violation. (HOE-DEC-018, BUILD_SPEC §6, §23.)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AGENTS_DIR = REPO_ROOT / "agents"

# Forbidden patterns. Each is matched with re.DOTALL because the .add(/.set(/.update(
# call may sit on a continuation line after .collection('wire_events').
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "firestore.add('wire_events', ...)",
        re.compile(
            r"firestore\s*\.\s*add\s*\(\s*['\"]wire_events['\"]",
            re.DOTALL,
        ),
        "Direct firestore.add('wire_events', ...) call. Use wire.emit(event) instead.",
    ),
    (
        ".collection('wire_events').add/.set/.update(",
        re.compile(
            r"\.collection\s*\(\s*['\"]wire_events['\"]\s*\)\s*\.\s*(?:add|set|update)\s*\(",
            re.DOTALL,
        ),
        ".collection('wire_events').<add|set|update>(...) bypasses wire.emit. Use wire.emit(event).",
    ),
    (
        ".collection('wire_events').document(...).set/.update/.create(",
        re.compile(
            r"\.collection\s*\(\s*['\"]wire_events['\"]\s*\)\s*\.\s*document\s*\([^)]*\)\s*\.\s*(?:set|update|create)\s*\(",
            re.DOTALL,
        ),
        "Direct document write into wire_events bypasses wire.emit. Use wire.emit(event).",
    ),
    (
        "AsyncClient/.collection('wire_events') write",
        re.compile(
            r"firestore_v1[\w.]*\s*\.[\w.]*\s*\.\s*collection\s*\(\s*['\"]wire_events['\"]\s*\)\s*\.\s*(?:add|set|update)\s*\(",
            re.DOTALL,
        ),
        "firestore_v1 client direct write to wire_events bypasses wire.emit.",
    ),
]


@dataclass
class Violation:
    file: Path
    line: int
    pattern_label: str
    message: str
    snippet: str


def _is_test_file(path: Path) -> bool:
    return path.name.startswith("test_") and path.suffix == ".py"


def _is_proxy_file(path: Path, agents_dir: Path) -> bool:
    """The proxy itself at agents/wire/emit.py is the one place real writes happen."""
    try:
        rel = path.relative_to(agents_dir)
    except ValueError:
        return False
    return rel.parts == ("wire", "emit.py")


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _snippet_of(text: str, offset: int, length: int = 80) -> str:
    start = max(0, offset - 10)
    end = min(len(text), offset + length)
    return text[start:end].replace("\n", " ").strip()


def scan_file(path: Path) -> list[Violation]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    out: list[Violation] = []
    for label, pattern, msg in PATTERNS:
        for m in pattern.finditer(text):
            out.append(
                Violation(
                    file=path,
                    line=_line_of(text, m.start()),
                    pattern_label=label,
                    message=msg,
                    snippet=_snippet_of(text, m.start()),
                )
            )
    return out


def walk_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip common noise dirs.
        dirnames[:] = [
            d for d in dirnames
            if d not in {"__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
        ]
        for fn in filenames:
            if fn.endswith(".py"):
                files.append(Path(dirpath) / fn)
    return files


def lint(agents_dir: Path) -> int:
    if not agents_dir.exists():
        print(
            f"WARNING: {agents_dir} does not exist yet — skipping wire-write lint. "
            "(Will activate once /agents/ is created.)",
            file=sys.stderr,
        )
        return 0

    files = walk_python_files(agents_dir)
    if not files:
        print(f"WARNING: no .py files under {agents_dir} — nothing to lint.")
        return 0

    violations: list[Violation] = []
    scanned = 0
    skipped: list[Path] = []
    for f in files:
        if _is_proxy_file(f, agents_dir) or _is_test_file(f):
            skipped.append(f)
            continue
        scanned += 1
        violations.extend(scan_file(f))

    if violations:
        print(
            f"FAIL: {len(violations)} direct wire_events write(s) found in {scanned} file(s) "
            f"under {agents_dir}.",
            file=sys.stderr,
        )
        for v in violations:
            print(
                f"  {v.file}:{v.line}  [{v.pattern_label}]\n"
                f"    {v.message}\n"
                f"    > {v.snippet}",
                file=sys.stderr,
            )
        print(
            "\nFix: route the write through agents/wire/emit.py::wire.emit(event). "
            "The proxy invokes the NIL Redaction Layer; bypassing it is a DQ risk. "
            "(HOE-DEC-018, BUILD_SPEC §6.)",
            file=sys.stderr,
        )
        return 1

    print(f"OK lint_no_direct_wire_writes: {scanned} file(s) scanned, 0 violations. (skipped {len(skipped)} test/proxy file(s).)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        default=str(DEFAULT_AGENTS_DIR),
        help=f"Path to scan (default: {DEFAULT_AGENTS_DIR})",
    )
    args = parser.parse_args(argv)
    return lint(Path(args.path).resolve())


if __name__ == "__main__":
    sys.exit(main())
