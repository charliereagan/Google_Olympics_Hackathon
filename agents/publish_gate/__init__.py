"""Publish Gate package.

Day-7 ships:

* The full NIL Redaction Layer (`nil_redaction_layer.py`) — a drop-in
  replacement for the Day-2 stub, with disambiguation, near-id
  Flash-Lite check, small-aggregate detection, and return-to-Storyteller
  decision. The Day-2 stub stays importable as `NilRedactionLayerStub`.
* The Visualizer tool (`visualizer.py`) — Nano Banana Pro / Gemini
  Flash Image generation called by the Publish Gate orchestrator
  between sub-stage 6 (Language Review) and sub-stage 7 (Visual
  Review). Per CONSTITUTION Rule 2 + HOE-DEC-020 it's a tool, not an
  agent.
* The full Visual Review sub-stage (`visual_review.py`) — replaces
  the Day-6 30-LOC auto-pass stub with the photorealism / likeness /
  protected-mark check per CONSTITUTION Law 6 + §8 Kill List.
"""

from __future__ import annotations

from agents.publish_gate.fact_check import FactCheckSubstage
from agents.publish_gate.language_review import LanguageReviewSubstage
from agents.publish_gate.nil_redaction_layer import (
    NilRedactionLayer,
    RegistryTooSmallError,
)
# Day-2 stub kept available for reference / fallback.
from agents.publish_gate.nil_redaction_layer_stub import (
    NilRedactionLayer as NilRedactionLayerStub,
)
from agents.publish_gate.orchestrator import PublishGateAgent
from agents.publish_gate.parity_review import ParityReviewSubstage
from agents.publish_gate.safety_review import SafetyReviewSubstage
from agents.publish_gate.source_review import SourceReviewSubstage
from agents.publish_gate.visual_review import VisualReviewSubstage
from agents.publish_gate.visualizer import (
    GeminiImageGenError,
    Visualizer,
    VisualizerSafetyError,
)

__all__ = [
    "PublishGateAgent",
    "FactCheckSubstage",
    "SourceReviewSubstage",
    "ParityReviewSubstage",
    "SafetyReviewSubstage",
    "LanguageReviewSubstage",
    "VisualReviewSubstage",
    "Visualizer",
    "GeminiImageGenError",
    "VisualizerSafetyError",
    "NilRedactionLayer",
    "NilRedactionLayerStub",
    "RegistryTooSmallError",
]
