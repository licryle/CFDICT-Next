"""Tests for the cleanup script (Phase 6, spec §9, §14).

Covers each precedence rule in isolation and together, dry-run behavior,
and fail-loud handling of malformed inputs.
"""

import json

import pytest

from cfdict_next.cleanup import (
    cfdict_identities,
    cleanup_datasets,
    cleanup_files,
)


def write(path, content):
    path.write_text(content, encoding="utf-8")
    return path


def record_for(key, confidence="confident"):
    """Build a valid record whose fields match its identity key."""
    trad, simp, pin = key.split("|")
    return {
        "traditional": trad,
        "simplified": simp,
        "pinyin": pin,
        "senses": [{"source_gloss": "g", "french_definition": "d"}],
        "confidence": confidence,
        "cc_cedict_version": "v",
        "llm_model": "m",
        "prompt_version": "p",
        "generation_date": "2025-01-01T00:00:00+00:00",
    }


CFDICT_SAMPLE = (
    "# sample\n"
    "中國 中国 [Zhong1 guo2] /Chine/\n"
    "行 行 [Xing2] /marcher/\n"
)

CHINA = "中國|中国|Zhong1 guo2"
WALK = "行|行|Xing2"
OTHER = "美|美|Mei3"
FOURTH = "好|好|Hao3"


def test_confident_entries_in_cfdict_are_removed():
    confident = {CHINA: record_for(CHINA), OTHER: record_for(OTHER)}
    kept, _, report = cleanup_datasets({CHINA}, confident, {})
    assert set(kept) == {OTHER}
    assert report.confident_removed_cfdict == 1
    assert report.confident_after == 1


def test_review_entries_in_cfdict_are_removed():
    review = {CHINA: record_for(CHINA, "review"), OTHER: record_for(OTHER, "review")}
    _, kept, report = cleanup_datasets({CHINA}, {}, review)
    assert set(kept) == {OTHER}
    assert report.review_removed_cfdict == 1


def test_review_entries_in_confident_are_removed():
    # Same identity in both: confident wins, review copy goes.
    confident = {WALK: record_for(WALK)}
    review = {WALK: record_for(WALK, "review"), OTHER: record_for(OTHER, "review")}
    kept_c, kept_r, report = cleanup_datasets(set(), confident, review)
    assert set(kept_c) == {WALK}
    assert set(kept_r) == {OTHER}
    assert report.review_removed_confident == 1


def test_cfdict_beats_confident_for_review_too():
    # Entry in all three datasets: survives only implicitly via CFDICT.
    confident = {CHINA: record_for(CHINA)}
    review = {CHINA: record_for(CHINA, "review")}
    kept_c, kept_r, report = cleanup_datasets({CHINA}, confident, review)
    assert kept_c == {}
    assert kept_r == {}
    assert report.review_removed_cfdict == 1
    assert report.review_removed_confident == 0  # counted under CFDICT


def test_no_overlap_is_a_no_op():
    confident = {OTHER: record_for(OTHER)}
    review = {WALK: record_for(WALK, "review")}
    kept_c, kept_r, report = cleanup_datasets({CHINA}, confident, review)
    assert kept_c == confident and kept_r == review
    assert report.confident_after == 1 and report.review_after == 1


def test_cleanup_files_end_to_end(tmp_path):
    cfdict = write(tmp_path / "cfdict.u8", CFDICT_SAMPLE)
    confident_p = write(
        tmp_path / "confident.json",
        json.dumps(
            {CHINA: record_for(CHINA), OTHER: record_for(OTHER)},
            ensure_ascii=False,
        ),
    )
    review_p = write(
        tmp_path / "review.json",
        json.dumps(
            {
                WALK: record_for(WALK, "review"),
                OTHER: record_for(OTHER, "review"),
                FOURTH: record_for(FOURTH, "review"),
            },
            ensure_ascii=False,
        ),
    )
    report = cleanup_files(cfdict, confident_p, review_p)
    # CHINA dropped from confident (now in CFDICT); WALK dropped from
    # review (now in CFDICT); OTHER dropped from review (kept confident);
    # FOURTH survives in review (nowhere else).
    assert report.confident_after == 1
    assert report.review_after == 1
    assert set(json.loads(confident_p.read_text(encoding="utf-8"))) == {OTHER}
    assert set(json.loads(review_p.read_text(encoding="utf-8"))) == {FOURTH}


def test_dry_run_writes_nothing(tmp_path):
    cfdict = write(tmp_path / "cfdict.u8", CFDICT_SAMPLE)
    confident_p = write(
        tmp_path / "confident.json", json.dumps({CHINA: record_for(CHINA)})
    )
    review_p = write(tmp_path / "review.json", json.dumps({}))
    before_c, before_r = (
        confident_p.read_bytes(),
        review_p.read_bytes(),
    )
    report = cleanup_files(cfdict, confident_p, review_p, dry_run=True)
    assert report.confident_removed_cfdict == 1
    assert confident_p.read_bytes() == before_c
    assert review_p.read_bytes() == before_r


def test_malformed_cfdict_fails_loudly(tmp_path):
    cfdict = write(tmp_path / "cfdict.u8", "this is not an entry\n")
    with pytest.raises(ValueError, match="malformed"):
        cfdict_identities(cfdict)


def test_invalid_llm_json_fails_loudly(tmp_path):
    cfdict = write(tmp_path / "cfdict.u8", CFDICT_SAMPLE)
    confident_p = write(tmp_path / "confident.json", "{bad json")
    review_p = write(tmp_path / "review.json", json.dumps({}))
    with pytest.raises(Exception, match="[Ii]nvalid JSON"):
        cleanup_files(cfdict, confident_p, review_p)
