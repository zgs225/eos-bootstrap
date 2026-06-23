# Hyprland/Wayland Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace X11/i3 display stack with Wayland/Hyprland by swapping packages, removing xrdp infrastructure, and updating group_vars.

**Architecture:** In-place replacement in the existing role structure. No new roles, no new variables, no conditional logic. Three independent file-change groups: package lists, xrdp cleanup, and variable updates.

**Tech Stack:** Ansible (community.general.pacman), Arch Linux packages (hyprland, waybar, mako, etc.)

## Global Constraints

- `become: true` for all system-level tasks (Ansible config inherited from playbook)
- All edits must pass `tests/lint.sh` (ansible-lint, yamllint, shellcheck)
- All edits must pass `tests/idempotency.sh` (playbook re-run produces zero `changed=` tasks)
- Package lists stay in `defaults/main.yml` (not `vars/`) per the existing convention documented in the file header
- No new Ansible roles, no new variables — hard switch, no compositor-selection gate

---

### Task 1: Swap Display Packages

**Files:**
- Modify: `ansible/roles/packages/defaults/main.yml`

**Interfaces:**
- Consumes: nothing
- Produces: updated `pacman_packages` and `aur_packages` lists consumed by `tasks/pacman.yml` and `tasks/aur.yml`

- [ ] **Step 1: Remove X11 display packages from pacman_packages**

Remove lines 30-49 (X11 section, GPU section comment, VNC section, i3wm ecosystem section):

```
# Xorg / X11 (startx + i3 — no display manager)
- xorg-server
- xorg-xinit
- xclip
# GPU drivers and diagnostics (Intel / virtio / modesetting)
- mesa
- mesa-utils
# VNC server for sharing :0 (xrdp VNC backend)
- tigervnc
# i3wm ecosystem
- i3-wm
- i3status
- i3lock
- polybar
- rofi
- dunst
- picom
- feh
- arandr
- lxappearance
```

Replace with:

```
# Wayland compositor
- hyprland
- waybar
- anyrun
- mako
- hyprpaper
- grim
- slurp
- swaylock
- wl-clipboard
- wlogout
- wdisplays
- nwg-look
- xdg-desktop-portal-hyprland
# GPU drivers and diagnostics (Intel / virtio / modesetting)
- mesa
- mesa-utils
```

- [ ] **Step 2: Remove xrdp from aur_packages**

Remove lines 112-114:
```
# xrdp remote desktop
# xrdp VNC backend connects to x0vncserver on :0, no xorgxrdp needed.
- xrdp
```

- [ ] **Step 3: Verify syntax with ansible-playbook --syntax-check**

```bash
ansible-playbook ansible/playbook.yml --syntax-check
```

Expected: no errors.

- [ ] **Step 4: Run lint**

```bash
bash tests/lint.sh
```

Expected: all checks pass.

- [ ] **Step 5: Commit**

```bash
git add ansible/roles/packages/defaults/main.yml
git commit -m "feat: swap X11/i3 packages for Wayland/Hyprland"
```

---

### Task 2: Remove xrdp Infrastructure

**Files:**
- Delete: `ansible/roles/packages/tasks/xrdp.yml`
- Delete: `ansible/roles/packages/templates/xrdp.ini.j2`
- Delete: `ansible/roles/packages/templates/x0vncserver.service.j2`
- Modify: `ansible/roles/packages/tasks/main.yml`
- Modify: `ansible/roles/packages/handlers/main.yml`

