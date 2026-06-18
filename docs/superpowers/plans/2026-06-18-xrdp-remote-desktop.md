# xrdp Remote Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add xrdp + xorgxrdp remote desktop, gated by `xrdp_enabled: false` in group_vars, deploying config templates and enabling two systemd services.

**Architecture:** Single task file (`xrdp.yml`) in the `packages` role, following the same conditional pattern as `bluetooth.yml`, `sunshine.yml`, and `cloud_init.yml`. Three Jinja2 config templates (`xrdp.ini.j2`, `sesman.ini.j2`, `startwm.sh.j2`) are rendered to `/etc/xrdp/`. Packages are AUR (`xrdp`, `xorgxrdp`), always installed; service enablement is gated by `xrdp_enabled`.

**Tech Stack:** Ansible (community.general >= 8.0.0), Arch Linux (xrdp + xorgxrdp from AUR via paru), Jinja2 templates.

---

### Task 1: Add `xrdp_enabled` variable to group_vars/all.yml

**Files:**
- Modify: `ansible/group_vars/all.yml`

- [ ] **Step 1: Add `xrdp_enabled` variable**

In `ansible/group_vars/all.yml`, add after the `dotfiles_use_encryption` block (end of file):

```yaml

# xrdp remote desktop (xorgxrdp backend, i3 session).
# Set to true to install and enable xrdp + xrdp-sesman.
# Packages (xrdp, xorgxrdp) are always installed from AUR; service
# enablement is gated by this flag.
xrdp_enabled: false
```

- [ ] **Step 2: Commit**

```bash
git add ansible/group_vars/all.yml
git commit -m "feat: add xrdp_enabled variable gate"
```

---

### Task 2: Add xrdp AUR packages to defaults/main.yml

**Files:**
- Modify: `ansible/roles/packages/defaults/main.yml`

- [ ] **Step 1: Add packages to aur_packages list**

In `ansible/roles/packages/defaults/main.yml`, append to the `aur_packages` list:

```yaml
  # xrdp remote desktop (xorgxrdp backend)
  - xrdp
  - xorgxrdp
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/defaults/main.yml
git commit -m "feat: add xrdp and xorgxrdp to AUR packages"
```

---

### Task 3: Add Restart xrdp handler

**Files:**
- Modify: `ansible/roles/packages/handlers/main.yml`

- [ ] **Step 1: Add handler**

In `ansible/roles/packages/handlers/main.yml`, append after the `Regenerate initramfs` handler:

```yaml
- name: Restart xrdp
  become: true
  ansible.builtin.systemd:
    name: "{{ item }}"
    state: restarted
  loop:
    - xrdp.service
    - xrdp-sesman.service
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/handlers/main.yml
git commit -m "feat: add Restart xrdp handler"
```

---

### Task 4: Create xrdp.ini.j2 template

**Files:**
- Create: `ansible/roles/packages/templates/xrdp.ini.j2`

- [ ] **Step 1: Create template file**

```jinja2
# {{ ansible_managed }}
# xrdp main configuration — port, security, backend definitions.

[Globals]
ini_version=1

port=3389
port=vsock://-1
use_vsock=false

tcp_nodelay=true
tcp_keepalive=true

security_layer=negotiate
crypt_level=high

certificate=
key_file=

ssl_protocols=TLSv1.2, TLSv1.3

autorun=

allow_channels=true
allow_multimon=true
bitmap_cache=true
bitmap_compression=true

bulk_compression=true

max_bpp=32
use_compression=true

new_cursors=true

use_fastpath=both

[Logging]
LogFile=/var/log/xrdp.log
LogLevel=INFO
EnableSyslog=true
SyslogLevel=INFO

[Channels]
rdpdr=true
rdpsnd=true
drdynvc=true
cliprdr=true
rail=true
xrdpvr=true
tcutils=true

[Xorg]
name=Xorg
lib=libxup.so
username=ask
password=ask
ip=127.0.0.1
port=-1
code=20
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/templates/xrdp.ini.j2
git commit -m "feat: add xrdp.ini.j2 template"
```

---

### Task 5: Create sesman.ini.j2 template

**Files:**
- Create: `ansible/roles/packages/templates/sesman.ini.j2`

- [ ] **Step 1: Create template file**

