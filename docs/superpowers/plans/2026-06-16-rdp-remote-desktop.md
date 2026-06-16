# RDP Remote Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add xrdp + Xorg support for independent RDP remote desktop sessions with hardware acceleration on the EndeavourOS workstation.

**Architecture:** xrdp listens on 3389, sesman forks Xorg per connection, i3wm runs inside each session. PAM authenticates users. Xorg backend provides GPU acceleration for wezterm and other hardware-accelerated apps.

**Tech Stack:** xrdp, xorgxrdp, Ansible, systemd

---

### Task 1: Update packages (Xvnc → Xorg)

**Files:**
- Modify: `ansible/roles/packages/defaults/main.yml`

- [ ] **Step 1: Replace tigervnc with xorgxrdp**

In `ansible/roles/packages/defaults/main.yml`, change the remote desktop section:

```yaml
  # Remote desktop (RDP via xrdp + Xorg, hardware accelerated)
  - xrdp
  - xorgxrdp
```

This replaces `tigervnc` with `xorgxrdp`.

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/defaults/main.yml
git commit -m "feat(packages): replace tigervnc with xorgxrdp for hardware-accelerated RDP"
```

---

### Task 2: Add xrdp.service to core services

**Files:**
- Modify: `ansible/roles/services/vars/core_services.yml`

- [ ] **Step 1: Add xrdp.service to core_services**

Add `xrdp.service` to the `core_services` list in `ansible/roles/services/vars/core_services.yml`:

```yaml
core_services:
  - NetworkManager.service
  - docker.service
  - fstrim.timer
  - sshd.service
  - xrdp.service
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/services/vars/core_services.yml
git commit -m "feat(services): enable xrdp.service as core service"
```

---

### Task 3: Update xrdp configuration (Xvnc → Xorg)

**Files:**
- Modify: `ansible/roles/packages/tasks/xrdp.yml`
- Modify: `ansible/roles/packages/templates/sesman.ini.j2`

We deploy the full `sesman.ini` as a template with the `[Xorg]` section configured. The `[Xvnc]` section is removed (not needed for Xorg backend).

- [ ] **Step 1: Update sesman.ini.j2 template**

Replace the `[Xvnc]` section with `[Xorg]` section in `ansible/roles/packages/templates/sesman.ini.j2`:

```ini
[Xorg]
param=/usr/lib/Xorg
param=-config
param=xrdp/xorg.conf
param=-noreset
param=-nolisten
param=tcp
```

Remove the entire `[Xvnc]` section (no longer needed).

- [ ] **Step 2: Update xrdp task if needed**

The existing task file should work as-is (it just deploys the template). No changes needed.

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/packages/templates/sesman.ini.j2
git commit -m "feat(xrdp): switch from Xvnc to Xorg backend for hardware acceleration"
```

---

### Task 4: Update design spec with dotfiles repo action item

**Files:**
- Modify: `docs/superpowers/specs/2026-06-16-rdp-remote-desktop-design.md`

The design spec already documents that `~/.xsession` must be provided by the dotfiles repo. No code changes needed in this repo for that. This task is just a reminder — no file changes required.

- [ ] **Step 1: Note the dotfiles repo requirement**

The dotfiles repo needs a `~/.xsession` file (managed by chezmoi) containing:

```sh
#!/bin/sh
exec i3
```

This is a manual action outside this repo's scope. No commit needed here.

---

### Task 5: Run lint and verify

**Files:** None (verification only)

- [ ] **Step 1: Run ansible-lint and yamllint**

```bash
cd /Users/yuez/Workspace/Misc/eos-bootstrap
bash tests/lint.sh
```

Expected: all lints passed.

- [ ] **Step 2: Fix any lint errors if present**

If yamllint or ansible-lint reports issues, fix them and re-run.
