"""Wire vocabulary library — loader + sampler.

Reads `data/wire_vocabulary.json` (BUILD_SPEC §6.4) into memory once at
runtime boot. Agents draw a random fragment via `sample(agent, message_type)`
and fill `{placeholder}` slots via `fill(fragment, **slots)`.

This module is pure stdlib — no third-party deps, no Vertex AI. Day-3+
a separate Flash-Lite utility will fill placeholders given context; for
now `fill()` is naive `str.format`-style substitution that leaves
unknown slots in place rather than raising KeyError.

Loaded once at runtime boot in `agents/runtime.py` step 5b (after
streaming_profiles, before NIL bootstrap) and stored on
`RuntimeState.wire_vocabulary`. The Editor and Scouts will start
calling `runtime_state.wire_vocabulary.sample(...)` from Day-4 onward.
"""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PATH = REPO_ROOT / "data" / "wire_vocabulary.json"

# Match `{snake_case_or_int}` and `[snake_case_or_int]` placeholders.
# Underscores + ASCII letters + digits only inside the brackets; spaces or
# punctuation don't count (those would be format spec or escapes).
#
# HOE-DEC-032 settled the canonical placeholder convention as `[snake_case]`,
# but the seed JSON shipped with `{snake_case}` slots and is treated as data
# (do not edit it as code). To keep both the JSON's existing slots and the
# canonical bracket style working, fill() substitutes against either bracket
# style — `{place}` and `[place]` both match.
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}|\[([A-Za-z_][A-Za-z0-9_]*)\]")


class WireVocabulary:
    """Immutable in-memory vocabulary library.

    Attributes:
        path:  source JSON path, kept for diagnostics.
        data:  {agent: {message_type: [fragment, ...]}}.

    The `_comments` top-level key is stripped on load (it documents the
    placeholder convention; see the JSON file itself for the schema).
    """

    def __init__(self, data: dict[str, dict[str, list[str]]], path: Path | None = None) -> None:
        self.data = data
        self.path = path

    # ----- Construction ------------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> "WireVocabulary":
        """Load `data/wire_vocabulary.json` (or a custom path) into memory.

        On parse failure, logs and returns an empty vocabulary so the runtime
        can still boot — `sample()` returns None, and consumers fall back to
        sensible defaults. This is intentional: vocabulary draws are texture,
        not gating.
        """
        target = Path(path) if path is not None else DEFAULT_PATH
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning("wire_vocabulary.json missing at %s", target)
            return cls({}, path=target)
        except json.JSONDecodeError:
            logger.exception("wire_vocabulary.json parse failed at %s", target)
            return cls({}, path=target)

        # Strip top-level `_comments` keys; only agent buckets are content.
        cleaned: dict[str, dict[str, list[str]]] = {}
        for agent, types in raw.items():
            if agent.startswith("_"):
                continue
            if not isinstance(types, dict):
                logger.warning("wire_vocabulary: skipping non-dict bucket %r", agent)
                continue
            cleaned[agent] = {
                mt: list(frags) for mt, frags in types.items() if isinstance(frags, list)
            }
        return cls(cleaned, path=target)

    # ----- Drawing -----------------------------------------------------------

    def sample(self, agent: str, message_type: str = "thinking") -> str | None:
        """Return a random fragment for `agent` + `message_type`, or None.

        Returns None if the agent or message type is missing, or the bucket
        is empty. Callers should treat None as "skip the wire-vocabulary
        path and use the agent's own LLM-generated message."
        """
        bucket = self.data.get(agent, {}).get(message_type)
        if not bucket:
            return None
        return random.choice(bucket)

    def fill(self, fragment: str, **slots: object) -> str:
        """Fill `{placeholder}` and `[placeholder]` slots. Missing slots stay as-is.

        Both bracket styles are supported (HOE-DEC-032): `[snake_case]` is the
        canonical style going forward, while `{snake_case}` is preserved for
        backward-compatibility with the seed JSON.

        Example::

            v.fill("Going with {place}.", place="Mount Pleasant")
            # -> "Going with Mount Pleasant."

            v.fill("Going with [place].", place="Mount Pleasant")
            # -> "Going with Mount Pleasant."

            v.fill("{a} {b}", a="x")
            # -> "x {b}"   (unknown {b} preserved, not raised)

            v.fill("[a] {b}", a="x", b="y")
            # -> "x y"     (mixed bracket styles both work)
        """

        def _sub(match: re.Match[str]) -> str:
            # group(1) = curly-brace key (or None); group(2) = square-bracket key (or None).
            key = match.group(1) if match.group(1) is not None else match.group(2)
            if key in slots:
                return str(slots[key])
            return match.group(0)  # leave the literal `{key}` or `[key]` in place

        return _PLACEHOLDER_RE.sub(_sub, fragment)

    # ----- Introspection -----------------------------------------------------

    def agents(self) -> list[str]:
        return sorted(self.data.keys())

    def message_types(self, agent: str) -> list[str]:
        return sorted(self.data.get(agent, {}).keys())

    def all_fragments(self) -> Iterable[tuple[str, str, str]]:
        """Yield every (agent, message_type, fragment) triple. Used by tests."""
        for agent, types in self.data.items():
            for mt, frags in types.items():
                for frag in frags:
                    yield (agent, mt, frag)

    def total_fragments(self, agent: str) -> int:
        return sum(len(frags) for frags in self.data.get(agent, {}).values())
