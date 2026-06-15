# fcitx5 Chinese Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Chinese (Pinyin) input method support via fcitx5, respecting the two-repo boundary.

**Architecture:** This repo (`eos-bootstrap`) installs five fcitx5 packages via the existing `packages` role and adds a runbook troubleshooting section. The dotfiles repo (separate) adds `~/.xprofile` (env vars), `~/.config/fcitx5/profile` (default Pinyin profile), and one `exec` line to the i3 config.

**Tech Stack:** Ansible (pacman module), fcitx5, chezmoi (dotfiles deployment)

---

## File Structure

| Repo | Path | Action | Responsibility |
|------|------|--------|----------------|
| eos-bootstrap | `ansible/roles/packages/defaults/main.yml` | Modify | Add 5 fcitx5 packages to `pacman_packages` |
| eos-bootstrap | `docs/runbook.md` | Modify | Add "Chinese input not working" troubleshooting section |
| dotfiles | `dot_xprofile` | Create | Export 4 IM environment variables |
| dotfiles | `dot_config/fcitx5/profile` | Create | Default profile: Chinese → Pinyin |
| dotfiles | `dot_config/i3/config` | Modify | Append `exec --no-startup-id fcitx5 -d` |

---

### Task 1: Add fcitx5 packages to pacman_packages

**Files:**
- Modify: `ansible/roles/packages/defaults/main.yml:44` (after `ttf-dejavu`, before `# Development`)

- [ ] **Step 1: Add the five fcitx5 packages**

Insert after line 44 (`  - ttf-dejavu`) and before line 45 (`  # Development`):

```yaml
  # Input method (Chinese pinyin via fcitx5)
  - fcitx5
  - fcitx5-chinese-addons
  - fcitx5-gtk
  - fcitx5-qt
  - fcitx5-configtool
```

The full block around the insertion point should read:

```yaml
  - noto-fonts-cjk
  - noto-fonts-emoji
  - ttf-dejavu
  # Input method (Chinese pinyin via fcitx5)
  - fcitx5
  - fcitx5-chinese-addons
  - fcitx5-gtk
  - fcitx5-qt
  - fcitx5-configtool
  # Development
```

- [ ] **Step 2: Verify YAML is valid**

Run: `python3 -c "import yaml; yaml.safe_load(open('ansible/roles/packages/defaults/main.yml'))"`

Expected: no output (exit 0).

- [ ] **Step 3: Run lint**

Run: `tests/lint.sh`

Expected: clean (no ansible-lint or yamllint errors). The new entries are simple YAML strings with no Jinja or shell.

- [ ] **Step 4: Commit**

```bash
git add ansible/roles/packages/defaults/main.yml
git commit -m "feat(packages): add fcitx5 Chinese input method packages"
```

---

### Task 2: Add Chinese input troubleshooting to runbook

**Files:**
- Modify: `docs/runbook.md:179` (append after the last section)

- [ ] **Step 1: Append the troubleshooting section**

After the last line of `docs/runbook.md`, append:

```markdown

## Chinese input not working

1. Confirm packages installed: `pacman -Q fcitx5 fcitx5-chinese-addons fcitx5-gtk fcitx5-qt fcitx5-configtool`
2. Confirm daemon running: `pgrep -a fcitx5` (empty = not started; check i3 config has `exec --no-startup-id fcitx5 -d`)
3. Confirm env vars in X session: `echo "$GTK_IM_MODULE $QT_IM_MODULE $XMODIFIERS $SDL_IM_MODULE"` should print `fcitx fcitx @im=fcitx fcitx`. If blank, `~/.xprofile` is not being sourced — verify `startx` chain in `~/.zprofile`.
4. Run `fcitx5-diagnose` and read the output.
5. Open `fcitx5-configtool` to verify Pinyin is listed under "Available Input Methods" and ticked under "Current Input Methods".
```

- [ ] **Step 2: Run lint**

Run: `tests/lint.sh`

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add docs/runbook.md
git commit -m "docs(runbook): add Chinese input troubleshooting section"
```

---

### Task 3: Add ~/.xprofile to dotfiles repo

**Files:**
- Create: `dot_xprofile` (in the dotfiles repo chezmoi source directory)

This task is performed in the **dotfiles repo** (`https://github.com/zgs225/dotfiles.git`, branch `chezmoi-migration`). The exact path to the chezmoi source directory depends on the repo layout — it is typically the repo root or a `home/` subdirectory within the repo.

- [ ] **Step 1: Create `dot_xprofile` in the chezmoi source directory**

Create the file with this exact content:

```sh
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export SDL_IM_MODULE=fcitx
```

The `dot_` prefix is the chezmoi convention for files that start with `.` — chezmoi renders `dot_xprofile` as `~/.xprofile` on the target machine.

