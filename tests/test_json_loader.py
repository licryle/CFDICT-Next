"""Unit tests for LLM dataset loading/validation (src/parser/json.py, spec §4, §5, §8, §14, §15)."""

import json

import pytest

from cfdict_next.parser.json import LLMDataError, assert_gloss_coverage, load_llm_json


def make_record(**overrides):
    record = {
        "traditional": "中國",
        "simplified": "中国",
        "pinyin": "Zhong1 guo2",
        "senses": [
            {"source_gloss": "China", "french_definition": "pays d'Asie de l'Est"},
            {
                "source_gloss": "Middle Kingdom",
                "french_definition": "nom historique de la Chine",
            },
        ],
        "confidence": "confident",
        "cc_cedict_version": "mdbg-2025-09-12",
        "llm_model": "test-model-v1",
        "prompt_version": "p1",
        "generation_date": "2025-09-12T00:00:00Z",
    }
    record.update(overrides)
    return record


def write_dataset(tmp_path, mapping):
    f = tmp_path / "confident.json"
    f.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
    return f


def test_valid_dataset_loads(tmp_path):
    f = write_dataset(tmp_path, {"中國|中国|Zhong1 guo2": make_record()})
    data = load_llm_json(f)
    assert list(data) == ["中國|中国|Zhong1 guo2"]
    assert len(data["中國|中国|Zhong1 guo2"]["senses"]) == 2


def test_real_world_pinyin_punctuation_loads(tmp_path):
    # CC-CEDICT pinyin carries its own punctuation: ',' separates multiple
    # readings, ':' is the u:/ü convention, '·' splits transliterated names.
    # Records echo source pinyin verbatim, so the schema must admit it.
    cases = [
        ("一不做，二不休|一不做，二不休|yi1 bu4 zuo4 , er4 bu4 xiu1",
         "一不做，二不休", "一不做，二不休", "yi1 bu4 zuo4 , er4 bu4 xiu1"),
        ("綠|绿|lu:4", "綠", "绿", "lu:4"),
        ("喬治·布什|乔治·布什|Qiao2 zhi4 · Bu4 shi2",
         "喬治·布什", "乔治·布什", "Qiao2 zhi4 · Bu4 shi2"),
    ]
    for key, trad, simp, pin in cases:
        record = make_record(traditional=trad, simplified=simp, pinyin=pin)
        f = write_dataset(tmp_path, {key: record})
        assert list(load_llm_json(f)) == [key]


def test_control_characters_in_pinyin_rejected(tmp_path):
    record = make_record(pinyin="Zhong1\u0007 guo2")
    f = write_dataset(tmp_path, {"中國|中国|Zhong1\u0007 guo2": record})
    with pytest.raises(LLMDataError, match="pinyin"):
        load_llm_json(f)


