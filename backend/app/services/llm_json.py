"""Utilities to safely extract JSON objects from LLM responses."""

import json
import re
from typing import Any

CODE_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def _try_parse_object(payload: str) -> dict[str, Any] | None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _first_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False

        for idx in range(start, len(text)):
            char = text[idx]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:idx + 1]

        start = text.find("{", start + 1)

    return None


def extract_json_object(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None

    text = raw.strip()

    parsed = _try_parse_object(text)
    if parsed is not None:
        return parsed

    for match in CODE_FENCE_PATTERN.finditer(text):
        parsed = _try_parse_object(match.group(1).strip())
        if parsed is not None:
            return parsed

    candidate = _first_balanced_json_object(text)
    if candidate:
        return _try_parse_object(candidate)

    return None


def preview_llm_output(raw: str, max_len: int = 240) -> str:
    if not raw:
        return "<empty>"

    compact = " ".join(raw.strip().split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3] + "..."
