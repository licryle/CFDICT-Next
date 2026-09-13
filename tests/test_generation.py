"""Tests for the LLM generation pipeline (Phase 5, spec §5, §6, §7, §8).

Entry-level prompts: one entry (full gloss list) in, one record (full
sense list) out. No network: the HTTP layer is injected as a fake. Covers
config parsing, prompt rendering, batch validation/mapping/parity/retries,
record building with provenance, confidence splitting, the identical-sense
flag, merging, and atomic writes (round-tripped through the real Phase 3
loader).
"""

import json

import pytest

from cfdict_next.generation.config import (
    ConfigError,
    LLMConfig,
    load_config,
)
from cfdict_next.generation.llm import (
    GenerationError,
    GenerationItem,
    Sense,
    generate_batch,
)
from cfdict_next.generation.output import (
    Provenance,
    build_records,
    merge_records,
    write_llm_json,
)
from cfdict_next.generation.prompt import PROMPT_VERSION, render_prompt
from cfdict_next.parser.json import load_llm_json


def make_config(**overrides):
    args = {
        "endpoint": "http://test:1234/v1/chat/completions",
        "model": "test-model",
        "batch_size": 10,
        "max_retries": 1,
        "timeout_s": 5.0,
    }
    args.update(overrides)
    return LLMConfig(**args)


def make_items():
    return [
        GenerationItem(
            key="中國|中国|Zhong1 guo2",
            traditional="中國",
            simplified="中国",
            pinyin="Zhong1 guo2",
            glosses=("China", "Middle Kingdom"),
        ),
        GenerationItem(
            key="行|行|Xing2",
            traditional="行",
            simplified="行",
            pinyin="Xing2",
            glosses=("to walk",),
        ),
    ]


def chat_body(objects):
    return {"choices": [{"message": {"content": json.dumps(objects)}}]}


# --- config ---


def test_dotenv_parsing(tmp_path):
    f = tmp_path / ".env"
    f.write_text(
        "# comment\n"
        "LLM_API_ENDPOINT=http://192.168.2.147:1234/v1/chat/completions\n"
        'LLM_MODEL_NAME="qwen/qwen2.5-vl-7b"\n'
        "LLM_BATCH_SIZE=5\n",
        encoding="utf-8",
    )
    cfg = load_config(env_path=f, environ={})
    assert cfg.endpoint == "http://192.168.2.147:1234/v1/chat/completions"
    assert cfg.model == "qwen/qwen2.5-vl-7b"
    assert cfg.batch_size == 5
    assert cfg.max_retries == 2  # default
    assert cfg.timeout_s == 120.0  # default


