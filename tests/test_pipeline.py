"""Tests for the local end-to-end pipeline (spec §13 workflow, locally).

Fake endpoint throughout. Covers the full run, dry-run purity,
fail-fast stage attribution, and --skip-generate.
"""

import json

import pytest

from cfdict_next.cli.pipeline import PipelineError, main, run_pipeline
from cfdict_next.generation.config import LLMConfig


def config(**overrides):
    args = {
        "endpoint": "http://test:1/x",
        "model": "m",
        "batch_size": 10,
        "max_retries": 0,
        "timeout_s": 5.0,
    }
    args.update(overrides)
    return LLMConfig(**args)


CFDICT_SAMPLE = "中國 中国 [Zhong1 guo2] /Chine/\n"
CC_SAMPLE = (
    "中國 中国 [Zhong1 guo2] /China/Middle Kingdom/\n"
    "美 美 [Mei3] /beautiful/\n"
    "行 行 [Xing2] /to walk/\n"
)


def write(path, content):
    path.write_text(content, encoding="utf-8")
    return path


def fixture(tmp_path, confident=None, review=None):
    cfdict = write(tmp_path / "cfdict.u8", CFDICT_SAMPLE)
    cc = write(tmp_path / "cc.u8", CC_SAMPLE)
    confident_p = write(
        tmp_path / "confident.json",
        json.dumps(confident if confident is not None else {}, ensure_ascii=False),
    )
    review_p = write(
        tmp_path / "review.json",
        json.dumps(review if review is not None else {}, ensure_ascii=False),
    )
    return cfdict, cc, confident_p, review_p


def fake_post(endpoint, model, system, user, timeout_s):
    import json as _json
    import re

    objects = []
    current = None
    for line in user.splitlines():
        m = re.match(r"^\[(\d+)\] (\S+)", line)
        if m:
            current = {"id": int(m[1]), "word": m[2], "senses": []}
            objects.append(current)
        g = re.match(r'^\s+-\s+"(.*)"$', line)
        if g and current is not None:
            current["senses"].append({"gloss": g[1], "fr": f"fr-{g[1]}"})
    for obj in objects:
        obj["confidence"] = "confident"
    return {"choices": [{"message": {"content": _json.dumps(objects)}}]}


def base_kwargs(tmp_paths, **overrides):
    cfdict, cc, confident_p, review_p = tmp_paths
    args = {
        "cfdict_path": cfdict,
        "cc_cedict_path": cc,
        "confident_path": confident_p,
        "review_path": review_p,
        "out_confident_path": tmp_paths[0].parent / "c.u8",
        "out_full_path": tmp_paths[0].parent / "f.u8",
        "config": config(),
        "cc_version": "cc-test",
        "limit": 0,
        "post": fake_post,
        "generation_date": "T",
    }
    args.update(overrides)
    return args


def test_full_run_end_to_end(tmp_path):
    paths = fixture(tmp_path)
    out_scope = tmp_path / "scope.md"
    report = run_pipeline(**base_kwargs(paths, scope_out=out_scope))
    assert not report.dry_run
    assert report.missing_scoped == 2  # 美 + 行 (中國 is CFDICT)
    assert report.generated == 2
    assert report.confident_new == 2 and report.review_new == 0
    assert report.confident_n == 3 and report.full_n == 3
    assert (tmp_path / "c.u8").exists() and (tmp_path / "f.u8").exists()
    text = out_scope.read_text(encoding="utf-8")
    assert "Confident dictionary: 3 entries" in text
    confident = json.loads((tmp_path / "confident.json").read_text(encoding="utf-8"))
    assert set(confident) == {"美|美|Mei3", "行|行|Xing2"}


def test_dry_run_calls_nothing_and_writes_nothing(tmp_path):
    paths = fixture(tmp_path)
    before = (
        (tmp_path / "confident.json").read_bytes(),
        (tmp_path / "review.json").read_bytes(),
    )
    calls = []
    report = run_pipeline(
        **base_kwargs(paths, dry_run=True, post=lambda *a: calls.append(1) or fake_post(*a))
    )
    assert report.dry_run and calls == []
    assert report.missing_scoped == 2
    assert (tmp_path / "confident.json").read_bytes() == before[0]
    assert not (tmp_path / "c.u8").exists()  # no assembly in dry-run


