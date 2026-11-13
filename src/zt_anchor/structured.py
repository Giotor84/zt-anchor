"""Structured output from any LLM: pull the JSON out of a chatty answer, validate it, retry with the error.

Works with any ``generate(prompt) -> str`` callable (local llama.cpp, Bedrock, OpenAI-compatible servers).
Validation covers the JSON Schema subset that extraction contracts need: type, properties, required,
additionalProperties=false, enum, items, minimum/maximum, minLength. No dependencies.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_TYPES = {
    "object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool,
    "null": type(None),
}


class StructuredOutputError(ValueError):
    pass


def extract_json(text: str) -> Any:
    """First JSON object or array in ``text``: inside ```json fences or bare, ignoring prose around it."""
    for candidate in [m.group(1) for m in _FENCE.finditer(text)] + [text]:
        for start, ch in enumerate(candidate):
            if ch not in "{[":
                continue
            depth, in_str, esc = 0, False, False
            for end in range(start, len(candidate)):
                c = candidate[end]
                if in_str:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        in_str = False
                    continue
                if c == '"':
                    in_str = True
                elif c in "{[":
                    depth += 1
                elif c in "}]":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(candidate[start:end + 1])
                        except json.JSONDecodeError:
                            break
            # not valid from this start: try the next opening bracket
    raise StructuredOutputError("no JSON object found in the model output")


def _type_ok(value: Any, t: str) -> bool:
    if t in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[t])


def validate(value: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    """List of errors (empty when valid)."""
    errors: list[str] = []
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, x) for x in types):
            return [f"{path}: expected {'/'.join(types)}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > {schema['maximum']}")
    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        errors.append(f"{path}: shorter than {schema['minLength']}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                errors.append(f"{path}: missing required '{k}'")
        if schema.get("additionalProperties") is False:
            errors += [f"{path}: unexpected '{k}'" for k in value if k not in props]
        for k, sub in props.items():
            if k in value:
                errors += validate(value[k], sub, f"{path}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errors += validate(item, schema["items"], f"{path}[{i}]")
    return errors


def generate_structured(
    generate: Callable[[str], str], prompt: str, schema: Mapping[str, Any], attempts: int = 3
) -> Any:
    """Call the model, parse and validate; on failure retry with the errors appended to the prompt."""
    feedback = ""
    last: list[str] = []
    for _ in range(attempts):
        raw = generate(prompt + feedback)
        try:
            value = extract_json(raw)
        except StructuredOutputError as exc:
            last = [str(exc)]
        else:
            last = validate(value, schema)
            if not last:
                return value
        feedback = (
            "\n\nYour previous answer was not valid. Errors:\n- " + "\n- ".join(last)
            + "\nAnswer again with JSON only, matching the schema."
        )
    raise StructuredOutputError(f"invalid after {attempts} attempts: {last}")
