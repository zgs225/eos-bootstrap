# RDP Remote Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add xrdp + Xvnc support for independent RDP remote desktop sessions on the EndeavourOS workstation.

**Architecture:** xrdp listens on 3389, sesman forks Xvnc per connection, i3wm runs inside each session. PAM authenticates users. Configuration is deployed via Ansible template.

**Tech Stack:** xrdp, tigervnc (Xvnc), Ansible, systemd

---

### Task 1: Add xrdp and tigervnc to pacman packages

**Files:**
- Modify: `ansible/roles/packages/defaults/main.yml`

- [ ] **Step 1: Add packages to the list**

Add `xrdp` and `tigervnc` to `pacman_packages` in `ansible/roles/packages/defaults/main.yml`, in a new `# Remote desktop` comment section after the Cloud / VM guests block (after line 84):

```yaml
  # Remote desktop (RDP via xrdp + Xvnc)
  - xrdp
  - tigervnc
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/defaults/main.yml
git commit -m "feat(packages): add xrdp and tigervnc for RDP remote desktop"
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

### Task 3: Create xrdp configuration task and template

**Files:**
- Create: `ansible/roles/packages/tasks/xrdp.yml`
- Create: `ansible/roles/packages/templates/sesman.ini.j2`
- Create: `ansible/roles/packages/handlers/main.yml`
- Modify: `ansible/roles/packages/tasks/main.yml`

We deploy the full `sesman.ini` as a template — the same pattern used by `sysctl.d.conf.j2` in the kernel role. The only change from the upstream default is adding `-securitytypes None` to the `[Xvnc]` param list so the VNC layer does not prompt for a separate password (xrdp already authenticates via PAM). Ansible is the source of truth for system config.

- [ ] **Step 1: Create sesman.ini.j2 template**

Create `ansible/roles/packages/templates/sesman.ini.j2`:

```ini
;; Managed by Ansible — do not edit by hand.
;; See `man 5 sesman.ini` for details.

[Globals]
ListenAddress=127.0.0.1
ListenPort=3350
EnableUserWindowManager=true
UserWindowManager=startwm.sh
DefaultWindowManager=startwm.sh
ReconnectScript=

[Logging]
LogFile=/var/log/xrdp-sesman.log
LogLevel=INFO
EnableSyslog=true
SyslogLevel=INFO

[Sessions]
X11DisplayOffset=10
MaxSessions=10
KillDisconnected=false
DisconnectedTimeLimit=0
IdleTimeLimit=0
Policy=Default

[Security]
AllowRootLogin=false
MaxLoginRetry=4
AlwaysGroupCheck=false

[Chansrv]
FuseMountName=thinclient_drives

[SessionVariables]

[Xvnc]
param=Xvnc
param=-bs
param=-nolisten
param=tcp
param=-localhost
param=-dpi
param=96
param=-securitytypes
param=None
```

- [ ] **Step 2: Create xrdp task file**

Create `ansible/roles/packages/tasks/xrdp.yml`:

```yaml
---
- name: Deploy sesman.ini
  ansible.builtin.template:
    src: sesman.ini.j2
    dest: /etc/xrdp/sesman.ini
    owner: root
    group: root
    mode: "0644"
  notify: Restart xrdp
  tags: [packages, xrdp]
```

- [ ] **Step 3: Create handlers file**

Create `ansible/roles/packages/handlers/main.yml`:

```yaml
---
- name: Restart xrdp
  ansible.builtin.systemd:
    name: xrdp.service
    state: restarted
```

- [ ] **Step 4: Include xrdp task from main.yml**

Add the xrdp task include to `ansible/roles/packages/tasks/main.yml` after the cloud_init include:

```yaml
- name: Configure xrdp
  ansible.builtin.include_tasks: xrdp.yml
  tags: [packages, xrdp]
```

- [ ] **Step 5: Commit**

```bash
git add ansible/roles/packages/tasks/xrdp.yml \
        ansible/roles/packages/templates/sesman.ini.j2 \
        ansible/roles/packages/handlers/main.yml \
        ansible/roles/packages/tasks/main.yml
git commit -m "feat(packages): add xrdp configuration task, template, and handler"
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