```jinja2
# {{ ansible_managed }}
# xrdp session manager configuration.

[Globals]
ListenAddress=127.0.0.1
ListenPort=3350
EnableUserWindowManager=true
UserWindowManager=startwm.sh
DefaultWindowManager=startwm.sh

MaxSessions=10

KillDisconnected=false
DisconnectedTimeLimit=0
IdleTimeLimit=0

Policy=UBDC

[Security]
AllowRootLogin=false
MaxLoginRetry=4
TerminalServerUsers=tsusers
TerminalServerAdmins=tsadmins
AlwaysGroupCheck=false
RestrictOutboundClipboard=false

[Sessions]
MaxSessions=10
X11DisplayOffset=10

[SessionVariables]
PULSE_SCRIPT=/etc/xrdp/pulse/default.pa

[Logging]
LogFile=/var/log/xrdp-sesman.log
LogLevel=INFO
EnableSyslog=true
SyslogLevel=INFO

[Xorg]
param=-config
param=/etc/X11/xrdp/xorg.conf
param=-noreset
param=-nolisten
param=tcp
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/templates/sesman.ini.j2
git commit -m "feat: add sesman.ini.j2 template"
```

---

### Task 6: Create startwm.sh.j2 template

**Files:**
- Create: `ansible/roles/packages/templates/startwm.sh.j2`

- [ ] **Step 1: Create template file**

```jinja2
#!/bin/sh
# {{ ansible_managed }}
# xrdp session startup — launches i3 with full environment.

# Pre-session: source .xprofile for input method variables.
# This must happen before the X session starts so GTK/Qt/X11 apps
# pick up the correct fcitx5 im modules.
test -r "$HOME/.xprofile" && . "$HOME/.xprofile"

export XDG_CURRENT_DESKTOP=i3
export XDG_SESSION_TYPE=x11

# Use zsh login shell so .zprofile and .zshrc (mise, PATH, etc.) are
# loaded before exec i3. Terminals opened from i3 (Mod+Enter) inherit
# the full environment.
exec /usr/bin/zsh -l -c "exec i3"
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/templates/startwm.sh.j2
git commit -m "feat: add startwm.sh.j2 template for i3 xrdp sessions"
```

---

### Task 7: Create xrdp.yml task file

**Files:**
- Create: `ansible/roles/packages/tasks/xrdp.yml`

- [ ] **Step 1: Create task file**

```yaml
---
- name: Deploy xrdp configuration templates
  become: true
  ansible.builtin.template:
    src: "{{ item.src }}"
    dest: "{{ item.dest }}"
    owner: root
    group: root
    mode: "{{ item.mode }}"
  loop:
    - { src: xrdp.ini.j2,   dest: /etc/xrdp/xrdp.ini,   mode: "0644" }
    - { src: sesman.ini.j2, dest: /etc/xrdp/sesman.ini, mode: "0644" }
    - { src: startwm.sh.j2, dest: /etc/xrdp/startwm.sh, mode: "0755" }
  notify: Restart xrdp

- name: Enable and start xrdp services
  become: true
  ansible.builtin.systemd:
    name: "{{ item }}"
    enabled: true
    state: started
  loop:
    - xrdp.service
    - xrdp-sesman.service
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/tasks/xrdp.yml
git commit -m "feat: add xrdp.yml task file"
```

---

### Task 8: Wire xrdp.yml into packages/tasks/main.yml

**Files:**
- Modify: `ansible/roles/packages/tasks/main.yml`

- [ ] **Step 1: Add include_tasks entry**

In `ansible/roles/packages/tasks/main.yml`, append after the `sunshine.yml` block:

```yaml
- name: Configure xrdp when xrdp_enabled is true
  ansible.builtin.include_tasks: xrdp.yml
  when: xrdp_enabled | default(false) | bool
  tags: [packages, xrdp]
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/tasks/main.yml
git commit -m "feat: wire xrdp.yml into packages role"
```

---

### Task 9: Lint and verify

**Files:** All modified and created above.

- [ ] **Step 1: Run ansible-lint**

```bash
ansible-lint ansible/playbook.yml
```

Expected: No errors. Fix any issues found.

- [ ] **Step 2: Verify syntax with ansible-playbook --syntax-check**

```bash
ansible-playbook ansible/playbook.yml --syntax-check
```

Expected: "playbook: ansible/playbook.yml" (no errors).

- [ ] **Step 3: Run idempotency check (xrdp disabled)**

```bash
# Verify playbook still passes idempotency with default xrdp_enabled: false
ansible-playbook ansible/playbook.yml --ask-become-pass
ansible-playbook ansible/playbook.yml --ask-become-pass
```

Expected: Second run PLAY RECAP shows `changed=0`.

- [ ] **Step 4: Run shellcheck on startwm.sh template**

```bash
# Extract the non-Jinja2 content and check
shellcheck -s sh ansible/roles/packages/templates/startwm.sh.j2
```

Fix any warnings.

- [ ] **Step 5: Run yamllint on new files**

```bash
yamllint ansible/roles/packages/tasks/xrdp.yml
```

Expected: No warnings.

- [ ] **Step 6: Run project lint script**

```bash
tests/lint.sh
```

Expected: All checks pass.

- [ ] **Step 7: Commit any lint fixes**

```bash
git add -A && git commit -m "chore: lint fixes for xrdp feature"
```
