#!/usr/bin/env python3
"""Generate CJK alias fonts for apps that do their own font substitution.

WPS Office keeps its own font list and substitutes missing families to a
built-in Western face without ever consulting fontconfig aliases, so
documents asking for 宋体/SimSun render as tofu blocks. The fix is to
expose REAL fonts whose family names are the missing Windows names —
legal because the sources (Adobe Source Han, LXGW WenKai) are OFL, which
only forbids using their Reserved Font Names for derivatives, not
renaming to other names.

Each source face is copied once per target family; only the name table
is rewritten (Windows en-US + zh-CN records; typographic family IDs 16/17
are dropped so the alias never merges with the original family).
Idempotent: an output is regenerated only when its source is newer.
"""

import os
import shutil
import sys

from fontTools.ttLib import TTFont

OUT_DIR = "/usr/share/fonts/ms-cjk-alias"

# (source font, [(en family, zh family, PostScript name), ...])
JOBS = [
    (
        "/usr/share/fonts/adobe-source-han-serif/SourceHanSerifCN-Regular.otf",
        [("SimSun", "宋体", "SimSun")],
    ),
    (
        "/usr/share/fonts/adobe-source-han-sans/SourceHanSansCN-Regular.otf",
        [
            ("SimHei", "黑体", "SimHei"),
            ("Microsoft YaHei", "微软雅黑", "MicrosoftYaHei"),
        ],
    ),
    (
        "/usr/share/fonts/TTF/LXGWWenKai-Regular.ttf",
        [("KaiTi", "楷体", "KaiTi")],
    ),
]

REWRITE_IDS = {1, 2, 4, 6, 16, 17}


def rename(src_path: str, en: str, zh: str, ps: str) -> str:
    font = TTFont(src_path, lazy=False)
    name = font["name"]
    for record in list(name.names):
        if record.nameID in REWRITE_IDS:
            name.removeNames(
                record.nameID, record.platformID, record.platEncID, record.langID
            )
    for lang, family in ((0x409, en), (0x804, zh)):
        name.setName(family, 1, 3, 1, lang)
        name.setName("Regular", 2, 3, 1, lang)
        name.setName(family, 4, 3, 1, lang)
        name.setName("Version 1.0 (alias)", 5, 3, 1, lang)
        name.setName(ps, 6, 3, 1, lang)
    name.setName(en, 1, 1, 0, 0)
    name.setName("Regular", 2, 1, 0, 0)
    name.setName(en, 4, 1, 0, 0)
    name.setName(ps, 6, 1, 0, 0)
    out = os.path.join(OUT_DIR, ps + os.path.splitext(src_path)[1])
    font.save(out)
    font.close()
    return out


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    regenerated = []
    for src_path, targets in JOBS:
        if not os.path.exists(src_path):
            print(f"SKIP missing source: {src_path}", file=sys.stderr)
            continue
        src_mtime = os.path.getmtime(src_path)
        for en, zh, ps in targets:
            out = os.path.join(OUT_DIR, ps + os.path.splitext(src_path)[1])
            if os.path.exists(out) and os.path.getmtime(out) >= src_mtime:
                continue
            tmp_out = rename(src_path, en, zh, ps)
            os.chmod(tmp_out, 0o644)
            os.utime(tmp_out, (src_mtime, src_mtime))
            regenerated.append(tmp_out)
    for path in regenerated:
        print(f"generated {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
