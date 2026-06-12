# eos-bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an idempotent Ansible-based bootstrap for an EndeavourOS i3wm developer workstation, with chezmoi handling dotfiles and `mise` handling language toolchains.

**Architecture:** Two-repo model. `eos-bootstrap` (this repo) provides `bootstrap.sh` and an Ansible tree. The Ansible roles install system packages, configure NetworkManager, enable services, set sysctl, manage user groups, and detect-install bluetooth. A pre-existing dotfiles repo (managed separately by `chezmoi`) provides all user-level configuration. `bootstrap.sh` orchestrates the full sequence: install Ansible + paru → run playbook → install chezmoi → apply dotfiles (which runs `mise install` via `run_once_after`).

**Tech Stack:** Bash (bootstrap.sh), Ansible (system provisioning), pacman + paru (packages), systemd, NetworkManager, chezmoi (dotfiles), mise (language toolchains).

**Working directory for all tasks:** `/Users/yuez/Workspace/Misc/eos-bootstrap`

**Reference spec:** `docs/superpowers/specs/2026-06-12-eos-bootstrap-design.md`

---

## File Structure

| Path | Responsibility |
|------|----------------|
| `bootstrap.sh` | Entry point: install Ansible/paru/chezmoi, run playbook, apply dotfiles |
| `.gitignore` | Ignore Ansible retry files, `*.pyc`, editor cruft |
| `ansible/ansible.cfg` | Ansible config: localhost inventory, roles path, become defaults |
| `ansible/requirements.yml` | Community collections: `community.general` |
| `ansible/inventory/localhost.yml` | Single-host inventory |
| `ansible/playbook.yml` | Top-level playbook: invokes all 6 roles in order |
| `ansible/group_vars/all.yml` | Coarse layer variables: `target_user`, `user_groups`, `optional_services`, `dotfiles_repo` |
| `ansible/roles/packages/defaults/main.yml` | Package role defaults (currently empty) |
| `ansible/roles/packages/vars/pacman_packages.yml` | Initial pacman package list |
| `ansible/roles/packages/vars/aur_packages.yml` | Initial AUR package list |
| `ansible/roles/packages/tasks/main.yml` | Orchestrates pacman, aur, bluetooth sub-tasks |
| `ansible/roles/packages/tasks/pacman.yml` | Install pacman packages via `community.general.pacman` |
| `ansible/roles/packages/tasks/aur.yml` | Install AUR packages via `paru` (uses `creates:` for idempotency) |
| `ansible/roles/packages/tasks/bluetooth.yml` | Hardware-detect, install `bluez` and `bluez-utils`, enable service |
| `ansible/roles/mise/tasks/main.yml` | Install `mise` via pacman |
| `ansible/roles/mise/handlers/main.yml` | Placeholder for future handlers |
| `ansible/roles/network/defaults/main.yml` | Network role defaults |
| `ansible/roles/network/files/nmconnection/.gitkeep` | Drop directory; users add `.nmconnection` files |
| `ansible/roles/network/tasks/main.yml` | Copy `*.nmconnection` files, reload NetworkManager |
| `ansible/roles/services/vars/core_services.yml` | Hardcoded `core_services` list (code-reviewed) |
| `ansible/roles/services/defaults/main.yml` | `optional_services: []` |
| `ansible/roles/services/tasks/main.yml` | Enable+start `core_services` and `optional_services` |
| `ansible/roles/kernel/defaults/main.yml` | Kernel role defaults |
| `ansible/roles/kernel/tasks/sysctl.yml` | Template sysctl fragment and apply via `ansible.builtin.sysctl` |
| `ansible/roles/kernel/tasks/modules.yml` | Template modules-load fragment |
| `ansible/roles/kernel/templates/sysctl.d.conf.j2` | Sysctl settings |
| `ansible/roles/kernel/templates/modules-load.d.conf.j2` | Kernel modules to load at boot |
| `ansible/roles/user/defaults/main.yml` | `user_groups: []` |
| `ansible/roles/user/tasks/groups.yml` | Add target_user to `user_groups` |
| `ansible/roles/user/tasks/sudoers.yml` | Drop sudoers fragment (NOPASSWD for wheel) |
| `ansible/roles/user/tasks/polkit.yml` | Drop polkit rules |
| `ansible/roles/user/files/polkit/.gitkeep` | Drop directory for polkit rule files |
| `tests/lint.sh` | Run `ansible-lint`, `yamllint`, `shellcheck` |
| `tests/idempotency.sh` | Run playbook twice, verify no changes second time |
| `docs/runbook.md` | Day-to-day usage: how to add packages, services, run lint, etc. |
| `README.md` | Project overview, quickstart, link to spec/plan |

