"""OpenAI-compatible LLM client for batch French-definition generation.

Sends batches of entries (each with its full gloss list), validates the
JSON-array response, and maps each object back onto its entry via the
echoed `id`. Gloss parity is enforced on the response itself: every input
sense must be covered exactly once — a dropped or invented sense fails the
batch loudly (spec §14). The batch is retried up to `max_retries`, then a
GenerationError names the failure. Standard library only (`urllib`).
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .config import LLMConfig
from .prompt import GenerationItem, render_prompt


class GenerationError(Exception):
    """Raised when a batch cannot be generated or validated."""


@dataclass(frozen=True)
class Sense:
    """One validated French definition for one gloss."""

    gloss: str
    french_definition: str


@dataclass(frozen=True)
class GenerationResult:
    """One validated entry: identity plus its full sense list."""

    key: str  # lexical identity "traditional|simplified|pinyin"
    traditional: str
    simplified: str
    pinyin: str
    senses: tuple[Sense, ...]
    confidence: str  # "confident" | "review"


def post_chat_completions(
    endpoint: str, model: str, system: str, user: str, timeout_s: float
) -> Any:
    """POST one chat-completions request; return the decoded JSON body."""
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8")
    except OSError as exc:
        raise GenerationError(f"LLM request failed: {exc}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise GenerationError(f"LLM response is not valid JSON: {exc}") from exc


def _extract_content(response: Any) -> str:
    """Pull the assistant message text out of a chat-completions body."""
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GenerationError(
            f"LLM response has no choices[0].message.content: {response!r}"
        ) from exc


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences LLMs add despite 'No markdown' instruction.

    Handles ```json ... ```, ``` ... ```, with leading/trailing whitespace.
    Returns the inner payload unchanged when no fences are present.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    # Drop opening fence (``` or ```json + possible trailing text).
    lines = lines[1:]
    # Drop closing fence: last line starting with ``` (or trailing ```).
    while lines and lines[-1].strip() == "":
        lines.pop()
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    else:
        # Closing fence glued to content on the same line.
        joined = "\n".join(lines)
        if "```" in joined:
            joined = joined.rsplit("```", 1)[0]
        return joined.strip()
    return "\n".join(lines).strip()


def _parse_content(content: str) -> Any:
    """Parse assistant message text as JSON, tolerating code fences."""
    try:
        return json.loads(_strip_code_fences(content))
    except json.JSONDecodeError as exc:
        raise GenerationError(
            f"LLM message content is not a JSON array: {content[:200]!r}"
        ) from exc


def _validate_senses(item: GenerationItem, obj: Any, entry_id: int) -> tuple[Sense, ...]:
    """Validate one entry's senses array against its input glosses."""
    senses = obj.get("senses") if isinstance(obj, dict) else None
    if not isinstance(senses, list) or not senses:
        raise GenerationError(f"LLM response id {entry_id}: 'senses' must be a non-empty array")
    seen: dict[str, str] = {}
    for sense in senses:
        if not isinstance(sense, dict):
            raise GenerationError(
                f"LLM response id {entry_id}: sense must be an object, got {sense!r}"
            )
        gloss = sense.get("gloss")
        french = sense.get("fr")
        if not isinstance(gloss, str) or not gloss.strip():
            raise GenerationError(
                f"LLM response id {entry_id}: sense has empty 'gloss'"
            )
        if not isinstance(french, str) or not french.strip():
            raise GenerationError(
                f"LLM response id {entry_id}: sense {gloss!r} has empty 'fr'"
            )
        if gloss in seen:
            raise GenerationError(
                f"LLM response id {entry_id}: duplicate sense for {gloss!r}"
            )
        seen[gloss] = french.strip()
    expected = set(item.glosses)
    missing = expected - set(seen)
    extra = set(seen) - expected
    if missing or extra:
        details = []
        if missing:
            details.append(f"dropped sense(s): {sorted(missing)}")
        if extra:
            details.append(f"invented sense(s): {sorted(extra)}")
        raise GenerationError(
            f"LLM response id {entry_id} ({item.simplified}): gloss parity failure — "
            + "; ".join(details)
        )
    return tuple(Sense(gloss=gloss, french_definition=seen[gloss]) for gloss in item.glosses)


def _validate_batch_response(
    items: list[GenerationItem], raw: Any
) -> list[GenerationResult]:
    """Validate one batch response; return results aligned with `items`."""
    if not isinstance(raw, list):
        raise GenerationError(
            "LLM response must be a JSON array, "
            f"got {type(raw).__name__}: {str(raw)[:200]!r}"
        )
    by_id: dict[Any, Any] = {}
    for obj in raw:
        if not isinstance(obj, dict) or "id" not in obj:
            raise GenerationError(f"LLM response object has no 'id': {obj!r}")
        if obj["id"] in by_id:
            raise GenerationError(f"LLM response repeats id {obj['id']!r}")
        by_id[obj["id"]] = obj
    extra = set(by_id) - set(range(len(items)))
    if extra:
        raise GenerationError(f"LLM response has unknown ids: {sorted(extra)}")

    results: list[GenerationResult] = []
    for i, item in enumerate(items):
        if i not in by_id:
            raise GenerationError(
                f"LLM response is missing id {i} ({item.simplified})"
            )
        obj = by_id[i]
        word = obj.get("word")
        if word != item.simplified:
            raise GenerationError(
                f"LLM response id {i}: word {word!r} does not match "
                f"requested {item.simplified!r} — mapping unsafe"
            )
        senses = _validate_senses(item, obj, i)
        confidence = obj.get("confidence")
        if confidence not in ("confident", "review"):
            # Conservative default (output spec): when in doubt, review.
            confidence = "review"
        results.append(
            GenerationResult(
                key=item.key,
                traditional=item.traditional,
                simplified=item.simplified,
                pinyin=item.pinyin,
                senses=senses,
                confidence=confidence,
            )
        )
    return results


def generate_batch(
    items: list[GenerationItem],
    config: LLMConfig,
    post: Callable[..., Any] = post_chat_completions,
) -> list[GenerationResult]:
    """Generate French definitions for one batch of entries, with retries.

    `post` is injectable so tests run without a network. Raises
    GenerationError after `max_retries` failed attempts.
    """
    if not items:
        raise GenerationError("cannot generate an empty batch")
    for item in items:
        if not item.glosses:
            raise GenerationError(f"entry {item.key}: no glosses to generate")
    system, user = render_prompt(items)
    last_error: GenerationError | None = None
    for _ in range(config.max_retries + 1):
        try:
            response = post(
                config.endpoint, config.model, system, user, config.timeout_s
            )
            content = _extract_content(response)
            raw = _parse_content(content)
            return _validate_batch_response(items, raw)
        except GenerationError as exc:
            last_error = exc
    raise GenerationError(
        f"batch failed after {config.max_retries + 1} attempt(s): {last_error}"
    )
