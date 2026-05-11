#!/usr/bin/env python3
"""Test the Storyteller prompt against ONE investigation packet.

Single Pro call. ~$0.50-1.50 per run. No equity_editor, no publish_gate,
no narrator, no image-gen, no autonomous loop. Just the prompt → one
draft → stdout.

Usage:
    python3 scripts/test_storyteller_prompt.py
    python3 scripts/test_storyteller_prompt.py --packet-id pkt-abc123
    python3 scripts/test_storyteller_prompt.py --keyword "Lake Placid"

The default behavior:
- If --packet-id is given: load that exact packet from Firestore.
- Else if --keyword is given: pick the most recent packet whose
  story_unit_id or notes contain the keyword (case-insensitive).
- Else: pick the most recent packet by created_at.

Exit codes:
    0 — draft generated; printed to stdout.
    1 — no packet found.
    2 — Pro Runner failed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

# Ensure repo root is on sys.path so `from agents.prompts import load_prompts` works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.cloud import firestore

PROJECT = "predictive-fx-495200-j4"


def _pick_packet(args: argparse.Namespace) -> dict | None:
    db = firestore.Client(project=PROJECT)
    coll = db.collection("investigation_packets")

    if args.packet_id:
        snap = coll.document(args.packet_id).get()
        if not snap.exists:
            return None
        d = snap.to_dict() or {}
        d["id"] = snap.id
        return d

    docs = list(coll.limit(50).stream())
    if not docs:
        return None
    docs.sort(key=lambda d: d.to_dict().get("created_at", ""), reverse=True)

    if args.keyword:
        kw = args.keyword.lower()
        for d in docs:
            data = d.to_dict() or {}
            haystack = json.dumps(data, default=str).lower()
            if kw in haystack:
                data["id"] = d.id
                return data

    d = docs[0]
    data = d.to_dict() or {}
    data["id"] = d.id
    return data


def _format_user_message(packet: dict) -> str:
    """Mirror StorytellerAgent._format_user_message but with corrected
    word bounds (350-550 per VPS-DEC-053 / Worker SP1 tightening).
    """
    pid = packet.get("id", "unknown")
    return (
        "## Investigation Packet\n"
        f"{json.dumps(packet, ensure_ascii=False, default=str, indent=2)}\n\n"
        "## Your task\n"
        "Write a 350-550 word place narrative per the structural envelope "
        "in your instructions. Call `write_story_draft` exactly once with "
        "the full draft content. The packet id is "
        f"`{pid}`."
    )


def _stub_write_story_draft_tool(captured: list[dict]):
    """A stub `write_story_draft` tool. The model calls this; we capture
    args and return a fake doc-id. NO Firestore write, NO validation.
    """

    async def write_story_draft(
        investigation_packet_id: str,
        slug: str,
        headline: str,
        dek: str,
        body: str,
        why_this_matters: list[str],
        verified_claims: list[dict],
        pull_quote: str | None = None,
        pull_quote_after_paragraph: int | None = None,
    ) -> dict:
        captured.append({
            "investigation_packet_id": investigation_packet_id,
            "slug": slug,
            "headline": headline,
            "dek": dek,
            "body": body,
            "why_this_matters": why_this_matters,
            "verified_claims": verified_claims,
            "pull_quote": pull_quote,
            "pull_quote_after_paragraph": pull_quote_after_paragraph,
        })
        return {"id": "test-draft-stub", "ok": True}

    write_story_draft.__doc__ = (
        "Persist the story draft. Required fields: investigation_packet_id, "
        "slug, headline (8-12 words), dek (1 sentence), body (350-550 words), "
        "why_this_matters (3 short phrases), verified_claims (list of "
        "{slug, text, source}). Optional: pull_quote, pull_quote_after_paragraph."
    )
    return write_story_draft


async def _run(packet: dict) -> tuple[list[dict], dict]:
    # Vertex AI init
    os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

    import vertexai  # type: ignore[import-untyped]
    vertexai.init(project=PROJECT, location="global")

    from google.adk import Runner  # type: ignore[import-untyped]
    from google.adk.agents import LlmAgent  # type: ignore[import-untyped]
    from google.adk.sessions import InMemorySessionService  # type: ignore[import-untyped]
    from google.genai import types as genai_types  # type: ignore[import-untyped]

    from agents.prompts import load_prompts
    prompts = load_prompts(Path(__file__).resolve().parent.parent)
    storyteller_prompt = prompts["storyteller"]

    captured: list[dict] = []
    tool = _stub_write_story_draft_tool(captured)

    agent = LlmAgent(
        name="storyteller",
        model="gemini-3.1-pro-preview",
        instruction=storyteller_prompt,
        tools=[tool],
    )

    runner = Runner(
        app_name="storytellers_room",
        agent=agent,
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    user_msg = _format_user_message(packet)
    session_id = f"storyteller-test-{uuid.uuid4().hex[:8]}"

    in_tokens = 0
    out_tokens = 0
    async for event in runner.run_async(
        user_id="test-storyteller-prompt",
        session_id=session_id,
        new_message=genai_types.Content(
            parts=[genai_types.Part(text=user_msg)],
            role="user",
        ),
    ):
        usage = getattr(event, "usage_metadata", None)
        if usage is not None:
            pt = getattr(usage, "prompt_token_count", None)
            ct = getattr(usage, "candidates_token_count", None)
            if pt is not None:
                in_tokens += int(pt)
            if ct is not None:
                out_tokens += int(ct)

    return captured, {"input_tokens": in_tokens, "output_tokens": out_tokens}


def _print_draft(draft: dict, tokens: dict) -> None:
    print("=" * 72)
    print("DRAFT")
    print("=" * 72)
    print(f"slug: {draft.get('slug', '-')}")
    print(f"headline: {draft.get('headline', '-')}")
    print(f"dek: {draft.get('dek', '-')}")
    body = draft.get("body", "") or ""
    word_count = len(body.split())
    print(f"body word count: {word_count}  (350-550 expected)")
    print()
    print("-" * 72)
    print("BODY")
    print("-" * 72)
    print(body)
    print()
    print("-" * 72)
    print("WHY THIS MATTERS")
    print("-" * 72)
    for w in draft.get("why_this_matters") or []:
        print(f"  • {w}")
    print()
    print("-" * 72)
    print("VERIFIED CLAIMS")
    print("-" * 72)
    for c in draft.get("verified_claims") or []:
        print(f"  • [{c.get('slug', '?')}] {c.get('text', '?')}")
        print(f"    source: {c.get('source', '?')}")
    print()
    pq = draft.get("pull_quote")
    if pq:
        print("-" * 72)
        print("PULL QUOTE")
        print("-" * 72)
        print(pq)
        print(f"  after paragraph: {draft.get('pull_quote_after_paragraph', '-')}")
    print()
    print("=" * 72)
    print("COST DIAGNOSTICS")
    print("=" * 72)
    print(f"input_tokens:  {tokens['input_tokens']}")
    print(f"output_tokens: {tokens['output_tokens']}")
    # Pro pricing (rough): $5 / 1M input, $20 / 1M output
    in_usd = tokens["input_tokens"] / 1_000_000 * 5.0
    out_usd = tokens["output_tokens"] / 1_000_000 * 20.0
    print(f"approx cost:   ${in_usd + out_usd:.3f} (in: ${in_usd:.3f}, out: ${out_usd:.3f})")
    print()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--packet-id", help="exact investigation_packet doc id")
    p.add_argument("--keyword", help="case-insensitive substring match against packet content")
    args = p.parse_args()

    packet = _pick_packet(args)
    if packet is None:
        print("error: no investigation_packet found", file=sys.stderr)
        return 1

    print(f"Using packet id={packet['id']} story_unit_id={packet.get('story_unit_id', '?')}", file=sys.stderr)
    print("(Calling Pro once. ~$0.50-1.50 expected.)", file=sys.stderr)
    print(file=sys.stderr)

    try:
        captured, tokens = asyncio.run(_run(packet))
    except Exception as e:
        print(f"error: Pro Runner failed: {e}", file=sys.stderr)
        return 2

    if not captured:
        print("error: model did not call write_story_draft (no draft captured)", file=sys.stderr)
        print(f"input_tokens: {tokens['input_tokens']}, output_tokens: {tokens['output_tokens']}", file=sys.stderr)
        return 2

    if len(captured) > 1:
        print(f"warning: model called write_story_draft {len(captured)} times; printing first", file=sys.stderr)

    _print_draft(captured[0], tokens)
    return 0


if __name__ == "__main__":
    sys.exit(main())
