# Source data

This directory holds the source datasets. Provenance (URL, date, checksum) is
recorded here for every file, per specification §3, §12 and §16 (releases must
be traceable to exact source versions).

## CC-CEDICT (lexical scope)

- File: `cc-cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz` (stored verbatim as published)
- Source URL: https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz
- Downloaded (UTC): 2025-09-12
- SHA-256: `b8c062da61ed1709c52a2a26370f18dfc0fcd4d4c487a9628fa73eb336e341e4`
- Size: 125,076 lines (uncompressed)
- Format: CEDICT — `traditional simplified [pinyin] /gloss1/gloss2/.../`,
  `#` lines are metadata/comments.
- Quirk: this snapshot uses CRLF (`\r\n`) line endings on every line;
  parsers must normalize before matching (verified: all 125,046 entry
  lines are canonical after stripping `\r`).
- Note: MDBG serves a daily snapshot without an explicit version identifier;
  the SHA-256 above is the release-pinning reference for this snapshot.

## CFDICT (authoritative French definitions)

- File: `cfdict.u8`
- Source URL: https://chine.in/assets/cfdict/cfdict.u8 (provided by maintainer)
- Downloaded (UTC): 2025-09-12
- SHA-256: `124d87f0fc2aed305e42ec3794584fa62bf00df9ed0aac45b950aba518795e75`
- Size: 56,326 lines (3,522,011 bytes)
- Format: CEDICT — `traditional simplified [pinyin] /définition1/définition2/.../`,
  `#` lines are metadata/comments.
- Quirk: CRLF (`\r\n`) line endings on every line (like the CC-CEDICT
  snapshot); parsers normalize before matching.
- This file is the forked authoritative source (spec §2); future updates
  arrive via pull requests against it.
