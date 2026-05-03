#!/usr/bin/env python3
"""Smoke tests for scripts/lint_no_direct_wire_writes.py.

Runs in pure stdlib (no pytest required) so the worker / CI can invoke it as
`python3 scripts/tests/test_lint_no_direct_wire_writes.py`.

Builds a temporary agents/ tree containing both legitimate and forbidden write
patterns, then asserts the lint:
  - flags the forbidden patterns
  - allows agents/wire/emit.py (the proxy)
  - allows test_*.py files
  - exits 0 when /agents/ doesn't exist
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
LINT_SCRIPT = SCRIPTS_DIR / "lint_no_direct_wire_writes.py"


def _load_lint_module():
    spec = importlib.util.spec_from_file_location("lint_module", LINT_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register before exec_module so __future__ annotations + dataclass field-resolution
    # in the imported module can resolve their __module__'s namespace under py3.9-3.12.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_offending_tree(root: Path) -> None:
    """Create an agents/ tree that should produce exactly N violations."""
    # 1. The proxy itself at agents/wire/emit.py — ALLOWED to call firestore directly.
    _write(
        root / "wire" / "emit.py",
        '''"""The wire.emit proxy. The one legitimate writer."""
def emit(event):
    db.collection("wire_events").add(event)  # this is the only legit write path
''',
    )

    # 2. A scout that does the right thing — should NOT match.
    _write(
        root / "scouts" / "hometown.py",
        '''from agents.wire.emit import emit as wire_emit

async def run():
    wire_emit({"agent": "hometown", "kind": "thinking", "text": "scanning..."})
''',
    )

    # 3. An offender — direct firestore.add('wire_events', ...).
    _write(
        root / "scouts" / "bad_scout.py",
        '''import firestore  # noqa
def emit_directly(event):
    firestore.add('wire_events', event)
''',
    )

    # 4. An offender — .collection('wire_events').add(...).
    _write(
        root / "investigator" / "writer.py",
        '''def write_lead(db, event):
    db.collection("wire_events").add(event)
''',
    )

    # 5. An offender — multiline .collection('wire_events').set(...).
    _write(
        root / "investigator" / "ml_writer.py",
        '''def stash(db, doc_id, event):
    db.collection(
        'wire_events'
    ).document(doc_id).set(event)
''',
    )

    # 6. A test file — ALLOWED even with forbidden pattern.
    _write(
        root / "wire" / "test_emit.py",
        '''def test_seed():
    db.collection("wire_events").add({"x": 1})  # fixture seed; this file is exempt
''',
    )


def main() -> int:
    lint_mod = _load_lint_module()
    failures = 0

    # 1. Empty agents dir doesn't exist -> exit 0 with warning.
    with tempfile.TemporaryDirectory() as td:
        non_existent = Path(td) / "agents"
        rc = lint_mod.lint(non_existent)
        if rc != 0:
            print(f"FAIL: missing-dir case should exit 0, got {rc}")
            failures += 1
        else:
            print("OK: missing-dir case returns 0")

    # 2. Tree with violations -> exit 1.
    with tempfile.TemporaryDirectory() as td:
        agents_dir = Path(td) / "agents"
        make_offending_tree(agents_dir)
        rc = lint_mod.lint(agents_dir)
        if rc != 1:
            print(f"FAIL: violation case should exit 1, got {rc}")
            failures += 1
        else:
            print("OK: violation case returns 1")

        # Inspect the violations directly via scan_file to verify allow-list.
        proxy = agents_dir / "wire" / "emit.py"
        proxy_vs = lint_mod.scan_file(proxy)
        if not proxy_vs:
            print("FAIL: proxy file has no matches (sanity broken)")
            failures += 1
        elif lint_mod._is_proxy_file(proxy, agents_dir):
            print("OK: proxy file recognized via _is_proxy_file (so its matches are skipped)")
        else:
            print("FAIL: _is_proxy_file did not recognize agents/wire/emit.py")
            failures += 1

        test_file = agents_dir / "wire" / "test_emit.py"
        if lint_mod._is_test_file(test_file):
            print("OK: test_emit.py recognized as test file (skipped)")
        else:
            print("FAIL: test_emit.py not recognized as test file")
            failures += 1

        # Hometown scout must NOT have any violations.
        good = agents_dir / "scouts" / "hometown.py"
        if lint_mod.scan_file(good):
            print("FAIL: clean scout file flagged")
            failures += 1
        else:
            print("OK: clean scout file not flagged")

        # bad_scout, investigator/writer, investigator/ml_writer SHOULD all be flagged.
        for relpath, label in [
            (Path("scouts") / "bad_scout.py", "firestore.add"),
            (Path("investigator") / "writer.py", "single-line collection.add"),
            (Path("investigator") / "ml_writer.py", "multi-line collection.document.set"),
        ]:
            v = lint_mod.scan_file(agents_dir / relpath)
            if not v:
                print(f"FAIL: missed violation in {relpath} ({label})")
                failures += 1
            else:
                print(f"OK: flagged {relpath} ({label}, {len(v)} match)")

    # 3. Tree with only legitimate code -> exit 0.
    with tempfile.TemporaryDirectory() as td:
        agents_dir = Path(td) / "agents"
        _write(
            agents_dir / "scouts" / "good.py",
            '''from agents.wire.emit import emit as wire_emit
async def run():
    wire_emit({"x": 1})
''',
        )
        rc = lint_mod.lint(agents_dir)
        if rc != 0:
            print(f"FAIL: clean tree should exit 0, got {rc}")
            failures += 1
        else:
            print("OK: clean tree returns 0")

    print()
    if failures:
        print(f"FAIL: {failures} test failure(s).")
        return 1
    print("OK: all lint matcher tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
