# xrdp VNC Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace xrdp's xorgxrdp backend with a VNC backend that connects to x0vncserver sharing the existing :0 display, enabling GPU acceleration for all applications.

**Architecture:** xrdp listens on :3389 (RDP), connects via libvnc.so to x0vncserver on 127.0.0.1:5900, which shares the :0 i3wm desktop backed by Intel GPU. xrdp-sesman is disabled (no session lifecycle needed). autologin on tty1 drives startx → i3 on :0.

**Tech Stack:** Ansible (localhost, become), archlinux (pacman/paru), systemd user services, tigervnc (x0vncserver), xrdp (RDP w/ VNC module)

## Global Constraints

- Ansible never writes under `~` except via `become_user` + explicit user-scoped path (x0vncserver user service)
- `chemin` never installs packages or enables services
- `community.general >= 8.0.0` required
- All tasks tagged with at least `[xrdp]`
- Idempotent on re-run (second pass `changed=0`)
- Lint must pass: ansible-lint, yamllint, shellcheck

---

### Task 1: Update package lists

**Files:**
- Modify: `ansible/roles/packages/defaults/main.yml:101-109`

**Interfaces:**
- Consumes: nothing
- Produces: updated `aur_packages` (no xorgxrdp), updated `pacman_packages` (includes tigervnc)

- [ ] **Step 1: Remove `xorgxrdp` from aur_packages, add `tigervnc` to pacman_packages, update comments**

In `ansible/roles/packages/defaults/main.yml`, replace lines 107-109:

```yaml
  # xrdp remote desktop (xorgxrdp backend)
  - xrdp
  - xorgxrdp
```

with:

```yaml
  # VNC (x0vncserver shares :0 for xrdp VNC backend)
  - tigervnc
  # xrdp remote desktop
  # xrdp VNC backend connects to x0vncserver on :0, no xorgxrdp needed.
  - xrdp
```

Then find the `# Cloud / VM guests` section and add `tigervnc` was accidentally not grouped. Actually, add it alongside the existing packages. The `tigervnc` line was placed in `pacman_packages`, make sure it's in the right list:

Place `- tigervnc` in `pacman_packages` list (not `aur_packages`), near the display/remote-desktop related packages. Add after line 33 (`- xclip`):

```yaml
  # VNC server for sharing :0 (xrdp VNC backend)
  - tigervnc
```

