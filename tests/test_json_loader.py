"""Unit tests for LLM dataset loading/validation (src/parser/json.py, spec §4, §8, §14)."""

import json

import pytest

from src.parser.json import LLMDataError, load_llm_json


def make_record(**overrides):
    record = {
        "traditional": "中國",
        "simplified": "中国",
        "pinyin": "Zhong1 guo2",
        "source_gloss": "China",
        "french_definition": "pays d'Asie de l'Est",
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
    assert data["中國|中国|Zhong1 guo2"]["french_definition"] == "pays d'Asie de l'Est"


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


def test_review_file_same_structure(tmp_path):
    f = write_dataset(
        tmp_path,
        {"行|行|Xing2": make_record(
            traditional="行", simplified="行", pinyin="Xing2",
            source_gloss="to walk", confidence="review",
        )},
    )
    data = load_llm_json(f)
    assert data["行|行|Xing2"]["confidence"] == "review"