def test_config_missing_required_names_the_missing(tmp_path):
    f = tmp_path / ".env"
    f.write_text("LLM_MODEL_NAME=x\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="LLM_API_ENDPOINT"):
        load_config(env_path=f, environ={})


def test_config_rejects_bad_values(tmp_path):
    f = tmp_path / ".env"
    f.write_text(
        "LLM_API_ENDPOINT=not-a-url\nLLM_MODEL_NAME=x\nLLM_BATCH_SIZE=0\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="http"):
        load_config(env_path=f, environ={})


def test_config_missing_file_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(env_path=tmp_path / "nope.env", environ={})


def test_environ_overrides_dotenv(tmp_path):
    f = tmp_path / ".env"
    f.write_text(
        "LLM_API_ENDPOINT=http://file:1/x\nLLM_MODEL_NAME=file-model\n",
        encoding="utf-8",
    )
    cfg = load_config(env_path=f, environ={"LLM_MODEL_NAME": "env-model"})
    assert cfg.model == "env-model"
    assert cfg.endpoint == "http://file:1/x"


# --- prompt ---


def test_render_lists_whole_gloss_lists_per_entry():
    system, user = render_prompt(make_items())
    assert "{example_lines}" not in system
    assert "lexicography" in system
    assert '[0] 中国 (中國, Zhong1 guo2) — senses:' in user
    assert '"China"' in user and '"Middle Kingdom"' in user
    assert '[1] 行 (行, Xing2) — senses:' in user


def test_prompt_version_is_pinned():
    assert PROMPT_VERSION == "v4"


def test_few_shot_examples_pass_the_real_validator():
    # The examples shown to the model must themselves be valid prompt /
    # response pairs — otherwise we teach the model our own mistakes.
    from cfdict_next.generation.prompt import EXAMPLE_ITEMS, EXAMPLE_OUTPUTS

    def fake_post(endpoint, model, system, user, timeout_s):
        for item, output in zip(EXAMPLE_ITEMS, EXAMPLE_OUTPUTS):
            assert f"[{output['id']}] {item.simplified}" in user
        return chat_body(EXAMPLE_OUTPUTS)

    outcome = generate_batch(
        list(EXAMPLE_ITEMS), make_config(max_retries=0), post=fake_post
    )
    assert outcome.failed == []
    confidences = [r.confidence for r in outcome.results]
    assert confidences.count("confident") == 14
    assert confidences.count("review") == 1
    assert sum(len(r.senses) for r in outcome.results) == 25


def test_few_shot_file_is_self_consistent():
    # Every curated example splits to equal English/French segment counts
    # (checked at load), and identities match the file's own fields.
    import json
    from pathlib import Path

    from cfdict_next.generation import prompt as prompt_module
    from cfdict_next.identity import compute_lexical_identity

    few_shot = (
        Path(prompt_module.__file__).parent / "assets" / "few_shot_examples.json"
    )
    raw = json.loads(few_shot.read_text(encoding="utf-8"))
    assert len(raw) >= 12
    for example in raw:
        en = [s for s in example["english"].split("/") if s.strip()]
        fr = [s for s in example["fr"].split("/") if s.strip()]
        assert len(en) == len(fr) >= 1
        assert example["confidence"] in ("confident", "review")
    keys = [
        compute_lexical_identity(e["traditional"], e["simplified"], e["pinyin"])
        for e in raw
    ]
    assert len(set(keys)) == len(keys)  # no duplicate few-shot entries


def test_prompt_states_label_abbreviation_rules():
    # Regression test for the 行 xing2 report: verbose calques such as
    # "(forme fermée)" / "(écriture littéraire)" instead of "lit.".
    system, _ = render_prompt(make_items())
    assert '(bound form)' in system
    assert 'DROP' in system
    assert '"lit. "' in system or "'lit." in system or 'lit.' in system
    assert '(Tw [X])' in system
    assert 'KEEP it verbatim' in system or '"(Tw)"' in system
    for forbidden in ("forme fermée", "écriture littéraire", "prononcé en"):
        assert forbidden in system  # named in the FORBIDDEN list, not as usage
    assert "à Taïwan" in system  # named in the FORBIDDEN list, not as usage
    assert "old variant of" in system
    assert "forme ancienne de" in system


def test_few_shot_demonstrates_label_rules():
    # The model must see at least one bound-form drop, one lit. mapping,
    # and one Tw mapping in the examples it is shown.
    from cfdict_next.generation.prompt import EXAMPLE_ITEMS, EXAMPLE_OUTPUTS

    fr_all = " / ".join(
        s["fr"] for out in EXAMPLE_OUTPUTS for s in out["senses"]
    )
    gloss_all = " / ".join(
        s["gloss"] for out in EXAMPLE_OUTPUTS for s in out["senses"]
    )
    assert "(bound form)" in gloss_all
    assert "(literary)" in gloss_all
    assert "(Taiwan pr." in gloss_all
    assert "(Tw) band-aid" in gloss_all  # OK绷: bare (Tw) preservation case
    assert "lit." in fr_all
    assert "(Tw [" in fr_all
    assert "(Tw) pansement adhésif" in fr_all  # kept verbatim, never expanded
    assert "old variant of" in gloss_all
    assert "forme ancienne de 帽[mao4]" in fr_all  # reference kept, not translated
    assert "de la casquette" not in fr_all
    for forbidden in ("forme fermée", "écriture littéraire", "prononcé en", "(à Taïwan"):
        # "(à Taïwan" with paren: the label expansion. Bare "à Taïwan" in
        # running text is legitimate (cf. 小朋友 usage note) and not banned.
        assert forbidden not in fr_all


# --- llm client ---


def test_generate_batch_maps_entries_to_sense_lists():
    def fake_post(endpoint, model, system, user, timeout_s):
        assert "chat/completions" in endpoint
        return chat_body(
            [
                {
                    "id": 1,
                    "word": "行",
                    "senses": [{"gloss": "to walk", "fr": "marcher"}],
                    "confidence": "review",
                },
                {
                    "id": 0,
                    "word": "中国",
                    "senses": [
                        {"gloss": "China", "fr": "pays d'Asie"},
                        {"gloss": "Middle Kingdom", "fr": "Empire du Milieu"},
                    ],
                    "confidence": "confident",
                },
            ]
        )

    outcome = generate_batch(make_items(), make_config(), post=fake_post)
    assert outcome.failed == []
    results = outcome.results
    assert [r.key for r in results] == ["中國|中国|Zhong1 guo2", "行|行|Xing2"]
    assert [(s.gloss, s.french_definition) for s in results[0].senses] == [
        ("China", "pays d'Asie"),
        ("Middle Kingdom", "Empire du Milieu"),
    ]
    assert results[0].confidence == "confident"
    assert results[1].confidence == "review"


def test_dropped_sense_fails_the_batch():
    def fake_post(*args):
        return chat_body(
            [
                {
                    "id": 0,
                    "word": "中国",
                    "senses": [{"gloss": "China", "fr": "pays"}],
                    "confidence": "confident",
                }
            ]
        )

    with pytest.raises(GenerationError, match="dropped sense.*Middle Kingdom"):
        generate_batch(make_items()[:1], make_config(), post=fake_post)


def test_invented_sense_fails_the_batch():
    def fake_post(*args):
        return chat_body(
            [
                {
                    "id": 0,
                    "word": "中国",
                    "senses": [
                        {"gloss": "China", "fr": "pays"},
                        {"gloss": "Middle Kingdom", "fr": "Empire"},
                        {"gloss": "Cathay", "fr": "Cathay"},
                    ],
                    "confidence": "confident",
                }
            ]
        )

    with pytest.raises(GenerationError, match="invented sense.*Cathay"):
        generate_batch(make_items()[:1], make_config(), post=fake_post)


def test_unknown_confidence_defaults_to_review():
    def fake_post(*args):
        return chat_body(
            [
                {
                    "id": 0,
                    "word": "中国",
                    "senses": [
                        {"gloss": "China", "fr": "pays"},
                        {"gloss": "Middle Kingdom", "fr": "Empire"},
                    ],
                }
            ]
        )

    outcome = generate_batch(make_items()[:1], make_config(), post=fake_post)
    assert outcome.failed == []
    (result,) = outcome.results
    assert result.confidence == "review"


def test_missing_id_retries_then_raises():
    calls = []

    def fake_post(*args):
        calls.append(1)
        return chat_body(
            [
                {
                    "id": 0,
                    "word": "中国",
                    "senses": [
                        {"gloss": "China", "fr": "pays"},
                        {"gloss": "Middle Kingdom", "fr": "Empire"},
                    ],
                    "confidence": "confident",
                }
            ]
        )

    outcome = generate_batch(make_items(), make_config(max_retries=2), post=fake_post)
    assert [r.key for r in outcome.results] == ["中國|中国|Zhong1 guo2"]
    assert [i.key for i in outcome.failed] == ["行|行|Xing2"]
    assert "missing id 1" in outcome.causes["行|行|Xing2"]
    assert len(calls) == 1  # salvaged at once: no whole-batch retries burned


def test_word_mismatch_is_rejected():
    def fake_post(*args):
        return chat_body(
            [
                {
                    "id": 0,
                    "word": "美国",
                    "senses": [{"gloss": "China", "fr": "pays"}],
                    "confidence": "confident",
                }
            ]
        )

    with pytest.raises(GenerationError, match="does not match"):
        generate_batch(make_items()[:1], make_config(), post=fake_post)


def test_non_array_response_is_rejected():
    def fake_post(*args):
        return {"choices": [{"message": {"content": '{"id": 0}'}}]}

    with pytest.raises(GenerationError, match="JSON array"):
        generate_batch(make_items()[:1], make_config(), post=fake_post)


def test_fenced_json_content_is_accepted():
    # Real LLMs wrap the array in ```json fences despite 'No markdown'.
    from cfdict_next.generation.llm import _parse_content

    payload = json.dumps(
        [{"id": 0, "word": "x", "senses": [], "confidence": "confident"}]
    )
    assert _parse_content(f"```json\n{payload}\n```")[0]["id"] == 0
    assert _parse_content(f"```\n{payload}\n```")[0]["word"] == "x"
    assert _parse_content(f"  ```json\n{payload}\n```  \n")[0]["id"] == 0
    assert _parse_content(payload)[0]["id"] == 0  # no fences: unchanged


def test_generate_batch_accepts_fenced_content():
    fenced = (
        "```json\n"
        + json.dumps(
            [
                {
                    "id": 0,
                    "word": "中国",
                    "senses": [
                        {"gloss": "China", "fr": "pays"},
                        {"gloss": "Middle Kingdom", "fr": "Empire"},
                    ],
                    "confidence": "confident",
                }
            ]
        )
        + "\n```"
    )

    def fake_post(*args):
        return {"choices": [{"message": {"content": fenced}}]}

    outcome = generate_batch(make_items()[:1], make_config(), post=fake_post)
    assert outcome.failed == []
    (result,) = outcome.results
    assert result.confidence == "confident"
    assert [s.gloss for s in result.senses] == ["China", "Middle Kingdom"]


def test_partial_salvage_returns_good_and_defers_bad():
    # One bogus entry (dropped sense) beside a good one: exactly one
    # endpoint call, good entry returned, bad one deferred with its cause.
    calls = []

    def fake_post(*args):
        calls.append(1)
        return chat_body(
            [
                {
                    "id": 0,
                    "word": "中国",
                    "senses": [
                        {"gloss": "China", "fr": "pays"},
                        {"gloss": "Middle Kingdom", "fr": "Empire"},
                    ],
                    "confidence": "confident",
                },
                {
                    "id": 1,
                    "word": "行",
                    "senses": [],
                    "confidence": "confident",
                },
            ]
        )

    outcome = generate_batch(make_items(), make_config(), post=fake_post)
    assert [r.key for r in outcome.results] == ["中國|中国|Zhong1 guo2"]
    assert [i.key for i in outcome.failed] == ["行|行|Xing2"]
    assert "non-empty array" in outcome.causes["行|行|Xing2"]
    assert len(calls) == 1


def test_envelope_failure_retries_whole_batch_then_raises():
    calls = []

    def fake_post(*args):
        calls.append(1)
        return {"choices": [{"message": {"content": '{"id": 0}'}}]}

    with pytest.raises(GenerationError, match="JSON array"):
        generate_batch(make_items(), make_config(max_retries=2), post=fake_post)
    assert len(calls) == 3  # 1 initial + 2 retries


def test_single_transient_failure_recovers_on_retry():
    calls = []
    good = chat_body(
        [
            {
                "id": 0,
                "word": "中国",
                "senses": [
                    {"gloss": "China", "fr": "pays"},
                    {"gloss": "Middle Kingdom", "fr": "Empire"},
                ],
                "confidence": "confident",
            }
        ]
    )

    def fake_post(*args):
        calls.append(1)
        if len(calls) == 1:
            return chat_body(
                [
                    {
                        "id": 0,
                        "word": "中国",
                        "senses": [{"gloss": "China", "fr": "pays"}],
                        "confidence": "confident",
                    }
                ]
            )
        return good

    outcome = generate_batch(
        make_items()[:1], make_config(max_retries=2), post=fake_post
    )
    assert outcome.failed == []
    assert [r.key for r in outcome.results] == ["中國|中国|Zhong1 guo2"]
    assert len(calls) == 2


def test_empty_batch_is_rejected():
    with pytest.raises(GenerationError, match="empty batch"):
        generate_batch([], make_config(), post=lambda *a: None)


def test_entry_without_glosses_is_rejected():
    bad = GenerationItem(key="K", traditional="T", simplified="S", pinyin="P", glosses=())
    with pytest.raises(GenerationError, match="no glosses"):
        generate_batch([bad], make_config(), post=lambda *a: None)


# --- output ---


def provenance():
    return Provenance(cc_cedict_version="mdbg-test", llm_model="test-model")


def test_build_records_splits_by_confidence():
    from cfdict_next.generation.llm import GenerationResult

    results = [
        GenerationResult(
            key="中國|中国|Zhong1 guo2", traditional="中國", simplified="中国",
            pinyin="Zhong1 guo2",
            senses=(Sense("China", "pays"), Sense("Middle Kingdom", "Empire")),
            confidence="confident",
        ),
        GenerationResult(
            key="行|行|Xing2", traditional="行", simplified="行",
            pinyin="Xing2", senses=(Sense("to walk", "marcher (?)"),),
            confidence="review",
        ),
    ]
    confident, review = build_records(
        results, provenance(), generation_date="2025-01-01T00:00:00+00:00"
    )
    assert set(confident) == {"中國|中国|Zhong1 guo2"}
    assert set(review) == {"行|行|Xing2"}
    record = confident["中國|中国|Zhong1 guo2"]
    assert [s["source_gloss"] for s in record["senses"]] == ["China", "Middle Kingdom"]
    assert record["cc_cedict_version"] == "mdbg-test"
    assert record["llm_model"] == "test-model"
    assert record["prompt_version"] == PROMPT_VERSION
    assert record["generation_date"] == "2025-01-01T00:00:00+00:00"


def test_identical_senses_force_review():
    from cfdict_next.generation.llm import GenerationResult

    results = [
        GenerationResult(
            key="K", traditional="T", simplified="S", pinyin="P",
            senses=(Sense("g1", "same"), Sense("g2", "same")),
            confidence="confident",
        ),
    ]
    confident, review = build_records(results, provenance(), generation_date="x")
    assert confident == {}
    assert set(review) == {"K"}


def test_single_sense_is_not_flagged():
    from cfdict_next.generation.llm import GenerationResult

    results = [
        GenerationResult(
            key="K", traditional="T", simplified="S", pinyin="P",
            senses=(Sense("g1", "only"),),
            confidence="confident",
        ),
    ]
    confident, review = build_records(results, provenance(), generation_date="x")
    assert set(confident) == {"K"}


def test_merge_refuses_overwrites():
    with pytest.raises(ValueError, match="refusing to overwrite"):
        merge_records({"K": {"a": 1}}, {"K": {"a": 2}})
    merged = merge_records({"A": 1}, {"B": 2})
    assert merged == {"A": 1, "B": 2}


def test_write_round_trips_through_loader(tmp_path):
    from cfdict_next.generation.llm import GenerationResult

    results = [
        GenerationResult(
            key="中國|中国|Zhong1 guo2", traditional="中國", simplified="中国",
            pinyin="Zhong1 guo2", senses=(Sense("China", "pays"),),
            confidence="confident",
        ),
    ]
    confident, _ = build_records(results, provenance(), generation_date="x")
    path = tmp_path / "confident.json"
    write_llm_json(path, confident)
    assert not path.with_suffix(".json.tmp").exists()  # no tmp left behind
    loaded = load_llm_json(path)
    assert list(loaded) == ["中國|中国|Zhong1 guo2"]
