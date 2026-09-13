"""Unit tests for scope computation (src/scope.py, spec §3, §10, §12)."""

from cfdict_next.identity import compute_lexical_identity
from cfdict_next.scope import (
    compute_confident_scope,
    compute_full_scope,
    compute_missing_scope,
    compute_scope_statistics,
)


def _id(trad, simp, pin):
    return compute_lexical_identity(trad, simp, pin)


# Fixture scenario:
#   CC-CEDICT: A, B, C, D
#   CFDICT:    A          (authoritative, wins)
#   confident: B          (already generated)
#   review:    —
A = _id("國", "国", "Guo2")
B = _id("中", "中", "Zhong1")
C = _id("行", "行", "Xing2")
D = _id("學", "学", "Xue2")


def test_missing_scope_excludes_cfdict_and_existing_llm():
    missing = compute_missing_scope({A, B, C, D}, {A}, {B}, set())
    assert missing == {C, D}


def test_missing_scope_is_empty_when_fully_covered():
    assert compute_missing_scope({A, B}, {A, B}, set(), set()) == set()
    assert compute_missing_scope({A}, {A}, {A}, {A}) == set()


def test_review_entries_do_not_reenter_missing_scope():
    missing = compute_missing_scope({A, B, C}, {A}, set(), {B})
    assert missing == {C}


def test_confident_scope_is_cfdict_plus_confident():
    scope = compute_confident_scope({A}, {B})
    assert scope == {A, B}
    # review content has no path into the confident dictionary (spec §10.1):
    # compute_confident_scope does not even accept review ids.
    assert C not in compute_confident_scope({A}, {B})


def test_full_scope_includes_review():
    scope = compute_full_scope({A}, {B}, {C})
    assert scope == {A, B, C}


def test_scope_statistics_are_consistent():
    stats = compute_scope_statistics({A, B, C, D}, {A}, {B}, {C})
    assert stats["cc_cedict_total"] == 4
    assert stats["cfdict_total"] == 1
    assert stats["llm_confident_total"] == 1
    assert stats["llm_review_total"] == 1
    assert stats["missing_scope_total"] == 1  # only D
    assert stats["confident_dictionary_total"] == 2  # A + B
    assert stats["full_dictionary_total"] == 3  # A + B + C
    assert stats["cfdict_covers_cc_cedict"] == 1
