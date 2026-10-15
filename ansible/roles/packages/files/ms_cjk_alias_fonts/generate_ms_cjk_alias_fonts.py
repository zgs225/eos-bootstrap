#!/usr/bin/env python3
"""Generate CJK alias fonts for apps that do their own font substitution.

Why this exists
===============
WPS Office keeps its own font list and never consults fontconfig aliases when it
resolves a document's font. For a family it does not have it falls back to one
generic CJK face -- FZFangSong / 方正仿宋_GBK. That face ships a *single*
weight. On a bold run WPS then finds no Bold face inside the resolved family and
synthesises one itself, and its synthetic bold inflates the strokes until every
glyph becomes a solid black rectangle ("黑块"). A missing family is therefore
only half of the bug: the run actually breaks when the resolved family has no
real Bold face.

Fix: expose REAL fonts whose family names ARE the missing Windows/Office names,
generated from OFL sources (Adobe Source Han, LXGW WenKai). OFL only forbids
reusing the *source's* Reserved Font Names, not renaming to other names. The
方正 (FZ*) fonts shipped with WPS are NOT OFL and are never used as sources.

Two rules make it work, and both are load-bearing:
  1. every target family gets BOTH a Regular and a Bold face;
  2. the weight metadata is normalised (OS/2.usWeightClass 400/700,
     OS/2.fsSelection BOLD/REGULAR bits, head.macStyle). A face copied from a
     Light/Medium source otherwise stays invisible to WPS's bold lookup and the
     black blocks come straight back.

Only the name table is rewritten; the source outlines are untouched.
Idempotent via a manifest (generator version + source mtime/size), so changing
the table below or this script regenerates exactly what it must.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import sys

from fontTools.ttLib import TTFont

OUT_DIR = "/usr/share/fonts/ms-cjk-alias"
MANIFEST = os.path.join(OUT_DIR, ".manifest.json")

# Bump when a change must force a full regeneration (e.g. new target names or a
# change in how faces are built). Recorded in the manifest.
GENERATOR_VERSION = 2

# Style of the generated face -> the weight it must present to applications.
FACE_WEIGHT = {"Regular": 400, "Bold": 700}

# Source families. Keys are used by TARGETS below. Only OFL sources are ever
# renamed (OFL forbids reusing the *source's* Reserved Font Names, nothing else);
# the commercial 方正 fonts are never renamed, only installed as real fonts.
SOURCES = {
    "sans": "/usr/share/fonts/adobe-source-han-sans/SourceHanSansCN-{weight}.otf",
    "serif": "/usr/share/fonts/adobe-source-han-serif/SourceHanSerifCN-{weight}.otf",
    "kai": "/usr/share/fonts/TTF/LXGWWenKai-{weight}.ttf",
    # 朱雀仿宋 (OFL) — a real 仿宋, preferred over approximating it with 思源宋体
    # Light. Covers all of GB2312 level 1 (12882 glyphs).
    "zhuque": "/usr/share/fonts/ttf-zhuque-fangsong/ZhuqueFangsong-{weight}.ttf",
}

# "This face already exists": an installed real font provides it, so there is
# nothing to generate. Used for faces that come from a package (ttf-fangzheng,
# ttf-foundertype-sc-fonts, …) — generating a second Regular for the same family
# would just give WPS two Regular faces to pick from.
REAL = ("real",)

# (tier, en family, zh family, PostScript base, Regular source, Bold source)
#   source = (SOURCE_KEY, weight) or None to skip that face.
# Tiers: 1 = families that actually appear in the documents on this machine and
# where the style matters; 2 = other common Chinese families; 3 = the long tail
# (extra scripts, single-use names). Raise MS_CJK_ALIAS_TIER to include more.
# Cost warning: every entry is a FULL copy of the source face (~8.5 MB sans,
# ~12 MB serif, ~25 MB kai, per face). List what a tier costs with --list.
TARGETS = [
    # ---------------------------------------------------------------- tier 1
    # 等线: the family behind the reported black blocks. WPS has no 等线 face,
    # so it fell back to FZFangSong, whose missing Bold made bold runs break.
    (1, "DengXian", "等线", "DengXian", ("sans", "Normal"), ("sans", "Bold")),
    (1, "DengXian Light", "等线 Light", "DengXianLight", ("sans", "Light"), ("sans", "Bold")),
    (1, "SimHei", "黑体", "SimHei", ("sans", "Regular"), ("sans", "Bold")),
    (1, "Microsoft YaHei", "微软雅黑", "MicrosoftYaHei", ("sans", "Regular"), ("sans", "Bold")),
    (1, "Microsoft YaHei Light", "微软雅黑 Light", "MicrosoftYaHeiLight", ("sans", "Light"), ("sans", "Bold")),
    (1, "STXihei", "华文细黑", "STXihei", ("sans", "Light"), ("sans", "Bold")),
    (1, "SimSun", "宋体", "SimSun", ("serif", "Regular"), ("serif", "Bold")),
    (1, "NSimSun", "新宋体", "NSimSun", ("serif", "Regular"), ("serif", "Bold")),
    # 仿宋 has no OFL equivalent *family name*, but 朱雀仿宋 (OFL) is a real
    # 仿宋, so it is used instead of approximating with 思源宋体 Light. It ships a
    # single weight, so the Bold face still comes from 思源宋体 Bold.
    (1, "FangSong", "仿宋", "FangSong", ("zhuque", "Regular"), ("serif", "Bold")),
    (1, "FangSong_GB2312", "仿宋_GB2312", "FangSongGB2312", ("zhuque", "Regular"), ("serif", "Bold")),
    (1, "STFangsong", "华文仿宋", "STFangsong", ("zhuque", "Regular"), ("serif", "Bold")),
    # FZFangSong-Z02 / 方正仿宋_GBK is WPS's generic CJK fallback family. The
    # real font (package ttf-fangzheng) is a single weight, so only its missing
    # Bold face is generated — that Bold is the safety net for every family not
    # listed here.
    (1, "FZFangSong-Z02", "方正仿宋_GBK", "FZFangSongZ02", REAL, ("serif", "Bold")),
    (1, "STZhongsong", "华文中宋", "STZhongsong", ("serif", "Regular"), ("serif", "Bold")),
    (1, "FZXiaoBiaoSong-B05", "方正小标宋简体", "FZXiaoBiaoSongB05", ("serif", "Regular"), ("serif", "Bold")),
    (1, "KaiTi", "楷体", "KaiTi", ("kai", "Regular"), ("kai", "Medium")),
    (1, "KaiTi_GB2312", "楷体_GB2312", "KaiTiGB2312", ("kai", "Regular"), ("kai", "Medium")),
    # ---------------------------------------------------------------- tier 2
    (2, "Heiti SC", "黑体-简", "HeitiSC", ("sans", "Regular"), ("sans", "Bold")),
    (2, "PingFang SC", "苹方", "PingFangSC", ("sans", "Regular"), ("sans", "Bold")),
    (2, "YouYuan", "幼圆", "YouYuan", ("sans", "Regular"), ("sans", "Bold")),
    (2, "Microsoft JhengHei", "微軟正黑體", "MicrosoftJhengHei", ("sans", "Regular"), ("sans", "Bold")),
    (2, "STSong", "华文宋体", "STSong", ("serif", "Regular"), ("serif", "Bold")),
    (2, "Songti SC", "宋体-简", "SongtiSC", ("serif", "Regular"), ("serif", "Bold")),
    (2, "PMingLiU", "新細明體", "PMingLiU", ("serif", "Regular"), ("serif", "Bold")),
    (2, "FZSSK", "方正书宋_GBK", "FZSSK", ("serif", "Regular"), ("serif", "Bold")),
    (2, "STKaiti", "华文楷体", "STKaiti", ("kai", "Regular"), ("kai", "Medium")),
    (2, "FZKai-Z03", "方正楷体_GBK", "FZKaiZ03", ("kai", "Regular"), ("kai", "Medium")),
    # 方正小标宋_GBK shares its ASCII family name with 方正小标宋简体 above, so
    # it gets a synthetic ASCII identifier; documents ask for the zh name.
    (2, "FZXiaoBiaoSongB05G", "方正小标宋_GBK", "FZXiaoBiaoSongB05G", ("serif", "Regular"), ("serif", "Bold")),
    # ---------------------------------------------------------------- tier 3
    (3, "Malgun Gothic", "맑은 고딕", "MalgunGothic", ("sans", "Regular"), ("sans", "Bold")),
    (3, "MS Gothic", "ＭＳ ゴシック", "MSGothic", ("sans", "Regular"), ("sans", "Bold")),
    (3, "MS Mincho", "ＭＳ 明朝", "MSMincho", ("serif", "Regular"), ("serif", "Bold")),
    (3, "MingLiU", "細明體", "MingLiU", ("serif", "Regular"), ("serif", "Bold")),
    (3, "FZLSK", "方正隶书_GBK", "FZLSK", ("serif", "Regular"), ("serif", "Bold")),
    (3, "FZWBK", "方正魏碑_GBK", "FZWBK", ("serif", "Regular"), ("serif", "Bold")),
    (3, "FZXKK", "方正行楷_GBK", "FZXKK", ("kai", "Regular"), ("kai", "Medium")),
]

# Name table IDs we rewrite: family, subfamily, full name, PostScript name, plus
# the typographic (16/17) pair, which we DROP so an alias never merges with the
# source family.
REWRITE_IDS = {1, 2, 4, 6, 16, 17}
# (platform, encoding, language) records to write: Windows en-US, Windows
# zh-CN (WPS queries the localized name stored in the document), and Mac Roman.
WINDOWS_RECORDS = ((0x409, None), (0x804, None))


def source_path(source: tuple[str, str]) -> str:
    key, weight = source
    return SOURCES[key].format(weight=weight)


def normalize_weight(font: TTFont, style: str) -> None:
    """Make the face present itself as the weight it claims to be.

    Faces are copied from Light/Medium sources, so their OS/2 and head weight
    fields describe the *source* weight. Applications (WPS in particular) decide
    whether a face is the regular or the bold one from exactly these fields, so
    without this the alias Bold is never found and bold renders break again.
    """
    bold = style == "Bold"
    os2 = font["OS/2"]
    head = font["head"]

    os2.usWeightClass = FACE_WEIGHT[style]
    if bold:
        os2.fsSelection = (os2.fsSelection | 0x20) & ~0x40  # BOLD, clear REGULAR
        head.macStyle |= 0x01
    else:
        os2.fsSelection = (os2.fsSelection | 0x40) & ~0x20  # REGULAR, clear BOLD
        head.macStyle &= ~0x01
    # These faces are upright; a leftover skew from the source would be applied.
    font["post"].italicAngle = 0.0


def rename(src_path: str, en: str, zh: str, ps: str, style: str) -> TTFont:
    font = TTFont(src_path, lazy=False)
    name = font["name"]
    for record in list(name.names):
        if record.nameID in REWRITE_IDS:
            name.removeNames(
                record.nameID, record.platformID, record.platEncID, record.langID
            )

    full = f"{en} {style}" if style != "Regular" else en
    for lang, family in ((0x409, en), (0x804, zh)):
        name.setName(family, 1, 3, 1, lang)
        name.setName(style, 2, 3, 1, lang)
        name.setName(f"{family} {style}" if style != "Regular" else family, 4, 3, 1, lang)
        name.setName("Version 1.0 (alias)", 5, 3, 1, lang)
        name.setName(ps, 6, 3, 1, lang)
    name.setName(en, 1, 1, 0, 0)
    name.setName(style, 2, 1, 0, 0)
    name.setName(full, 4, 1, 0, 0)
    name.setName(ps, 6, 1, 0, 0)

    normalize_weight(font, style)
    return font


def build_one(job: dict) -> str:
    out = os.path.join(OUT_DIR, job["out"])
    tmp = out + ".tmp"
    font = rename(job["src"], job["en"], job["zh"], job["ps"], job["style"])
    font.save(tmp)
    font.close()
    os.chmod(tmp, 0o644)
    os.replace(tmp, out)
    return out


def plan(tier: int) -> list[dict]:
    """Expand TARGETS into one job per (family, style) face."""
    jobs = []
    for entry_tier, en, zh, ps_base, regular, bold in TARGETS:
        if entry_tier > tier:
            continue
        for style, source in (("Regular", regular), ("Bold", bold)):
            if source is None or source == REAL:
                continue
            if style == "Regular":
                ps = ps_base
            else:
                ps = f"{ps_base}-{style}"
            jobs.append(
                {
                    "tier": entry_tier,
                    "en": en,
                    "zh": zh,
                    "ps": ps,
                    "style": style,
                    "src": source_path(source),
                    "out": ps + os.path.splitext(source_path(source))[1],
                }
            )
    return jobs


def load_manifest() -> dict:
    try:
        with open(MANIFEST, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("generator_version") == GENERATOR_VERSION:
            return data
    except (OSError, ValueError):
        pass
    return {"generator_version": GENERATOR_VERSION, "faces": {}}


def check(tier: int) -> int:
    """Assert every target family resolves to a real CJK face in both weights.

    This is the contract that keeps the black blocks away: WPS needs an actual
    Bold *face* in the family it resolves to, so both the Regular and the Bold
    lookup have to land on a CJK face with the right weight. Run this after
    installing packages — it catches a removed real font or a missing Bold.
    """
    import subprocess

    failures = []
    for entry_tier, en, zh, ps_base, regular, bold in TARGETS:
        if entry_tier > tier:
            continue
        for style, source in (("Regular", regular), ("Bold", bold)):
            if source is None:
                continue
            want_bold = style == "Bold"
            for name in sorted({en, zh}):
                # Build a real pattern: a bare family name containing '-' is
                # parsed by fontconfig as a separator, not as part of the name.
                pattern = f":family={name}"
                if want_bold:
                    pattern += ":weight=bold"
                out = subprocess.run(
                    ["fc-match", "-f", "%{file}", pattern],
                    capture_output=True, text=True,
                ).stdout.strip()
                problem = None
                if not out.endswith((".ttf", ".otf", ".ttc")):
                    problem = f"no font found ({out!r})"
                else:
                    try:
                        font = TTFont(out, fontNumber=0, lazy=True)
                        if 0x5DE5 not in font.getBestCmap():  # 工
                            problem = f"no CJK coverage ({out})"
                        elif want_bold and font["OS/2"].usWeightClass < 600:
                            problem = (
                                f"resolved a non-bold face "
                                f"(usWeightClass={font['OS/2'].usWeightClass}, {out})"
                            )
                        font.close()
                    except Exception as exc:  # noqa: BLE001
                        problem = f"cannot read {out}: {exc}"
                if problem:
                    failures.append(f"{name} [{style}]: {problem}")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print(f"{len(failures)} problem(s) over {len(TARGETS)} families")
    return 1 if failures else 0


def main() -> int:
    tier = int(os.environ.get("MS_CJK_ALIAS_TIER", "1"))
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    if mode == "--check":
        return check(tier)
    if mode == "--list":
        jobs = plan(tier)
        total = 0
        for job in jobs:
            size = os.path.getsize(job["src"]) if os.path.exists(job["src"]) else 0
            total += size
            print(
                f"tier {job['tier']}  {job['zh']:<16} {job['style']:<7} "
                f"{size / 2**20:5.1f} MB  <- {os.path.basename(job['src'])}"
            )
        print(f"\n{len(jobs)} faces, {total / 2**20:.0f} MB (tier <= {tier})")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = load_manifest()
    faces = manifest["faces"]
    jobs = plan(tier)

    todo = []
    for job in jobs:
        if not os.path.exists(job["src"]):
            print(f"SKIP missing source: {job['src']}", file=sys.stderr)
            continue
        st = os.stat(job["src"])
        record = {
            "src": job["src"],
            "src_mtime": int(st.st_mtime),
            "src_size": st.st_size,
            "en": job["en"],
            "zh": job["zh"],
            "style": job["style"],
        }
        out = os.path.join(OUT_DIR, job["out"])
        if os.path.exists(out) and faces.get(job["out"]) == record:
            continue
        job["record"] = record
        todo.append(job)

    if not todo:
        print("up to date")
        return 0

    # One process per face; Source Han faces take tens of seconds each.
    workers = min(8, len(todo), os.cpu_count() or 1)
    done = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(build_one, job): job for job in todo}
        for future in concurrent.futures.as_completed(futures):
            job = futures[future]
            try:
                path = future.result()
            except Exception as exc:  # noqa: BLE001 - report and keep going
                print(f"FAILED {job['ps']}: {exc}", file=sys.stderr)
                continue
            faces[job["out"]] = job["record"]
            done.append(path)
            print(f"generated {path}")

    # Drop manifest entries for faces no longer produced at this tier, and the
    # files they point at (e.g. a family that a new package now provides).
    wanted = {job["out"] for job in jobs}
    for stale in [k for k in faces if k not in wanted]:
        faces.pop(stale)
        try:
            os.remove(os.path.join(OUT_DIR, stale))
            print(f"removed stale {stale}")
        except OSError:
            pass

    manifest["generator_version"] = GENERATOR_VERSION
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
