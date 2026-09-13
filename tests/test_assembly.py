"""Tests for dictionary assembly (Phase 7, spec §10, §14, §15).

Covers precedence and fail-loud overlaps, output ordering, the U+3000
write-back rule, lossless parser/writer round-trips over both real
datasets, determinism, and the CLI.
"""

import json
import re
from pathlib import Path

import pytest

from cfdict_next.assembly import (
    assemble,
    assemble_files,
    format_u8_entry,
    record_to_entry,
    write_u8_file,
)
from cfdict_next.parser.u8 import DictionaryEntry, iter_u8_lines, parse_u8_line, parse_u8_file

REPO = Path(__file__).resolve().parent.parent
CFDICT = REPO / "data" / "cfdict.u8"
CEDICT_GZ = REPO / "data" / "cc-cedict" / "cedict_1_0_ts_utf-8_mdbg.txt.gz"


def entry(trad="中國", simp="中国", pin="Zhong1 guo2", defs=("Chine",)):
    return DictionaryEntry(traditional=trad, simplified=simp, pinyin=pin, definitions=defs)


def llm_record_for(key, senses=(("China", "Chine"),), confidence="confident"):
    """Build an LLM record whose identity fields match its key."""
    trad, simp, pin = key.split("|")
    return {
        "traditional": trad,
        "simplified": simp,
        "pinyin": pin,
        "senses": [
            {"source_gloss": g, "french_definition": d} for g, d in senses
        ],
        "confidence": confidence,
        "cc_cedict_version": "v",
        "llm_model": "m",
        "prompt_version": "p",
        "generation_date": "2025-01-01T00:00:00+00:00",
    }


def llm_record(senses=(("China", "Chine"),), confidence="confident"):
    return llm_record_for("美|美|Mei3", senses, confidence)


def test_cfdict_always_wins_and_overlap_raises():
    cfdict = [entry()]
    confident = {"中國|中国|Zhong1 guo2": llm_record()}
    with pytest.raises(ValueError, match="overlap CFDICT"):
        assemble(cfdict, confident, {})


def test_confident_beats_review_and_overlap_raises():
    review = {"美|美|Mei3": llm_record(confidence="review")}
    confident = {"美|美|Mei3": llm_record()}
    with pytest.raises(ValueError, match="overlap CFDICT/confident"):
        assemble([], confident, review)


def test_review_overlapping_cfdict_raises():
    cfdict = [entry()]
    review = {"中國|中国|Zhong1 guo2": llm_record(confidence="review")}
    with pytest.raises(ValueError, match="overlap CFDICT/confident"):
        assemble(cfdict, {}, review)


def test_confident_dict_excludes_review_full_includes_it():
    cfdict = [entry()]
    confident = {"美|美|Mei3": llm_record_for("美|美|Mei3")}
    review = {"好|好|Hao3": llm_record_for("好|好|Hao3", confidence="review")}
    confident_entries, full_entries = assemble(cfdict, confident, review)
    assert [e.lexical_id() for e in confident_entries] == [
        "中國|中国|Zhong1 guo2",
        "美|美|Mei3",
    ]
    assert [e.lexical_id() for e in full_entries] == [
        "中國|中国|Zhong1 guo2",
        "美|美|Mei3",
        "好|好|Hao3",
    ]
    assert full_entries[2].definitions == ("Chine",)


def test_order_is_cfdict_then_sorted_llm():
    cfdict = [entry("中", "中", "Zhong1", ("milieu",)), entry()]
    confident = {
        "行|行|Xing2": llm_record_for("行|行|Xing2"),
        "美|美|Mei3": llm_record_for("美|美|Mei3"),
    }
    confident_entries, _ = assemble(cfdict, confident, {})
    assert [e.simplified for e in confident_entries] == ["中", "中国", "美", "行"]


def test_record_to_entry_preserves_sense_order():
    record = llm_record(senses=(("b", "B"), ("a", "A")))
    e = record_to_entry("美|美|Mei3", record)
    assert e.definitions == ("B", "A")


def test_format_restores_u3000():
    # Real CFDICT line 31202: the writer must put back the U+3000 the
    # parser normalizes (user rule: parser/writer are careful).
    raw = "法郎索瓦　萨维叶 法郎索瓦　萨维叶 [fa3 lang2 suo3 wa3 sa4 wei2 ye4] /François Xavier/\n"
    assert format_u8_entry(parse_u8_line(raw)) == raw


