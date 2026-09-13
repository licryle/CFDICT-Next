"""Scope computation for dictionary generation (spec §3, §10, §12).

Missing generation scope:  CC-CEDICT − CFDICT − CFDICT-LLM
Confident dictionary:      CFDICT + confident.json
Full dictionary:           CFDICT + confident.json + review.json

CC-CEDICT and CFDICT arrive as parsed lists of DictionaryEntry; the LLM
datasets arrive as mappings of lexical identity -> record (see
cfdict_next.parser.json.load_llm_json). All four sources meet at the same
lexical identity (spec §15), which is what makes the set arithmetic valid.
"""

from __future__ import annotations


def compute_missing_scope(
    cc_cedict_ids: set[str],
    cfdict_ids: set[str],
    confident_ids: set[str],
    review_ids: set[str],
) -> set[str]:
    """Return the identities still needing LLM generation.

    CC-CEDICT minus everything already covered by the authoritative
    dictionary or by existing LLM output (spec §3, §5).
    """
    return set(cc_cedict_ids) - set(cfdict_ids) - set(confident_ids) - set(review_ids)


def compute_confident_scope(
    cfdict_ids: set[str],
    confident_ids: set[str],
) -> set[str]:
    """Return the identities included in the confident dictionary (spec §10.1)."""
    return set(cfdict_ids) | set(confident_ids)


def compute_full_scope(
    cfdict_ids: set[str],
    confident_ids: set[str],
    review_ids: set[str],
) -> set[str]:
    """Return the identities included in the full dictionary (spec §10.2)."""
    return set(cfdict_ids) | set(confident_ids) | set(review_ids)


def compute_scope_statistics(
    cc_cedict_ids: set[str],
    cfdict_ids: set[str],
    confident_ids: set[str],
    review_ids: set[str],
) -> dict[str, int]:
    """Return coverage counts for the release scope information (spec §12)."""
    missing = compute_missing_scope(cc_cedict_ids, cfdict_ids, confident_ids, review_ids)
    confident_scope = compute_confident_scope(cfdict_ids, confident_ids)
    full_scope = compute_full_scope(cfdict_ids, confident_ids, review_ids)
    in_cc = set(cc_cedict_ids)
    return {
        "cc_cedict_total": len(cc_cedict_ids),
        "cfdict_total": len(cfdict_ids),
        "llm_confident_total": len(confident_ids),
        "llm_review_total": len(review_ids),
        "missing_scope_total": len(missing),
        "confident_dictionary_total": len(confident_scope),
        "full_dictionary_total": len(full_scope),
        "cfdict_covers_cc_cedict": len(set(cfdict_ids) & in_cc),
        "confident_covers_cc_cedict": len(set(confident_ids) & in_cc),
        "review_covers_cc_cedict": len(set(review_ids) & in_cc),
    }
