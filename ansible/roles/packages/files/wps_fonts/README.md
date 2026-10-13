# Bundled no-package WPS fonts

Fonts referenced by WPS/Office documents that have **no AUR package** and
**no automatable download source**. The `packages` role deploys every
`.ttf`/`.ttc`/`.otf` in this directory to
`/usr/local/share/fonts/wps-bundled/` (tagged `packages, wps_fonts`,
handler refreshes the font cache).

## What belongs here

| File | Font name |
|------|-----------|
| STXIHEI.TTF | 华文细黑 |
| STKAITI.TTF | 华文楷体 |
| STSONG.TTF | 华文宋体 |
| STZHONGS.TTF | 华文中宋 |
| STFANGSO.TTF | 华文仿宋 |
| STXINWEI.TTF | 华文新魏 |
| STCAIYUN.TTF | 华文彩云 |
| STHUPO.TTF | 华文琥珀 |
| STLITI.TTF | 华文隶书 |
| STXINGKA.TTF | 华文行楷 |
| SIMLI.TTF | 隶书 |
| SIMYOU.TTF | 幼圆 |
| SIMKAI.TTF | 楷体_GB2312 (XP-era simkai.ttf) |
| SIMFANG.TTF | 仿宋_GB2312 (XP-era simfang.ttf) |

Additionally, `ttf-office-2007-fonts` (Garamond, Century Gothic,
Book Antiqua, Monotype Corsiva, Copperplate Gothic, MS Reference,
Franklin Gothic series, Bookshelf Symbol 7 …) is intentionally NOT in
`aur_packages`: its PKGBUILD ships no font sources and always fails a
bare paru build. If you need any of its fonts, copy the exact .ttf files
into this directory too.

These ship with Microsoft Office 简体中文版 (not Windows, not Office
EN), which is why `ttf-ms-win11-auto-zh_cn` etc. don't contain them.

## What does NOT belong here

Any font that has an AUR package (`ttf-wps-fonts`, `ttf-fangzheng`,
`ttf-office-2007-fonts`, `ttf-ms-win11-auto-zh_cn`…) — those are listed
in `roles/packages/defaults/main.yml::aur_packages` instead. Also nothing
outside ttf/ttc/otf.

## Licensing

Only copy these from a properly licensed Windows/Office machine. The
files land in a system-wide directory, so treat them the same way you
treat the license of the machine they came from.
