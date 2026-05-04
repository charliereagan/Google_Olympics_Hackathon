"""Per-investigation `compression_factor` cadence.

BUILD_SPEC §6.10 + HOE-DEC-021. The pacer is constructed per investigation
and threaded through to every agent that emits Wire events. At
`compression_factor=1.0` the room runs at ambient speed (a new event every
4-8s). At `compression_factor=0.25` (the live URL hero CTA), the same logical
delays divide by 4, producing the 4× cadence — but timestamps still reflect
real wall-clock emission time per CONSTITUTION Rule 3.

Pure stdlib (asyncio + random). No Firestore / network. Trivially testable
with patched `asyncio.sleep`.
"""

from __future__ import annotations

import asyncio
import random

# Hard clamp: compression must be in (0, 1.0]. We refuse 0.0 (would divide by
# zero) and refuse > 1.0 (the room is meditative; no one should be running it
# faster than ambient). HOE-DEC-021 explicitly bounds compression.
_MIN_COMPRESSION = 0.05
_MAX_COMPRESSION = 1.0


class WirePacer:
    """Convert nominal "think time" into wall-clock asyncio sleeps.

    Args:
        compression_factor: 1.0 = ambient; 0.25 = 4× faster.
        jitter: optional 0..1 fraction added to each delay's random nudge.
    """

    def __init__(
        self,
        compression_factor: float = 1.0,
        *,
        jitter: float = 0.0,
    ) -> None:
        self._validate(compression_factor)
        if jitter < 0.0 or jitter > 1.0:
            raise ValueError(f"jitter must be in [0, 1.0]; got {jitter!r}")
        self._compression_factor = float(compression_factor)
        self._jitter = float(jitter)

    @staticmethod
    def _validate(cf: float) -> None:
        if cf < _MIN_COMPRESSION or cf > _MAX_COMPRESSION:
            raise ValueError(
                f"compression_factor must be in [{_MIN_COMPRESSION}, "
                f"{_MAX_COMPRESSION}]; got {cf!r}"
            )

    @property
    def compression_factor(self) -> float:
        return self._compression_factor

    async def delay(self, target_seconds: float) -> None:
        """Sleep `target_seconds * compression_factor` seconds.

        At `compression_factor=0.25` a 2.0s nominal pause becomes 0.5s wall
        clock — the 4× live-URL cadence (HOE-DEC-021).

        Note on formula: BUILD_SPEC §6.10 / plan §A.3 prose say "target /
        compression_factor" but their worked example ("a 6s think pause
        becomes 1.5s at compression 0.25") only solves under
        `target * compression_factor` (6 × 0.25 = 1.5). The intent is
        unambiguous (0.25 = 4× faster), so the multiplicative form is what
        ships. Flagged in the Day-2 status report for HoE clarification.
        """
        if target_seconds < 0:
            raise ValueError(f"target_seconds must be >= 0; got {target_seconds!r}")
        effective = target_seconds * self._compression_factor
        await asyncio.sleep(effective)

    async def jittered_delay(self, base_min: float, base_max: float) -> None:
        """Sleep a random duration in `[base_min*cf, base_max*cf]`.

        Used by the Editor's 30-90s think-cycle (BUILD_SPEC §5.1) and any
        Scout that wants natural-feeling pauses.
        """
        if base_min < 0 or base_max < base_min:
            raise ValueError(
                f"base_min={base_min!r}, base_max={base_max!r} invalid "
                "(must be 0 <= min <= max)"
            )
        nominal = random.uniform(base_min, base_max)
        await self.delay(nominal)