- [ ] **Step 2: Verify chezmoi source state**

Run: `chezmoi source-path ~/.xprofile`

Expected: prints the absolute path to the `dot_xprofile` file you just created.

- [ ] **Step 3: Apply and verify**

Run: `chezmoi apply --verbose`

Expected: chezmoi creates `~/.xprofile` with the four export lines. No errors.

- [ ] **Step 4: Commit (dotfiles repo)**

```bash
git add dot_xprofile
git commit -m "feat: add ~/.xprofile for fcitx5 IM environment variables"
```

---

### Task 4: Add fcitx5 default profile to dotfiles repo

**Files:**
- Create: `dot_config/fcitx5/profile` (in the dotfiles repo chezmoi source directory)

This task is performed in the **dotfiles repo**.

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p dot_config/fcitx5
```

- [ ] **Step 2: Create `dot_config/fcitx5/profile`**

Create the file with this exact content:

```ini
[Groups/0]
Name=Chinese
DefaultIM=Pinyin

[Groups/0/Items/0]
Name=Pinyin
Layout=

[GroupOrder/0]
0=Chinese
```

Note: `Layout=` is left empty intentionally. fcitx5 defaults to the system keyboard layout when empty. Setting `Layout=us` explicitly can cause fcitx5 to override the X keyboard layout, which breaks switching back to English via Ctrl+Space on some configurations. The empty value is safer.

- [ ] **Step 3: Verify chezmoi source state**

Run: `chezmoi source-path ~/.config/fcitx5/profile`

Expected: prints the absolute path to the `dot_config/fcitx5/profile` file.

- [ ] **Step 4: Apply and verify**

Run: `chezmoi apply --verbose`

Expected: chezmoi creates `~/.config/fcitx5/profile` with the INI content. No errors.

- [ ] **Step 5: Commit (dotfiles repo)**

```bash
git add dot_config/fcitx5/profile
git commit -m "feat: add fcitx5 default profile (Chinese → Pinyin)"
```

---

### Task 5: Add fcitx5 autostart to i3 config in dotfiles repo

**Files:**
- Modify: `dot_config/i3/config` (in the dotfiles repo chezmoi source directory)

This task is performed in the **dotfiles repo**.

- [ ] **Step 1: Append the exec line to the i3 config**

Append to the end of `dot_config/i3/config`:

```
exec --no-startup-id fcitx5 -d
```

Do NOT add a blank line before it if the file already ends with a newline — just append the single line. If the file does not end with a newline, add one first.

- [ ] **Step 2: Verify i3 config syntax**

Run: `i3 --moreversion 2>&1 || true`

This confirms i3 is available. For a proper syntax check, if on the target machine:

Run: `i3 -C -c ~/.config/i3/config`

Expected: no output (exit 0) means valid config.

- [ ] **Step 3: Apply and verify**

Run: `chezmoi apply --verbose`

Expected: chezmoi updates `~/.config/i3/config` with the new exec line. No errors.

- [ ] **Step 4: Commit (dotfiles repo)**

```bash
git add dot_config/i3/config
git commit -m "feat(i3): autostart fcitx5 daemon"
```

---

### Task 6: End-to-end verification (on target machine)

This task is a human-on-hardware smoke test. It cannot be automated.

- [ ] **Step 1: Re-apply eos-bootstrap**

On the target machine:

```bash
cd ~/eos-bootstrap  # or wherever the repo is cloned
./bootstrap.sh
```

Expected: Ansible installs the five fcitx5 packages (first run only). chezmoi deploys the three new dotfiles files.

- [ ] **Step 2: Verify packages**

```bash
pacman -Q fcitx5 fcitx5-chinese-addons fcitx5-gtk fcitx5-qt fcitx5-configtool
```

Expected: five lines, each showing `package version`.

- [ ] **Step 3: Log out and log back in (or reboot)**

This ensures `~/.xprofile` is sourced and i3 starts fresh.

- [ ] **Step 4: Verify environment variables in the X session**

Open a terminal and run:

```bash
echo "$GTK_IM_MODULE $QT_IM_MODULE $XMODIFIERS $SDL_IM_MODULE"
```

Expected: `fcitx fcitx @im=fcitx fcitx`

- [ ] **Step 5: Verify fcitx5 daemon is running**

```bash
pgrep -a fcitx5
```

Expected: one line showing `fcitx5 -d` (or similar).

- [ ] **Step 6: Run fcitx5-diagnose**

```bash
fcitx5-diagnose
```

Expected: no errors. The output should list Pinyin as an available input method.

- [ ] **Step 7: Test Chinese input in a GTK app**

Open wezterm (or any GTK app), press `Ctrl+Space`, type `zhongwen`, and select `中` from the candidate window. The character should appear in the text field.