---

## Task 1: Repository scaffolding

**Files:**
- Create: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: Create `.gitignore`**

```
# Ansible
*.retry
.ansible/
roles/*/.ansible/

# Python
__pycache__/
*.pyc

# Editor
.vscode/
.idea/
*.swp
*.swo
.DS_Store

# Local override
.envrc
```

- [ ] **Step 2: Create `README.md`**

```markdown
# eos-bootstrap

Idempotent bootstrap for an EndeavourOS i3wm developer workstation.

## Quickstart

```bash
git clone <this-repo> ~/Projects/eos-bootstrap
cd ~/Projects/eos-bootstrap
./bootstrap.sh
```

## What it does

1. Installs `ansible` and `paru` (skip if already present).
2. Runs the Ansible playbook in `ansible/` (packages, services, kernel, user, network).
3. Installs `chezmoi` and applies the dotfiles repo.
4. The dotfiles repo handles `mise` tool installs via `run_once_after`.

## Architecture

Two-repo model:

- **This repo** — coarse layer: system packages, services, kernel, NetworkManager, user groups.
- **Dotfiles repo** (separate) — fine layer: all dotfiles, i3 ecosystem, themes, `mise` config.

See [docs/superpowers/specs/2026-06-12-eos-bootstrap-design.md](docs/superpowers/specs/2026-06-12-eos-bootstrap-design.md) for the full design.

## Day-to-day

- Add a package: edit `ansible/roles/packages/vars/pacman_packages.yml` (or `aur_packages.yml`) and run `./bootstrap.sh`.
- Add a service: edit `ansible/roles/services/vars/core_services.yml` and run `./bootstrap.sh`.
- Add a dotfile: edit in the dotfiles repo, then `chezmoi apply`.
```

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/eos-bootstrap
git add README.md .gitignore
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "chore: add README and gitignore"
```

---

## Task 2: Bootstrap script

**Files:**
- Create: `bootstrap.sh`

- [ ] **Step 1: Create `bootstrap.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="${REPO_ROOT}/ansible"
DOTFILES_REPO="$(ansible-inventory -i "${ANSIBLE_DIR}/inventory" --export all.yml 2>/dev/null \
  | grep '^DOTFILES_REPO' | cut -d= -f2- | tr -d '"' || true)"