def test_invalid_json_is_rejected(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{not json", encoding="utf-8")
    with pytest.raises(LLMDataError, match="invalid JSON"):
        load_llm_json(f)


def test_top_level_must_be_object(tmp_path):
    f = tmp_path / "list.json"
    f.write_text("[]", encoding="utf-8")
    with pytest.raises(LLMDataError, match="JSON object"):
        load_llm_json(f)


def test_missing_required_field_rejected(tmp_path):
    record = make_record()
    del record["prompt_version"]
    f = write_dataset(tmp_path, {"中國|中国|Zhong1 guo2": record})
    with pytest.raises(LLMDataError, match="prompt_version"):
        load_llm_json(f)


def test_bad_confidence_value_rejected(tmp_path):
    f = write_dataset(
        tmp_path,
        {"中國|中国|Zhong1 guo2": make_record(confidence="probably")},
    )
    with pytest.raises(LLMDataError, match="confidence"):
        load_llm_json(f)


def test_key_record_mismatch_rejected(tmp_path):
    # Key says 行|行|Xing2 but the record is 中國 — spec §14: fail, don't fix.
    f = write_dataset(tmp_path, {"行|行|Xing2": make_record()})
    with pytest.raises(LLMDataError, match="identity mismatch"):
        load_llm_json(f)


def test_empty_provenance_string_rejected(tmp_path):
    f = write_dataset(tmp_path, {"中國|中国|Zhong1 guo2": make_record(llm_model="")})
    with pytest.raises(LLMDataError, match="llm_model"):
        load_llm_json(f)


def test_empty_senses_rejected(tmp_path):
    f = write_dataset(tmp_path, {"中國|中国|Zhong1 guo2": make_record(senses=[])})
    with pytest.raises(LLMDataError, match="senses"):
        load_llm_json(f)


def test_sense_missing_field_rejected(tmp_path):
    f = write_dataset(
        tmp_path,
        {"中國|中国|Zhong1 guo2": make_record(senses=[{"source_gloss": "China"}])},
    )
    with pytest.raises(LLMDataError, match="french_definition"):
        load_llm_json(f)


def test_duplicate_gloss_within_record_rejected(tmp_path):
    f = write_dataset(
        tmp_path,
        {
            "中國|中国|Zhong1 guo2": make_record(
                senses=[
                    {"source_gloss": "China", "french_definition": "pays"},
                    {"source_gloss": "China", "french_definition": "pays (bis)"},
                ]
            )
        },
    )
    with pytest.raises(LLMDataError, match="duplicate source_gloss"):
        load_llm_json(f)


def test_review_file_same_structure(tmp_path):
    f = write_dataset(
        tmp_path,
        {
            "行|行|Xing2": make_record(
                traditional="行",
                simplified="行",
                pinyin="Xing2",
                senses=[
                    {
                        "source_gloss": "to walk",
                        "french_definition": "marcher (à confirmer)",
                    }
                ],
                confidence="review",
            )
        },
    )
    data = load_llm_json(f)
    assert data["行|行|Xing2"]["confidence"] == "review"


def test_gloss_coverage_exact_match_accepted():
    record = make_record()
    assert_gloss_coverage(record, {"China", "Middle Kingdom"})  # no raise


def test_gloss_coverage_missing_gloss_rejected():
    record = make_record()
    with pytest.raises(LLMDataError, match="missing French.*Cathay"):
        assert_gloss_coverage(record, {"China", "Middle Kingdom", "Cathay"})


def test_gloss_coverage_extra_gloss_rejected():
    record = make_record()
    with pytest.raises(LLMDataError, match="not in CC-CEDICT.*China"):
        assert_gloss_coverage(record, {"Middle Kingdom"})


def test_expected_confidence_accepts_matching_verdicts(tmp_path):
    f = write_dataset(tmp_path, {"中國|中国|Zhong1 guo2": make_record()})
    assert list(load_llm_json(f, "confident")) == ["中國|中国|Zhong1 guo2"]
    # No expectation: both verdicts load (back-compat for ad-hoc use).
    mixed = {"中國|中国|Zhong1 guo2": make_record(confidence="review")}
    g = write_dataset(tmp_path, mixed)
    assert list(load_llm_json(g)) == ["中國|中国|Zhong1 guo2"]


def test_expected_confidence_rejects_crossed_verdicts(tmp_path):
    f = write_dataset(
        tmp_path, {"中國|中国|Zhong1 guo2": make_record(confidence="review")}
    )
    with pytest.raises(LLMDataError, match="expected 'confident'"):
        load_llm_json(f, "confident")
    g = write_dataset(tmp_path, {"中國|中国|Zhong1 guo2": make_record()})
    with pytest.raises(LLMDataError, match="expected 'review'"):
        load_llm_json(g, "review")


def test_cleanup_rejects_crossed_verdict_file(tmp_path):
    import json

    from cfdict_next.cleanup import cleanup_files

    cfdict = tmp_path / "cfdict.u8"
    cfdict.write_text("美 美 [Mei3] /beau/\n", encoding="utf-8")
    confident_p = write_dataset(
        tmp_path, {"中國|中国|Zhong1 guo2": make_record(confidence="review")}
    )
    # write_dataset always targets confident.json; review needs its own file.
    review_p = tmp_path / "review.json"
    review_p.write_text("{}", encoding="utf-8")
    with pytest.raises(LLMDataError, match="expected 'confident'"):
        cleanup_files(cfdict, confident_p, review_p)