def test_real_files_round_trip_without_loss():
    # Definitions are strip-normalized on parse (20 CFDICT lines carry
    # "/ " separators or "//" empties; CC-CEDICT has none), so two
    # properties are asserted instead of naive byte equality:
    #  1. parse -> format -> parse is idempotent for EVERY entry line
    #     (the writer loses no information), and
    #  2. format(parse(line)) is byte-exact for every clean line —
    #     including the U+3000 headword the writer must restore.
    for path in (CFDICT, CEDICT_GZ):
        seen: set[str] = set()
        dup_ids: set[str] = set()
        checked = exact = quirks = 0
        for raw in iter_u8_lines(path):
            line = raw.rstrip("\r\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            e = parse_u8_line(raw)
            assert e is not None
            # Idempotence for every line, duplicates included.
            assert parse_u8_line(format_u8_entry(e)) == e, f"{path}:{line[:40]}"
            ident = e.lexical_id()
            if ident in seen:
                dup_ids.add(ident)
                continue
            seen.add(ident)
            checked += 1
            # Quirk scope: a line needs separator-whitespace normalization
            # iff any definition segment differs from its stripped self
            # (covers "/ ", " /", "//" and non-breaking spaces) or is empty,
            # or the head/pinyin region uses runs of spaces or tabs.
            defs_start = line.find("/", line.find("]"))
            inner = line[defs_start + 1 : line.rfind("/")]
            segments = inner.split("/")
            head = line[: line.find("[")]
            if (
                any(s != s.strip() or not s for s in segments)
                or re.search(r"[ \t]{2,}", head)
                or "\t" in line
            ):
                quirks += 1
                continue
            assert format_u8_entry(e) == line + "\n", f"{path}:{line[:40]}"
            exact += 1
        assert checked > 50_000, path
        assert len(dup_ids) < 100, f"unexpected duplicate surge in {path}"
        # Every first-occurrence line is either byte-exact or a known quirk.
        assert exact + quirks == checked


def test_assemble_is_deterministic(tmp_path):
    cfdict = [entry(), entry("中", "中", "Zhong1", ("milieu",))]
    confident = {"美|美|Mei3": llm_record_for("美|美|Mei3")}
    review = {"好|好|Hao3": llm_record_for("好|好|Hao3", confidence="review")}
    out1_c, out1_f = tmp_path / "c1.u8", tmp_path / "f1.u8"
    out2_c, out2_f = tmp_path / "c2.u8", tmp_path / "f2.u8"
    ce, fe = assemble(cfdict, confident, review)
    write_u8_file(out1_c, ce)
    write_u8_file(out1_f, fe)
    ce2, fe2 = assemble(cfdict, confident, review)
    write_u8_file(out2_c, ce2)
    write_u8_file(out2_f, fe2)
    assert out1_c.read_bytes() == out2_c.read_bytes()
    assert out1_f.read_bytes() == out2_f.read_bytes()


def test_assemble_files_with_empty_llm_round_trips_cfdict(tmp_path):
    # No LLM data: both outputs equal CFDICT content modulo dup-merge +
    # newline normalization — verified entry by entry.
    out_c = tmp_path / "confident.u8"
    out_f = tmp_path / "full.u8"
    (tmp_path / "c.json").write_text("{}", encoding="utf-8")
    (tmp_path / "r.json").write_text("{}", encoding="utf-8")
    confident_n, full_n = assemble_files(
        CFDICT, tmp_path / "c.json", tmp_path / "r.json", out_c, out_f
    )
    assert confident_n == full_n
    source_entries, errors = parse_u8_file(CFDICT)
    assert errors == []
    out_entries, out_errors = parse_u8_file(out_c)
    assert out_errors == []
    assert [e.lexical_id() for e in out_entries] == [
        e.lexical_id() for e in source_entries
    ]
    assert [e.definitions for e in out_entries] == [
        e.definitions for e in source_entries
    ]


def test_cli_smoke(tmp_path, capsys):
    from cfdict_next.cli.assemble import main as cli_main

    c = tmp_path / "cfdict.u8"
    c.write_text("中國 中国 [Zhong1 guo2] /Chine/\n", encoding="utf-8")
    for name in ("c.json", "r.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    rc = cli_main(
        [
            "--cfdict", str(c),
            "--confident", str(tmp_path / "c.json"),
            "--review", str(tmp_path / "r.json"),
            "--out-confident", str(tmp_path / "o_c.u8"),
            "--out-full", str(tmp_path / "o_f.u8"),
        ]
    )
    assert rc == 0
    assert (tmp_path / "o_c.u8").read_text(encoding="utf-8") == (
        (tmp_path / "o_f.u8").read_text(encoding="utf-8")
    )
    assert "confident 1 entries" in capsys.readouterr().out
