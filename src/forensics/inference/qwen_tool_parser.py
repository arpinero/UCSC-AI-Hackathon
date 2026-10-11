"""Parser for the SOC fine-tune's tool-call blocks.

The `alirezaaminzadeh/soc-analyst-tool-use` fine-tune emits tool calls as
``<<{...}>>`` blocks (and, as a fallback convention, Qwen2.5-style
``[[{...}]]`` lists). This module converts those into typed
``ToolCallRequest`` contract objects — model-specific syntax must never leak
into investigation logic.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from contracts.inference import ToolCallRequest

#: ``<< { "name": ..., "arguments": {...} } >>`` blocks (primary convention).
#: Matching the full block between ``<<`` and ``>>`` (not brace-balanced) keeps
#: string-encoded arguments containing ``}`` parsable.
_TOOL_BLOCK_RE = re.compile(r"<<\s*(.*?)\s*>>", re.DOTALL)

#: ``[[{...}]]`` Qwen2.5 list convention (fallback).
_LIST_BLOCK_RE = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)


def _coerce_call(candidate: Any) -> ToolCallRequest | None:
    """Best-effort conversion of one parsed JSON value into a ToolCallRequest."""

    if not isinstance(candidate, dict):
        return None
    name = candidate.get("name") or candidate.get("tool_name")
    if not isinstance(name, str) or not name.strip():
        return None
    arguments = candidate.get("arguments", candidate.get("parameters"))
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    call_id = candidate.get("call_id") or candidate.get("id")
    try:
        return ToolCallRequest(
            tool_name=name.strip(),
            arguments=arguments,
            call_id=call_id if isinstance(call_id, str) else None,
        )
    except ValidationError:
        return None


def parse_qwen_tool_calls(text: str) -> list[ToolCallRequest]:
    """Extract all tool-call blocks from raw model output.

    Handles, in order:
      1. ``<<{...}>>`` blocks (the fine-tune's primary convention),
      2. ``[[{...}]]`` list blocks (Qwen2.5 convention),
      3. a bare JSON list/object as a last resort.
    Unparsable blocks are skipped, never fatal. Returns ``[]`` when no tool
    call is recognized (i.e. the model answered in prose).
    """

    calls: list[ToolCallRequest] = []

    for match in _TOOL_BLOCK_RE.finditer(text):
        try:
            candidate: Any = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        call = _coerce_call(candidate)
        if call is not None:
            calls.append(call)

    if calls:
        return _dedupe(calls)

    for match in _LIST_BLOCK_RE.finditer(text):
        raw = match.group(1).strip().removeprefix("json").strip()
        try:
            candidate = json.loads(raw)
        except json.JSONDecodeError:
            # Qwen's `[[...]]` convention lists calls comma-separated WITHOUT
            # inner brackets: `[[{...}, {...}]]` — wrap and retry.
            try:
                candidate = json.loads(f"[{raw}]")
            except json.JSONDecodeError:
                continue
        if isinstance(candidate, dict):
            call = _coerce_call(candidate)
            if call is not None:
                calls.append(call)
        elif isinstance(candidate, list):
            for item in candidate:
                call = _coerce_call(item)
                if call is not None:
                    calls.append(call)

    if calls:
        return _dedupe(calls)

    # Last resort: bare JSON array of calls, possibly inside code fences.
    stripped = text.strip().removeprefix("```json").removesuffix("```").strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            candidate = json.loads(stripped)
        except json.JSONDecodeError:
            return []
        if isinstance(candidate, list):
            for item in candidate:
                call = _coerce_call(item)
                if call is not None:
                    calls.append(call)
    return _dedupe(calls)


def _dedupe(calls: list[ToolCallRequest]) -> list[ToolCallRequest]:
    """Drop exact duplicates while preserving order (small models repeat)."""
    seen: set[tuple[str, str]] = set()
    unique: list[ToolCallRequest] = []
    for call in calls:
        key = (call.tool_name, json.dumps(call.arguments, sort_keys=True))
        if key not in seen:
            seen.add(key)
            unique.append(call)
    return unique


def strip_tool_blocks(text: str) -> str:
    """Remove tool-call blocks, leaving only the prose content."""

    text = _TOOL_BLOCK_RE.sub("", text)
    text = _LIST_BLOCK_RE.sub("", text)
    return text.strip()
