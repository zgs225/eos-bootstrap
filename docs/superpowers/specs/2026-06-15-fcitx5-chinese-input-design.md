# Chinese Input via fcitx5 — Design

**Date:** 2026-06-15
**Status:** Draft
**Scope:** Add Chinese (Pinyin) input method support to the i3wm workstation, respecting the existing two-repo boundary.

## Purpose

The bootstrap currently installs `noto-fonts-cjk` (so Chinese characters render) but no input method framework — typing Chinese in any GTK/Qt app (browser, wezterm, IDE, chat client) is impossible. This spec adds fcitx5 + Pinyin with the minimum surface area that respects the coarse/fine split.

## Scope

**In scope:**

- Install `fcitx5` + Chinese + GTK/Qt modules + the GTK config tool via the existing `packages` role.
- Add a single `exec` line to the existing i3 config (dotfiles repo) so the daemon starts when i3 starts.
- Provide a default fcitx5 profile (dotfiles repo) that enables Chinese → Pinyin out of the box.
- Provide `~/.xprofile` (dotfiles repo) exporting the four IM environment variables before any GTK/Qt app launches.
- Runbook entry for diagnosing common breakages.

**Out of scope:**

- Per-user fcitx5 customization beyond the default profile (the user can grow it via `fcitx5-configtool` and the changes will land in `~/.config/fcitx5/`).
- Rime, double-pinyin, wubi, cangjie schemas (can be added later by the user in `fcitx5-configtool`).
- Wayland-native input method protocol (the session is X11 via `startx`).
- An IME toggle indicator in polybar (out of scope; fcitx5's built-in candidate window is sufficient).
- Toggling fcitx5 on/off via a flag in `group_vars/all.yml` (YAGNI for a single-machine bootstrap).
- Systemd user unit for fcitx5 (the daemon is started by i3's `exec`; no need for a second supervisor).

## Architecture

Two-repo split, no new Ansible role needed. This change touches exactly two files in this repo:

- `ansible/roles/packages/defaults/main.yml` — append five `fcitx5*` packages to `pacman_packages`.

The remaining work lives in the dotfiles repo (`https://github.com/zgs225/dotfiles.git`, branch `chezmoi-migration` per `ansible/group_vars/all.yml`):

- `~/.xprofile` — exports the four IM env vars.
- `~/.config/fcitx5/profile` — default profile with Chinese → Pinyin.
- `~/.config/i3/config` — append `exec --no-startup-id fcitx5 -d`.

Execution flow on a fresh machine:

```
tty1 autologin (display role → getty drop-in)
  ↓
login shell as `target_user`
  ↓
~/.zprofile (chezmoi-managed): if tty1 && !DISPLAY → exec startx
  ↓
startx → sources ~/.xprofile → exports IM env vars → exec ~/.xinitrc
  ↓
~/.xinitrc (chezmoi-managed): exec i3
  ↓
i3 reads ~/.config/i3/config → exec --no-startup-id fcitx5 -d
  ↓
fcitx5 daemon reads ~/.config/fcitx5/profile
  ↓
GTK/Qt apps inherit env vars → route input through fcitx5 via XIM
  ↓
Ctrl+Space toggles Pinyin → candidate window → commit → Chinese character
```

**Boundary rule (per `AGENTS.md`):**

- `eos-bootstrap` (this repo) installs packages. Nothing else for this feature.
- Dotfiles repo owns all user-level artifacts: env vars, fcitx5 profile, i3 autostart line.
- `bootstrap.sh` is unchanged — its existing chain already reaches both.

## Components

### This repo — `ansible/roles/packages/defaults/main.yml`

Append to `pacman_packages` (under a new comment block, after the existing `Theming` block):

```yaml
  # Input method (Chinese pinyin via fcitx5)
  - fcitx5
  - fcitx5-chinese-addons
  - fcitx5-gtk
  - fcitx5-qt
  - fcitx5-configtool
```

Package roles:

| Package | Role |
|---------|------|
| `fcitx5` | Daemon + core framework |
| `fcitx5-chinese-addons` | Pinyin + variant engines (双拼, 五笔, 仓颉) |
| `fcitx5-gtk` | `im-fcitx5.so` for GTK 2/3/4 (Firefox, Chromium, Thunar, GNOME apps) |
| `fcitx5-qt` | `libfcitx5platforminputcontextplugin.so` for Qt 5/6 (Qt/KDE apps, Qt-based Electron builds) |
| `fcitx5-configtool` | GTK GUI for managing IMs, hotkeys, themes |

### Dotfiles repo

**`~/.xprofile`** (new file, sourced by `startx` once before the WM starts):

```sh
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export SDL_IM_MODULE=fcitx
```

**`~/.config/fcitx5/profile`** (new file, the default profile — kept tiny so the user can grow it via `fcitx5-configtool` later):

```ini
[Groups/0]
# Group 0 — Chinese
Name=Chinese
DefaultIM=Pinyin

[Groups/0/Items/0]
Name=Pinyin
Layout=us

[GroupOrder/0]
0=Chinese

[Groups/0/DefaultIM]
0=Pinyin
```

**`~/.config/i3/config`** (existing file, append one line at the bottom):

```
exec --no-startup-id fcitx5 -d
```

`exec` (not `exec_always`) is correct: the daemon is long-running and must start exactly once at i3 startup. `--no-startup-id` prevents i3 from blocking on the forked daemon.

## Data Flow

GTK app launched after i3 starts:

```
GTK app inherits env vars from the X session
  → GTK_IM_MODULE=fcitx
  → loads im-fcitx5.so at module init
  → registers as XIM client
  → forwards key events to fcitx5 over XIM/XWayland
Ctrl+Space pressed
  → fcitx5 (Pinyin engine) consumes keystrokes
  → fcitx5 renders candidate window via its built-in kimpanel
  → on commit (number key or space): UTF-8 character sent back to GTK → app
```

Qt apps take the equivalent path via `libfcitx5platforminputcontextplugin.so`. Electron/Chromium picks GTK or Qt based on how it was built (most modern builds use GTK).

**Key invariant:** the four env vars must be set before fcitx5 starts AND before any GTK/Qt app forks. `~/.xprofile` is sourced by `startx` once before `~/.xinitrc` runs, so this is satisfied.

## Error Handling

Three classes of failure.

**1. Package install fails** (network, mirror issue, AUR key).
- `community.general.pacman` aborts the role with non-zero. Bootstrap dies loudly.
- Idempotent retry works after the underlying issue is fixed — same as every other package.

**2. fcitx5 daemon fails to start** (bad `~/.config/fcitx5/profile`, missing binary).
- `exec --no-startup-id` swallows stderr; symptom is silent: `Ctrl+Space` does nothing.
- Diagnostic: `fcitx5-diagnose` (ships with the package) prints environment, profile, and module state. User runs it manually.
- Malformed profile: `~/.local/share/fcitx5/crash.log` shows the parser error. Fix: delete the file, re-run `chezmoi init --apply`.

**3. Env vars missing in some apps.**
- Symptom: `Ctrl+Space` toggles nothing in some apps, works in others. Means the env vars landed after those apps forked.
- `~/.xprofile` covers `startx`-based sessions; if an app is stubborn, the runbook documents the fallback: drop a `~/.config/environment.d/fcitx5.conf` with the same four `export` lines and re-login. We do NOT ship this by default because `~/.xprofile` is sufficient for the configured chain.

**4. Idempotency** (per `AGENTS.md`, `tests/idempotency.sh` greps `changed=[1-9]` in PLAY RECAP).
- The pacman task is idempotent via `state: present` + pacman's own package tracking. First run installs five packages (one `changed=`), subsequent runs are silent. No new tasks, handlers, or roles → no new `changed=` surface.

## Testing

**1. Idempotency** — re-uses `tests/idempotency.sh`.
- Expected: PLAY RECAP shows `changed=0` on the second run.

**2. Lint** — re-uses `tests/lint.sh` (ansible-lint, yamllint, shellcheck).
- Expected: clean. New entries are simple YAML strings; no Jinja, no shell.

**3. Functional smoke test** (human-on-hardware, documented in `docs/runbook.md`):
```bash
pacman -Q fcitx5 fcitx5-chinese-addons fcitx5-gtk fcitx5-qt fcitx5-configtool
echo "$GTK_IM_MODULE $QT_IM_MODULE $XMODIFIERS $SDL_IM_MODULE"
pgrep -a fcitx5
fcitx5-diagnose
# Open wezterm → Ctrl+Space → type "zhongwen" → select 中 → commit
```

**4. Dotfiles-repo verification** — covered by chezmoi's own machinery.
- `chezmoi init --apply` deploys the three files exactly as written.
- `chezmoi diff` shows zero drift on a re-run.

**5. No automated GUI test.** fcitx5 in a CI/VM without a real display is brittle; functional smoke test is human-on-hardware by design.

## Runbook Addition

Append a new subsection to `docs/runbook.md`:

```markdown
### Chinese input not working

1. Confirm packages installed: `pacman -Q fcitx5 fcitx5-chinese-addons fcitx5-gtk fcitx5-qt fcitx5-configtool`
2. Confirm daemon running: `pgrep -a fcitx5` (empty = not started; check i3 config has `exec --no-startup-id fcitx5 -d`)
3. Confirm env vars in X session: `echo "$GTK_IM_MODULE $QT_IM_MODULE $XMODIFIERS $SDL_IM_MODULE"` should print `fcitx fcitx @im=fcitx fcitx`. If blank, `~/.xprofile` is not being sourced — verify `startx` chain in `~/.zprofile`.
4. Run `fcitx5-diagnose` and read the output.
5. Open `fcitx5-configtool` to verify Pinyin is listed under "Available Input Methods" and ticked under "Current Input Methods".
```

## Files Touched

| Repo | Path | Change |
|------|------|--------|
| eos-bootstrap | `ansible/roles/packages/defaults/main.yml` | +6 lines (comment + 5 packages) |
| eos-bootstrap | `docs/runbook.md` | +1 subsection (Chinese input troubleshooting) |
| dotfiles | `~/.xprofile` (chezmoi source: `dot_xprofile`) | new |
| dotfiles | `~/.config/fcitx5/profile` (chezmoi source: `dot_config/fcitx5/profile`) | new |
| dotfiles | `~/.config/i3/config` | +1 line (`exec --no-startup-id fcitx5 -d`) |

`bootstrap.sh` is unchanged.

## Non-Goals

- Multi-input-method switching UI (the default profile uses Chinese → Pinyin only; user can add engines via `fcitx5-configtool`).
- Polybar fcitx5 indicator module.
- Wayland input method protocol support.
- Distro-agnostic portability (this is EndeavourOS/i3 only, per the existing design).