def test_validation_failure_stops_before_assembly(tmp_path):
    bad_confident = {
        "美|美|Mei3": {
            "traditional": "美", "simplified": "美", "pinyin": "Mei3",
            "senses": [{"source_gloss": "pretty", "french_definition": "joli"}],
            "confidence": "confident", "cc_cedict_version": "v",
            "llm_model": "m", "prompt_version": "p",
            "generation_date": "2025-01-01T00:00:00+00:00",
        }
    }
    paths = fixture(tmp_path, confident=bad_confident)
    with pytest.raises(PipelineError, match=r"\[validate-inputs\]"):
        run_pipeline(**base_kwargs(paths, skip_generate=True))
    assert not (tmp_path / "c.u8").exists()


def test_skip_generate_uses_current_datasets(tmp_path):
    calls = []
    paths = fixture(tmp_path)
    report = run_pipeline(
        **base_kwargs(paths, skip_generate=True,
                      post=lambda *a: calls.append(1) or fake_post(*a))
    )
    assert calls == []
    assert report.generated == 0 and report.missing_scoped == 0
    assert report.confident_n == 1 and report.full_n == 1  # CFDICT only


def test_cli_dry_run(tmp_path, capsys):
    cfdict, cc, confident_p, review_p = fixture(tmp_path)
    env = tmp_path / ".env"
    env.write_text("LLM_API_ENDPOINT=http://x:1/y\nLLM_MODEL_NAME=m\n", encoding="utf-8")
    rc = main(
        ["--env", str(env), "--cfdict", str(cfdict), "--cc-cedict", str(cc),
         "--confident", str(confident_p), "--review", str(review_p),
         "--out-confident", str(tmp_path / "c.u8"),
         "--out-full", str(tmp_path / "f.u8"),
         "--scope-out", str(tmp_path / "scope.md"), "--dry-run"]
    )
    assert rc == 0
    assert "dry run" in capsys.readouterr().out


def test_cli_limit_defaults_to_unlimited(tmp_path, monkeypatch):
    import cfdict_next.cli.pipeline as pipeline_mod
    from cfdict_next.cli.pipeline import PipelineReport

    cfdict, cc, confident_p, review_p = fixture(tmp_path)
    env = tmp_path / ".env"
    env.write_text("LLM_API_ENDPOINT=http://x:1/y\nLLM_MODEL_NAME=m\n", encoding="utf-8")
    seen = {}

    def fake_run(**kwargs):
        seen.update(kwargs)
        return PipelineReport(
            dry_run=True, missing_scoped=0, generated=0, confident_new=0,
            review_new=0, cleanup=None, confident_n=0, full_n=0, scope_markdown="",
        )

    monkeypatch.setattr(pipeline_mod, "run_pipeline", fake_run)
    rc = main(
        ["--env", str(env), "--cfdict", str(cfdict), "--cc-cedict", str(cc),
         "--confident", str(confident_p), "--review", str(review_p),
         "--out-confident", str(tmp_path / "c.u8"),
         "--out-full", str(tmp_path / "f.u8"),
         "--scope-out", str(tmp_path / "scope.md"), "--dry-run"]
    )
    assert rc == 0
    assert seen["limit"] == 0
    assert seen["progress"] is True
    rc = main(
        ["--env", str(env), "--cfdict", str(cfdict), "--cc-cedict", str(cc),
         "--confident", str(confident_p), "--review", str(review_p),
         "--out-confident", str(tmp_path / "c.u8"),
         "--out-full", str(tmp_path / "f.u8"),
         "--scope-out", str(tmp_path / "scope.md"), "--dry-run",
         "--no-progress"]
    )
    assert rc == 0
    assert seen["progress"] is False


def test_cli_reports_generation_error_with_stage(tmp_path, capsys, monkeypatch):
    import cfdict_next.cli.pipeline as pipeline_mod

    cfdict, cc, confident_p, review_p = fixture(tmp_path)
    env = tmp_path / ".env"
    env.write_text("LLM_API_ENDPOINT=http://x:1/y\nLLM_MODEL_NAME=m\n", encoding="utf-8")

    def failing_run(**kwargs):
        raise pipeline_mod.PipelineError("generate", "1 entry failed after retry")

    monkeypatch.setattr(pipeline_mod, "run_pipeline", failing_run)
    rc = main(
        ["--env", str(env), "--cfdict", str(cfdict), "--cc-cedict", str(cc),
         "--confident", str(confident_p), "--review", str(review_p),
         "--out-confident", str(tmp_path / "c.u8"),
         "--out-full", str(tmp_path / "f.u8"),
         "--scope-out", str(tmp_path / "scope.md")]
    )
    assert rc == 1
    assert "[generate]" in capsys.readouterr().out