- [ ] **Step 2: Verify file parses as valid YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('ansible/roles/packages/defaults/main.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/packages/defaults/main.yml
git commit -m "feat: replace xorgxrdp with tigervnc for xrdp VNC backend"
```

---

### Task 2: Update xrdp.ini template — VNC backend

**Files:**
- Modify: `ansible/roles/packages/templates/xrdp.ini.j2:51-57`

**Interfaces:**
- Consumes: nothing
- Produces: xrdp.ini with VNC session instead of Xorg session

- [ ] **Step 1: Replace `[Xorg]` section with `[VNC]` section**

In `ansible/roles/packages/templates/xrdp.ini.j2`, replace lines 51-57:

```ini
[Xorg]
name=Xorg
lib=libxup.so
username=ask
password=ask
port=-1
code=20
```

with:

```ini
[VNC]
name=VNC
lib=libvnc.so
ip=127.0.0.1
port=5900
username=na
password=ask
```

Update the comment on line 2 from `backend definitions.` to `VNC backend to x0vncserver on :0`.

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/templates/xrdp.ini.j2
git commit -m "feat: switch xrdp.ini from xorgxrdp to VNC backend"
```

---

### Task 3: Delete obsolete templates

**Files:**
- Delete: `ansible/roles/packages/templates/sesman.ini.j2`
- Delete: `ansible/roles/packages/templates/startwm.sh.j2`
- Delete: `ansible/roles/packages/templates/Xwrapper.config.j2`

**Interfaces:**
- Consumes: nothing (these templates are no longer referenced)
- Produces: nothing (cleanup)

- [ ] **Step 1: Delete the three template files**

```bash
rm ansible/roles/packages/templates/sesman.ini.j2
rm ansible/roles/packages/templates/startwm.sh.j2
rm ansible/roles/packages/templates/Xwrapper.config.j2
```

- [ ] **Step 2: Verify no references remain in tasks**

```bash
! grep -rq 'sesman\.ini\|startwm\.sh\|Xwrapper\.config' ansible/roles/packages/tasks/
```

Expected: exit 0 (no matches found)

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/packages/templates/
git commit -m "feat: remove xorgxrdp-specific templates (sesman, startwm, Xwrapper)"
```

---

### Task 4: Create x0vncserver systemd user service template

**Files:**
- Create: `ansible/roles/packages/templates/x0vncserver.service.j2`

**Interfaces:**
- Consumes: `{{ target_user }}` variable from group_vars
- Produces: systemd user unit template for x0vncserver

- [ ] **Step 1: Write the template file**

Create `ansible/roles/packages/templates/x0vncserver.service.j2`:

```ini
# {{ ansible_managed }}
[Unit]
Description=x0vncserver — share :0 via VNC
After=graphical-session.target
BindsTo=graphical-session.target

[Service]
ExecStart=/usr/bin/x0vncserver -display :0 -rfbport 5900 -localhost -SecurityTypes None
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
```

- [ ] **Step 2: Verify file exists**

```bash
ls -la ansible/roles/packages/templates/x0vncserver.service.j2
```

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/packages/templates/x0vncserver.service.j2
git commit -m "feat: add x0vncserver systemd user service template"
```

---

### Task 5: Rewrite xrdp.yml tasks

**Files:**
- Modify: `ansible/roles/packages/tasks/xrdp.yml` (complete rewrite)

**Interfaces:**
- Consumes: `xrdp_enabled` (bool, from group_vars), `target_user` (string, from group_vars), `x0vncserver.service.j2` template, `xrdp.ini.j2` template
- Produces: VNC-backed xrdp with x0vncserver user service running

- [ ] **Step 1: Write the new xrdp.yml**

Replace the entire content of `ansible/roles/packages/tasks/xrdp.yml`:

```yaml
---
- name: Deploy xrdp.ini with VNC backend
  become: true
  ansible.builtin.template:
    src: xrdp.ini.j2
    dest: /etc/xrdp/xrdp.ini
    owner: root
    group: root
    mode: "0644"
  notify: Restart xrdp
  tags: [xrdp]

- name: Create xrdp.service systemd override directory
  become: true
  ansible.builtin.file:
    path: /etc/systemd/system/xrdp.service.d
    state: directory
    owner: root
    group: root
    mode: "0755"
  tags: [xrdp]

- name: Deploy xrdp restart-on-failure override
  become: true
  ansible.builtin.copy:
    dest: /etc/systemd/system/xrdp.service.d/restart.conf
    content: |
      [Service]
      Restart=on-failure
      RestartSec=5
    owner: root
    group: root
    mode: "0644"
  notify:
    - Reload systemd
    - Restart xrdp
  tags: [xrdp]

- name: Deploy xrdp unbind-sesman override
  become: true
  ansible.builtin.copy:
    dest: /etc/systemd/system/xrdp.service.d/unbind-sesman.conf
    content: |
      [Unit]
      BindsTo=
    owner: root
    group: root
    mode: "0644"
  notify:
    - Reload systemd
    - Restart xrdp
  tags: [xrdp]

- name: Enable and start xrdp.service
  become: true
  ansible.builtin.systemd:
    name: xrdp.service
    enabled: true
    state: started
    daemon_reload: true
  tags: [xrdp]

- name: Disable and stop xrdp-sesman.service
  become: true
  ansible.builtin.systemd:
    name: xrdp-sesman.service
    enabled: false
    state: stopped
  tags: [xrdp]

- name: Create target_user systemd user directory
  become: true
  become_user: "{{ target_user }}"
  ansible.builtin.file:
    path: "/home/{{ target_user }}/.config/systemd/user"
    state: directory
    owner: "{{ target_user }}"
    group: "{{ target_user }}"
    mode: "0755"
  tags: [xrdp]

- name: Deploy x0vncserver user service
  become: true
  become_user: "{{ target_user }}"
  ansible.builtin.template:
    src: x0vncserver.service.j2
    dest: "/home/{{ target_user }}/.config/systemd/user/x0vncserver.service"
    owner: "{{ target_user }}"
    group: "{{ target_user }}"
    mode: "0644"
  notify:
    - Reload user systemd
    - Restart x0vncserver
  tags: [xrdp]

- name: Enable x0vncserver user service
  become: true
  become_user: "{{ target_user }}"
  ansible.builtin.systemd:
    name: x0vncserver.service
    enabled: true
    scope: user
    daemon_reload: true
  environment:
    XDG_RUNTIME_DIR: "/run/user/{{ ansible_facts.getent_passwd[target_user][1] | int }}"
  tags: [xrdp]

- name: Start x0vncserver user service (best-effort)
  become: true
  become_user: "{{ target_user }}"
  ansible.builtin.systemd:
    name: x0vncserver.service
    state: started
    scope: user
  environment:
    XDG_RUNTIME_DIR: "/run/user/{{ ansible_facts.getent_passwd[target_user][1] | int }}"
  register: _x0vnc_start
  failed_when: false
  changed_when: _x0vnc_start.rc == 0
  check_mode: false
  tags: [xrdp]
```

- [ ] **Step 2: Verify no YAML syntax errors**

```bash
python3 -c "import yaml; yaml.safe_load(open('ansible/roles/packages/tasks/xrdp.yml'))" && echo "YAML OK"
```

Expected: `YAML OK` — note: if the content line `BindsTo=` causes issues, it may need quoting. Use `BindsTo=` as-is.

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/packages/tasks/xrdp.yml
git commit -m "feat: rewrite xrdp tasks for VNC backend + x0vncserver user service"
```

---

### Task 6: Update handlers — remove sesman from Restart xrdp, add user handlers

**Files:**
- Modify: `ansible/roles/packages/handlers/main.yml:13-20`

**Interfaces:**
- Consumes: notified by Task 5 (`Restart xrdp`, `Reload user systemd`, `Restart x0vncserver`)
- Produces: handlers that restart only xrdp.service (not sesman), reload/restart user services

- [ ] **Step 1: Update Restart xrdp handler and add user service handlers**

In `ansible/roles/packages/handlers/main.yml`, replace the Restart xrdp handler (lines 13-20) with:

```yaml
- name: Restart xrdp
  become: true
  ansible.builtin.systemd:
    name: xrdp.service
    state: restarted

- name: Reload user systemd
  become: true
  become_user: "{{ target_user }}"
  ansible.builtin.systemd:
    scope: user
    daemon_reload: true
  register: _user_reload
  failed_when: false
  changed_when: _user_reload.rc == 0
  check_mode: false
  environment:
    XDG_RUNTIME_DIR: "/run/user/{{ ansible_facts.getent_passwd[target_user][1] | int }}"

- name: Restart x0vncserver
  become: true
  become_user: "{{ target_user }}"
  ansible.builtin.systemd:
    name: x0vncserver.service
    scope: user
    state: restarted
  register: _x0vnc_restart
  failed_when: false
  changed_when: _x0vnc_restart.rc == 0
  check_mode: false
  environment:
    XDG_RUNTIME_DIR: "/run/user/{{ ansible_facts.getent_passwd[target_user][1] | int }}"
```

- [ ] **Step 2: Verify YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('ansible/roles/packages/handlers/main.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/packages/handlers/main.yml
git commit -m "feat: update handlers — remove sesman, add user service handlers for x0vncserver"
```

---

### Task 7: Update group_vars comments

**Files:**
- Modify: `ansible/group_vars/all.yml:53-62`

**Interfaces:**
- Consumes: nothing
- Produces: accurate documentation comments

- [ ] **Step 1: Update comments to reflect VNC backend architecture**

In `ansible/group_vars/all.yml`, replace lines 53-62:

```yaml
# tty1 autologin → startx → i3 chain.
# Set to false when using xrdp as the primary (or only) graphical session
# to avoid fcitx5 display conflicts and an unnecessary local session.
display_autologin_enabled: true

# xrdp remote desktop (xorgxrdp backend, i3 session).
# Set to true to install and enable xrdp + xrdp-sesman.
# Packages (xrdp, xorgxrdp) are always installed from AUR; service
# enablement is gated by this flag.
xrdp_enabled: true
```

with:

```yaml
# tty1 autologin → startx → i3 chain on :0.
# Must be true for xrdp VNC backend — x0vncserver shares :0 over VNC.
display_autologin_enabled: true

# xrdp remote desktop (VNC backend, shares :0 display).
# Set to true to enable xrdp (RDP) + x0vncserver (VNC sharing :0).
# xrdp-sesman is disabled; no separate X sessions.
# Package tigervnc provides x0vncserver; xrdp provides RDP listener.
xrdp_enabled: true
```

- [ ] **Step 2: Verify YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('ansible/group_vars/all.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add ansible/group_vars/all.yml
git commit -m "docs: update group_vars comments for xrdp VNC backend"
```

---

### Task 8: Lint and verify

**Files:**
- All modified files

**Interfaces:**
- Consumes: all previous task outputs
- Produces: lint-clean, idempotency-verified codebase

- [ ] **Step 1: Run lint**

```bash
tests/lint.sh
```

Expected: all checks pass (ansible-lint, yamllint, shellcheck). Fix any issues before proceeding.

- [ ] **Step 2: Run idempotency check**

```bash
tests/idempotency.sh
```

Expected: `idempotency verified` — second run shows no `changed=[1-9]` in PLAY RECAP.

If idempotency fails, inspect `/tmp/run2.log` for the task producing changes. Common culprits:
- `x0vncserver.service` user unit: ensure `systemd` module with `scope: user` handles `daemon_reload` correctly
- `xrdp.service` drop-ins: ensure `unbind-sesman.conf` triggers correctly vs. `restart.conf`

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: address lint/idempotency issues"
```

---

### Task 9: Final git log review

- [ ] **Step 1: Review commit history**

```bash
git log --oneline -10
```

Expected: clean sequence of task commits, no WIP or debug commits, no secrets.

- [ ] **Step 2: Verify no untracked or leftover files**

```bash
git status
```

Expected: clean working tree.