**Interfaces:**
- Consumes: nothing (xrdp is already removed from aur_packages in Task 1 so `paru -S --needed` won't install it; the include task is dead code)
- Produces: clean packages role without xrdp references

- [ ] **Step 1: Delete xrdp task and template files**

```bash
rm ansible/roles/packages/tasks/xrdp.yml
rm ansible/roles/packages/templates/xrdp.ini.j2
rm ansible/roles/packages/templates/x0vncserver.service.j2
```

- [ ] **Step 2: Remove xrdp include from tasks/main.yml**

Remove lines 27-30:
```
- name: Configure xrdp when xrdp_enabled is true
  ansible.builtin.include_tasks: xrdp.yml
  when: xrdp_enabled | default(false) | bool
  tags: [packages, xrdp]
```

- [ ] **Step 3: Remove xrdp handlers from handlers/main.yml**

Remove lines 13-48 (from `- name: Restart xrdp` through `XDG_RUNTIME_DIR: "/run/user/{{ _uid }}"`):
```
- name: Restart xrdp
  become: true
  ansible.builtin.systemd:
    name: xrdp.service
    state: restarted

- name: Reload user systemd
  become: true
  become_user: "{{ target_user }}"
  vars:
    _uid: "{{ lookup('pipe', 'id -u ' + target_user) | trim | int }}"
  ansible.builtin.systemd:
    scope: user
    daemon_reload: true
  register: packages_user_reload
  failed_when: false
  changed_when: packages_user_reload is success
  check_mode: false
  environment:
    XDG_RUNTIME_DIR: "/run/user/{{ _uid }}"

- name: Restart x0vncserver
  become: true
  become_user: "{{ target_user }}"
  vars:
    _uid: "{{ lookup('pipe', 'id -u ' + target_user) | trim | int }}"
  ansible.builtin.systemd:
    name: x0vncserver.service
    scope: user
    state: restarted
  register: packages_x0vnc_restart
  failed_when: false
  changed_when: packages_x0vnc_restart is success
  check_mode: false
  environment:
    XDG_RUNTIME_DIR: "/run/user/{{ _uid }}"
```

The file after removal should contain only `Regenerate initramfs` (lines 1-6) and `Reload systemd` (lines 8-11).

- [ ] **Step 4: Verify syntax**

```bash
ansible-playbook ansible/playbook.yml --syntax-check
```

Expected: no errors.

- [ ] **Step 5: Run lint**

```bash
bash tests/lint.sh
```

Expected: all checks pass.

- [ ] **Step 6: Commit**

```bash
git add ansible/roles/packages/tasks/xrdp.yml ansible/roles/packages/templates/xrdp.ini.j2 ansible/roles/packages/templates/x0vncserver.service.j2 ansible/roles/packages/tasks/main.yml ansible/roles/packages/handlers/main.yml
git commit -m "feat: remove xrdp remote desktop infrastructure"
```

---

### Task 3: Update Group Variables

**Files:**
- Modify: `ansible/group_vars/all.yml`

**Interfaces:**
- Consumes: nothing
- Produces: clean `all.yml` without xrdp reference

- [ ] **Step 1: Update autologin comment**

Change line 54 from:
```
# tty1 autologin → startx → i3 chain on :0.
# Must be true for xrdp VNC backend — x0vncserver shares :0 over VNC.
```
To:
```
# tty1 autologin → Hyprland (Wayland compositor).
```

- [ ] **Step 2: Remove xrdp_enabled variable**

Remove lines 58-62:
```
# xrdp remote desktop (VNC backend, shares :0 display).
# Set to true to enable xrdp (RDP) + x0vncserver (VNC sharing :0).
# xrdp-sesman is disabled; no separate X sessions.
# Package tigervnc provides x0vncserver; xrdp provides RDP listener.
xrdp_enabled: true
```

- [ ] **Step 3: Verify syntax**

```bash
ansible-playbook ansible/playbook.yml --syntax-check
```

Expected: no errors (no undefined variable references).

- [ ] **Step 4: Run lint**

```bash
bash tests/lint.sh
```

Expected: all checks pass.

- [ ] **Step 5: Run idempotency check**

```bash
bash tests/idempotency.sh
```

Expected: second run PLAY RECAP shows no `changed=[1-9]` tasks.

- [ ] **Step 6: Commit**

```bash
git add ansible/group_vars/all.yml
git commit -m "feat: update group_vars for Wayland/Hyprland, remove xrdp_enabled"
```