# Fallback: parse group_vars/all.yml directly if ansible-inventory not available yet
if [[ -z "${DOTFILES_REPO:-}" ]]; then
  DOTFILES_REPO="$(grep -E '^\s*dotfiles_repo:' "${ANSIBLE_DIR}/group_vars/all.yml" \
    | sed -E 's/.*dotfiles_repo:\s*"?([^"]+)"?\s*/\1/')"
fi

log() { printf '\033[1;34m[bootstrap]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[bootstrap]\033[0m %s\n' "$*" >&2; exit 1; }

command -v sudo >/dev/null 2>&1 || die "sudo is required"

# ---------- 1. Base packages via pacman ----------
log "Ensuring base packages (git, base-devel, ansible)"
for pkg in git base-devel ansible; do
  if ! pacman -Qq "$pkg" &>/dev/null; then
    sudo pacman -S --needed --noconfirm "$pkg"
  fi
done

# ---------- 2. AUR helper (paru) ----------
if ! command -v paru >/dev/null 2>&1; then
  log "Installing paru from AUR"
  tmp="$(mktemp -d)"
  git clone https://aur.archlinux.org/paru.git "$tmp/paru"
  (cd "$tmp/paru" && makepkg -si --noconfirm)
  rm -rf "$tmp"
else
  log "paru already installed"
fi

# ---------- 3. Ansible playbook ----------
log "Running Ansible playbook"
ansible-playbook "${ANSIBLE_DIR}/playbook.yml" --ask-become-pass

# ---------- 4. Install chezmoi ----------
if ! command -v chezmoi >/dev/null 2>&1; then
  log "Installing chezmoi"
  if pacman -Si chezmoi &>/dev/null; then
    sudo pacman -S --needed --noconfirm chezmoi
  else
    paru -S --needed --noconfirm chezmoi
  fi
else
  log "chezmoi already installed"
fi

# ---------- 5. Apply dotfiles ----------
if [[ -z "${DOTFILES_REPO}" ]]; then
  die "DOTFILES_REPO not set in ansible/group_vars/all.yml"
fi

if [[ -d "${HOME}/.local/share/chezmoi" ]]; then
  log "Dotfiles already initialized; running chezmoi apply"
  chezmoi apply
else
  log "Initializing dotfiles from ${DOTFILES_REPO}"
  chezmoi init --apply "${DOTFILES_REPO}"
fi

log "bootstrap complete"
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x bootstrap.sh
git add bootstrap.sh
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "feat: add bootstrap.sh"
```

---

## Task 3: Ansible configuration and inventory

**Files:**
- Create: `ansible/ansible.cfg`
- Create: `ansible/requirements.yml`
- Create: `ansible/inventory/localhost.yml`

- [ ] **Step 1: Create `ansible/ansible.cfg`**

```ini
[defaults]
inventory = inventory
roles_path = roles
host_key_checking = False
retry_files_enabled = False
stdout_callback = yaml
forks = 4

[ssh_connection]
pipelining = True
```

- [ ] **Step 2: Create `ansible/inventory/localhost.yml`**

```yaml
all:
  hosts:
    localhost:
      ansible_connection: local
      ansible_python_interpreter: /usr/bin/python3
```

- [ ] **Step 3: Create `ansible/requirements.yml`**

```yaml
collections:
  - name: community.general
    version: ">=8.0.0"
```

- [ ] **Step 4: Install collections and commit**

```bash
ansible-galaxy collection install -r ansible/requirements.yml
git add ansible/ansible.cfg ansible/requirements.yml ansible/inventory/localhost.yml
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "chore: add ansible config and inventory"
```

---

## Task 4: Top-level playbook and group_vars

**Files:**
- Create: `ansible/playbook.yml`
- Create: `ansible/group_vars/all.yml`

- [ ] **Step 1: Create `ansible/group_vars/all.yml`**

```yaml
---
# Coarse-layer variables. Edits here are part of the machine's identity.

# The user this machine is being bootstrapped for.
target_user: "{{ ansible_user_id }}"

# User groups target_user should be added to.
user_groups:
  - wheel
  - docker
  - input
  - video
  - network
  - audio

# Services to enable in addition to core_services. Empty by default.
optional_services: []

# URL of the dotfiles repo (consumed by bootstrap.sh, not by Ansible).
dotfiles_repo: "git@github.com:you/dotfiles.git"
```

- [ ] **Step 2: Create `ansible/playbook.yml`**

```yaml
---
- name: Bootstrap EndeavourOS i3wm workstation
  hosts: localhost
  become: true
  gather_facts: true

  roles:
    - role: packages
    - role: mise
    - role: network
    - role: services
    - role: kernel
    - role: user
```

- [ ] **Step 3: Commit**

```bash
git add ansible/playbook.yml ansible/group_vars/all.yml
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "feat: add top-level playbook and group_vars"
```

---

## Task 5: packages role — structure and pacman sub-task

**Files:**
- Create: `ansible/roles/packages/defaults/main.yml`
- Create: `ansible/roles/packages/vars/pacman_packages.yml`
- Create: `ansible/roles/packages/tasks/main.yml`
- Create: `ansible/roles/packages/tasks/pacman.yml`

- [ ] **Step 1: Create `ansible/roles/packages/defaults/main.yml`**

```yaml
---
# Defaults for the packages role.
```

- [ ] **Step 2: Create `ansible/roles/packages/vars/pacman_packages.yml`**

```yaml
---
# Packages installed from the official Arch / EndeavourOS repositories.
# Grouped by purpose; remove a line to uninstall.
pacman_packages:
  # Base
  - sudo
  - vim
  - curl
  - wget
  - jq
  - unzip
  - zip
  - tree
  - htop
  # Networking
  - networkmanager
  - nm-connection-editor
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
  # Theming
  - gtk3
  - gtk4
  - papirus-icon-theme
  - noto-fonts
  - noto-fonts-emoji
  - ttf-dejavu
  # Development
  - git
  - base-devel
  - openssh
  - rsync
  - ripgrep
  - fd
  - fzf
  - bat
  - eza
  # Shell
  - zsh
  - zsh-completions
  - zsh-syntax-highlighting
  # Editors
  - neovim
  # Terminal
  - wezterm
  - tmux
  # Mise prerequisites
  - mise
```

- [ ] **Step 3: Create `ansible/roles/packages/tasks/pacman.yml`**

```yaml
---
- name: Install pacman packages
  community.general.pacman:
    name: "{{ pacman_packages }}"
    state: present
    update_cache: true
```

- [ ] **Step 4: Create `ansible/roles/packages/tasks/main.yml`**

```yaml
---
- name: Install official packages
  ansible.builtin.include_tasks: pacman.yml
  tags: [packages, pacman]

- name: Install AUR packages
  ansible.builtin.include_tasks: aur.yml
  tags: [packages, aur]

- name: Conditionally install bluetooth
  ansible.builtin.include_tasks: bluetooth.yml
  tags: [packages, bluetooth]
```

- [ ] **Step 5: Commit**

```bash
git add ansible/roles/packages/
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "feat(packages): add pacman sub-task and initial list"
```

---

## Task 6: packages role — AUR sub-task

**Files:**
- Create: `ansible/roles/packages/vars/aur_packages.yml`
- Create: `ansible/roles/packages/tasks/aur.yml`

- [ ] **Step 1: Create `ansible/roles/packages/vars/aur_packages.yml`**

```yaml
---
# Packages installed from the AUR via paru.
aur_packages: []
  # Add AUR packages here, e.g.:
  # - google-chrome
```

- [ ] **Step 2: Create `ansible/roles/packages/tasks/aur.yml`**

```yaml
---
- name: Install AUR packages via paru
  become: true
  become_user: "{{ target_user }}"
  environment:
    PARU: "1"
  command:
    cmd: "paru -S --needed --noconfirm {{ aur_packages | join(' ') }}"
  when: aur_packages | length > 0
  changed_when: false
  register: aur_install
  failed_when: aur_install.rc != 0 and 'already installed' not in aur_install.stderr
```

> **Note on idempotency:** `paru -S` is not declarative. The `failed_when` handles the case where `pacman` says the package is already installed even when `paru` exits non-zero. For long-term maintenance, consider switching to `kewlfft.aur` from the `kewlfft/aur` collection; deferred until a real need arises.

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/packages/
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "feat(packages): add AUR sub-task"
```

---

## Task 7: packages role — bluetooth conditional

**Files:**
- Create: `ansible/roles/packages/tasks/bluetooth.yml`

- [ ] **Step 1: Create `ansible/roles/packages/tasks/bluetooth.yml`**

```yaml
---
- name: Detect bluetooth hardware via lspci/lsusb
  ansible.builtin.shell: |
    set -o pipefail
    lspci -k 2>/dev/null | grep -qi 'bluetooth' \
      || lsusb 2>/dev/null | grep -qi 'bluetooth'
  register: bt_hw_check
  changed_when: false
  failed_when: false
  check_mode: false

- name: Install bluez packages (bluetooth hardware detected)
  when: bt_hw_check.rc == 0
  become: true
  community.general.pacman:
    name:
      - bluez
      - bluez-utils
    state: present

- name: Enable and start bluetooth.service (bluetooth hardware detected)
  when: bt_hw_check.rc == 0
  become: true
  ansible.builtin.systemd:
    name: bluetooth.service
    enabled: true
    state: started
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/packages/tasks/bluetooth.yml
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "feat(packages): add conditional bluetooth installation"
```

---

## Task 8: mise role

**Files:**
- Create: `ansible/roles/mise/tasks/main.yml`
- Create: `ansible/roles/mise/handlers/main.yml`

- [ ] **Step 1: Create `ansible/roles/mise/tasks/main.yml`**

```yaml
---
- name: Install mise via pacman
  community.general.pacman:
    name: mise
    state: present
    update_cache: true

# Note: Tool versions are NOT installed here. They are declared in
# ~/.config/mise/config.toml (managed by chezmoi), and `mise install`
# runs from a `run_once_after_*` script in the dotfiles repo.
```

- [ ] **Step 2: Create `ansible/roles/mise/handlers/main.yml`**

```yaml
---
# Reserved for future handlers (e.g., a notify hook for mise activation).
```

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/mise/
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "feat(mise): install mise binary"
```

---

## Task 9: network role

**Files:**
- Create: `ansible/roles/network/defaults/main.yml`
- Create: `ansible/roles/network/files/nmconnection/.gitkeep`
- Create: `ansible/roles/network/tasks/main.yml`

- [ ] **Step 1: Create empty file `ansible/roles/network/files/nmconnection/.gitkeep`**

```bash
touch ansible/roles/network/files/nmconnection/.gitkeep
```

- [ ] **Step 2: Create `ansible/roles/network/defaults/main.yml`**

```yaml
---
# Network role defaults.
# Add .nmconnection files to files/nmconnection/ to have them deployed.
```

- [ ] **Step 3: Create `ansible/roles/network/tasks/main.yml`**

```yaml
---
- name: Ensure /etc/NetworkManager/system-connections exists
  ansible.builtin.file:
    path: /etc/NetworkManager/system-connections
    state: directory
    owner: root
    group: root
    mode: "0700"

- name: Deploy NetworkManager connection profiles
  ansible.builtin.copy:
    src: "{{ item }}"
    dest: "/etc/NetworkManager/system-connections/{{ item | basename }}"
    owner: root
    group: root
    mode: "0600"
  with_fileglob:
    - "nmconnection/*"
  notify: Reload NetworkManager
  loop_control:
    label: "{{ item | basename }}"
```

- [ ] **Step 4: Add a reload handler in `ansible/roles/network/handlers/main.yml`** (create the file)

```yaml
---
- name: Reload NetworkManager
  ansible.builtin.command:
    cmd: nmcli connection reload
  become: true
  changed_when: true
```

- [ ] **Step 5: Commit**

```bash
git add ansible/roles/network/
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "feat(network): deploy NetworkManager connection profiles"
```

---

## Task 10: services role

**Files:**
- Create: `ansible/roles/services/vars/core_services.yml`
- Create: `ansible/roles/services/defaults/main.yml`
- Create: `ansible/roles/services/tasks/main.yml`

- [ ] **Step 1: Create `ansible/roles/services/vars/core_services.yml`**

```yaml
---
# Services every machine of this type runs. Changes require code review.
# Bluetooth is intentionally NOT here — it is enabled conditionally by
# roles/packages/tasks/bluetooth.yml based on hardware detection.
core_services:
  - NetworkManager.service
  - docker.service
  - fstrim.timer
  - sshd.service
```

- [ ] **Step 2: Create `ansible/roles/services/defaults/main.yml`**

```yaml
---
# Optional services to enable in addition to core_services.
optional_services: []
```

- [ ] **Step 3: Create `ansible/roles/services/tasks/main.yml`**

```yaml
---
- name: Combine core and optional services
  ansible.builtin.set_fact:
    all_services: "{{ core_services + optional_services }}"

- name: Enable and start services
  ansible.builtin.systemd:
    name: "{{ item }}"
    enabled: true
    state: started
  loop: "{{ all_services }}"
  loop_control:
    label: "{{ item }}"
```

- [ ] **Step 4: Commit**

```bash
git add ansible/roles/services/
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "feat(services): enable core_services and optional_services"
```

---

## Task 11: kernel role

**Files:**
- Create: `ansible/roles/kernel/defaults/main.yml`
- Create: `ansible/roles/kernel/tasks/sysctl.yml`
- Create: `ansible/roles/kernel/tasks/modules.yml`
- Create: `ansible/roles/kernel/tasks/main.yml`
- Create: `ansible/roles/kernel/templates/sysctl.d.conf.j2`
- Create: `ansible/roles/kernel/templates/modules-load.d.conf.j2`

- [ ] **Step 1: Create `ansible/roles/kernel/defaults/main.yml`**

```yaml
---
# Kernel tunables. Edit sysctl.d.conf.j2 for sysctl, and add module
# names to kernel_modules for modules-load.
sysctl_path: /etc/sysctl.d/99-eos.conf
modules_load_path: /etc/modules-load.d/eos.conf
kernel_modules: []
```

- [ ] **Step 2: Create `ansible/roles/kernel/templates/sysctl.d.conf.j2`**

```
# Managed by Ansible — do not edit by hand.
# Kernel tunables for an i3wm developer workstation.

# File descriptor limits
fs.file-max = 2097152

# Inotify watchers (neovim, wezterm, file watchers)
fs.inotify.max_user_watches = 524288

# Better desktop responsiveness under memory pressure
vm.swappiness = 10

# Network tuning
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
```

- [ ] **Step 3: Create `ansible/roles/kernel/templates/modules-load.d.conf.j2`**

```
# Managed by Ansible — do not edit by hand.
# Kernel modules to load at boot.
{% for mod in kernel_modules %}
{{ mod }}
{% endfor %}
```

- [ ] **Step 4: Create `ansible/roles/kernel/tasks/sysctl.yml`**

```yaml
---
- name: Deploy sysctl fragment
  ansible.builtin.template:
    src: sysctl.d.conf.j2
    dest: "{{ sysctl_path }}"
    owner: root
    group: root
    mode: "0644"
  notify: Apply sysctl

- name: Apply sysctl settings
  ansible.builtin.command:
    cmd: "sysctl -p {{ sysctl_path }}"
  become: true
  register: sysctl_apply
  changed_when: "'Applying' in sysctl_apply.stdout or sysctl_apply.rc == 0"
```

- [ ] **Step 5: Create `ansible/roles/kernel/tasks/modules.yml`**

```yaml
---
- name: Deploy modules-load fragment
  ansible.builtin.template:
    src: modules-load.d.conf.j2
    dest: "{{ modules_load_path }}"
    owner: root
    group: root
    mode: "0644"
  notify: Load kernel modules
```

- [ ] **Step 6: Create `ansible/roles/kernel/tasks/main.yml`**

```yaml
---
- name: Configure sysctl
  ansible.builtin.include_tasks: sysctl.yml
  tags: [kernel, sysctl]

- name: Configure modules-load
  ansible.builtin.include_tasks: modules.yml
  tags: [kernel, modules]
```

- [ ] **Step 7: Create `ansible/roles/kernel/handlers/main.yml`**

```yaml
---
- name: Apply sysctl
  ansible.builtin.command:
    cmd: "sysctl --system"
  become: true
  changed_when: false

- name: Load kernel modules
  ansible.builtin.command:
    cmd: "systemctl restart systemd-modules-load.service"
  become: true
  changed_when: false
```

- [ ] **Step 8: Commit**

```bash
git add ansible/roles/kernel/
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "feat(kernel): add sysctl and modules-load templates"
```

---

## Task 12: user role

**Files:**
- Create: `ansible/roles/user/defaults/main.yml`
- Create: `ansible/roles/user/tasks/main.yml`
- Create: `ansible/roles/user/tasks/groups.yml`
- Create: `ansible/roles/user/tasks/sudoers.yml`
- Create: `ansible/roles/user/tasks/polkit.yml`
- Create: `ansible/roles/user/files/polkit/.gitkeep`

- [ ] **Step 1: Create empty file `ansible/roles/user/files/polkit/.gitkeep`**

```bash
touch ansible/roles/user/files/polkit/.gitkeep
```

- [ ] **Step 2: Create `ansible/roles/user/defaults/main.yml`**

```yaml
---
# User role defaults.
# Edit user_groups in group_vars/all.yml, not here.
```

- [ ] **Step 3: Create `ansible/roles/user/tasks/groups.yml`**

```yaml
---
- name: Ensure target_user exists
  ansible.builtin.user:
    name: "{{ target_user }}"
    state: present
    shell: /usr/bin/zsh
    groups: "{{ user_groups }}"
    append: true
```

- [ ] **Step 4: Create `ansible/roles/user/tasks/sudoers.yml`**

```yaml
---
- name: Deploy wheel sudoers NOPASSWD fragment
  ansible.builtin.copy:
    dest: /etc/sudoers.d/10-wheel-nopasswd
    content: |
      # Managed by Ansible — do not edit by hand.
      %wheel ALL=(ALL:ALL) NOPASSWD: ALL
    owner: root
    group: root
    mode: "0440"
    validate: "visudo -cf %s"
```

- [ ] **Step 5: Create `ansible/roles/user/tasks/polkit.yml`**

```yaml
---
- name: Ensure /etc/polkit-1/rules.d exists
  ansible.builtin.file:
    path: /etc/polkit-1/rules.d
    state: directory
    owner: root
    group: root
    mode: "0755"

- name: Deploy polkit rules
  ansible.builtin.copy:
    src: "{{ item }}"
    dest: "/etc/polkit-1/rules.d/{{ item | basename }}"
    owner: root
    group: root
    mode: "0644"
  with_fileglob:
    - "polkit/*"
  loop_control:
    label: "{{ item | basename }}"
```

- [ ] **Step 6: Create `ansible/roles/user/tasks/main.yml`**

```yaml
---
- name: Configure user groups
  ansible.builtin.include_tasks: groups.yml
  tags: [user, groups]

- name: Configure sudoers
  ansible.builtin.include_tasks: sudoers.yml
  tags: [user, sudoers]

- name: Configure polkit
  ansible.builtin.include_tasks: polkit.yml
  tags: [user, polkit]
```

- [ ] **Step 7: Commit**

```bash
git add ansible/roles/user/
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "feat(user): manage groups, sudoers, polkit"
```

---

## Task 13: Test scripts

**Files:**
- Create: `tests/lint.sh`
- Create: `tests/idempotency.sh`

- [ ] **Step 1: Create `tests/lint.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "==> ansible-lint"
ansible-lint ansible/

echo "==> yamllint"
yamllint ansible/

echo "==> shellcheck bootstrap.sh"
shellcheck bootstrap.sh

echo "==> all lints passed"
```

- [ ] **Step 2: Create `tests/idempotency.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PLAYBOOK="ansible/playbook.yml"
LIMIT="${LIMIT:-localhost}"

echo "==> first run"
ansible-playbook "${PLAYBOOK}" --limit "${LIMIT}" --diff > /tmp/run1.log 2>&1 \
  || { tail -50 /tmp/run1.log; exit 1; }

echo "==> second run"
ansible-playbook "${PLAYBOOK}" --limit "${LIMIT}" --diff > /tmp/run2.log 2>&1 \
  || { tail -50 /tmp/run2.log; exit 1; }

echo "==> checking for changes on second run"
if grep -E "^\s*changed:.*localhost" /tmp/run2.log; then
  echo "ERROR: second run produced changes — playbook is not idempotent"
  grep -B 2 -A 5 "changed:" /tmp/run2.log
  exit 1
fi

echo "==> idempotency verified"
```

- [ ] **Step 3: Make executable and commit**

```bash
chmod +x tests/lint.sh tests/idempotency.sh
git add tests/
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "test: add lint and idempotency scripts"
```

---

## Task 14: Runbook

**Files:**
- Create: `docs/runbook.md`

- [ ] **Step 1: Create `docs/runbook.md`**

````markdown
# eos-bootstrap Runbook

Day-to-day operations for this bootstrap.

## Add a package

Pacman:

```yaml
# ansible/roles/packages/vars/pacman_packages.yml
pacman_packages:
  - <new-package>
```

Then re-run:

```bash
./bootstrap.sh
```

AUR:

```yaml
# ansible/roles/packages/vars/aur_packages.yml
aur_packages:
  - <new-aur-package>
```

## Add a core service

```yaml
# ansible/roles/services/vars/core_services.yml
core_services:
  - <service>.service
```

Then `./bootstrap.sh`. (Service additions go through code review because this file is hardcoded.)

## Add an optional service

```yaml
# ansible/group_vars/all.yml
optional_services:
  - <service>.service
```

## Add a NetworkManager connection

Drop a `.nmconnection` file into `ansible/roles/network/files/nmconnection/`. Permissions are forced to `0600` (root) at deploy time.

## Add a kernel tunable

Edit `ansible/roles/kernel/templates/sysctl.d.conf.j2`. The handler `Apply sysctl` re-applies on change.

## Add a kernel module

Edit `ansible/roles/kernel/defaults/main.yml`:

```yaml
kernel_modules:
  - <module-name>
```

## Add a user group

```yaml
# ansible/group_vars/all.yml
user_groups:
  - <group-name>
```

## Add a polkit rule

Drop a `.rules` file into `ansible/roles/user/files/polkit/`.

## Lint

```bash
tests/lint.sh
```

## Idempotency check

```bash
tests/idempotency.sh
```

## Re-apply dotfiles only

```bash
chezmoi apply
```

## Re-apply Ansible only

```bash
ansible-playbook ansible/playbook.yml --ask-become-pass
```

## Update mise tool versions

Edit `~/.config/mise/config.toml` in the dotfiles repo, then `chezmoi apply` triggers `run_once_after_*` which runs `mise install`.

## Smoke test (fresh VM)

1. Boot EndeavourOS installer, install base system.
2. Install git: `sudo pacman -S git`.
3. `git clone <this-repo> && cd eos-bootstrap`.
4. `./bootstrap.sh`.
5. Verify: `systemctl is-active NetworkManager docker`, `i3` starts at login, `mise list` shows go/python/node/rust.
````

- [ ] **Step 2: Commit**

```bash
git add docs/runbook.md
git -c user.email=bootstrap@local -c user.name=bootstrap commit -m "docs: add runbook"
```

---

## Self-Review

**1. Spec coverage:**

- Two-repo architecture with bootstrap.sh → Spec §Architecture, Tasks 1-4 ✓
- Ansible roles: packages, mise, network, services, kernel, user → Spec §Components, Tasks 5-12 ✓
- Bluetooth conditional install → Spec §Components, Task 7 ✓
- `core_services` hardcoded, `optional_services` variable → Spec §Data Model, Task 10 ✓
- `group_vars/all.yml` with target_user, user_groups, optional_services, dotfiles_repo → Spec §Data Model, Task 4 ✓
- `sysctl.d` and `modules-load.d` templates → Spec §Components, Task 11 ✓
- Idempotency tested by `tests/idempotency.sh` → Spec §Testing, Task 13 ✓
- Lint via `tests/lint.sh` → Spec §Testing, Task 13 ✓
- Runbook in `docs/runbook.md` → Spec §Testing, Task 14 ✓
- Dotfiles repo migration is out of scope (lives in dotfiles repo, deferred) — Spec §Migration Plan notes "implementation plan, not this design spec"

**2. Placeholder scan:** No "TBD", "TODO", "fill in", or vague instructions. All code blocks contain complete content.

**3. Type / variable consistency:** Verified.
- `core_services` defined in Task 10, consumed in same task ✓
- `optional_services` defined in Task 4 (`group_vars/all.yml`), consumed in Task 10 ✓
- `user_groups` defined in Task 4, consumed in Task 12 ✓
- `aur_packages` defined in Task 6, consumed in same task ✓
- `kernel_modules` referenced in template (Task 11) — needs to be defined in `defaults/main.yml`. Adding to Task 11 Step 1 below.

**Fix:** Add `kernel_modules: []` to kernel defaults.
