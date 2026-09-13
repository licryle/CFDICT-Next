# LLM generation — output specification (spec §4, §7, §8)

## File layout

Two JSON files, both mapping **lexical identity → record** (spec §15):

- `confident.json` — reliable enough for automatic assembly (§10.1).
- `review.json` — kept for human review, excluded from the confident
  dictionary (§10.2). There is intentionally **no** `review.u8` (spec §4).

The identity key MUST equal the identity computed from the record's own
`traditional`/`simplified`/`pinyin` fields; `src/parser/json.py` rejects
any mismatch instead of guessing (spec §14).

## Record layout: one record per entry, one sense per gloss

Generation happens per gloss (see `docs/llm_input_spec.md`), but records
are grouped per lexical entry: each record carries a `senses` list with
one `{source_gloss, french_definition}` pair per CEDICT gloss. There is
no separate record per gloss — the identity key alone cannot distinguish
glosses, so per-gloss records would collide and could silently overwrite
each other.

## Record fields (provenance, spec §8)

Every record MUST carry all of these fields:

| field               | meaning                                              |
|---------------------|------------------------------------------------------|
| `traditional`       | Traditional Chinese form                             |
| `simplified`        | Simplified Chinese form                              |
| `pinyin`            | Pinyin with tone numbers                             |
| `senses`            | List of `{source_gloss, french_definition}` — one sense per CEDICT gloss (see gloss parity below) |
| `confidence`        | `"confident"` or `"review"`                          |
| `cc_cedict_version` | CC-CEDICT snapshot the gloss came from (e.g. SHA-256 + date in `data/README.md`) |
| `llm_model`         | LLM model **and version** used                       |
| `prompt_version`    | Prompt template version used                         |
| `generation_date`   | ISO 8601 timestamp of generation                     |

The formal schema is `schemas/llm_entry.json` — the single normative
source enforced by `src/parser/json.py` (spec §14). The file schemas only
pin their respective constant — see `schemas/confident_schema.json` and
`schemas/review_schema.json`, both thin `$ref` wrappers around it).

## Gloss parity — accept/reject criterion

The French dictionary must carry the **same number of glosses per
entry as the English source**: the set of `source_gloss` values in a
record must **exactly equal** the CC-CEDICT gloss set for that entry.
A record that drops a gloss, or invents one absent from CC-CEDICT, is
**rejected** — never silently repaired (spec §14).

Enforced by `src/parser/json.py::assert_gloss_coverage`, which names the
missing and/or extra glosses. The loader itself cannot run this check
(it sees only the JSON file, not CC-CEDICT); Phase 9 wires the two
datasets together using this single shared implementation.

## Confidence classification (spec §7)

A generation belongs in `confident.json` when it is sufficiently reliable
for **automatic** dictionary assembly. It belongs in `review.json` when the
available information does not support sufficient confidence — e.g.
ambiguity, or insufficient information to determine the French definition.

Concrete triggers for `review` classification:

1. **Ambiguous gloss** — the English gloss admits several readings and the
   Chinese form + pinyin do not disambiguate (e.g. a single-character entry
   with many senses and a terse gloss).
2. **Proper nouns with uncertain French rendering** — transliterated foreign
   names, place names with competing French spellings.
3. **Obscure / archaic / highly domain-specific senses** — classical usages,
   dialectal forms, or technical terms where a wrong guess would pollute the
   dictionary.
4. **Gloss is itself a placeholder** — CEDICT glosses such as `xx5`-style
   markers or "(phonetic)"-only notes with no real semantic content.
5. **Model self-reported uncertainty** — when the generation pipeline
   surfaces low confidence, the record goes to `review`, never to
   `confident`.

When in doubt, classify as `review`: the confident dictionary is the
conservative product, and over-inclusion there is worse than under-inclusion.
The human review/promotion workflow itself is outside this specification.

## Example

See `tests/fixtures/llm_example.json`: one `confident` record and one `review`
record, with their generation inputs.
