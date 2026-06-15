# eos-bootstrap Design

**Date:** 2026-06-12
**Status:** Draft

## Purpose

A single-machine, idempotent bootstrap for an EndeavourOS developer workstation using i3wm. From a fresh install (or any drift state) running one command yields the same fully-configured system. The system targets a personal development workstation covering backend, frontend/web, ops/scripting, and (optionally) low-level/embedded work.

## Scope

**In scope:**

- One physical machine, one user, fresh EndeavourOS install
- System-level provisioning: packages, services, kernel parameters, user permissions, NetworkManager connections
- Window manager: i3 + polybar + rofi + dunst + picom (modern i3 ecosystem)
- Language toolchains (go, python, node, rust) managed by `mise`
- Dotfile management for all user-level configuration via `chezmoi`

**Out of scope:**

- Multi-host / multi-user support (single machine only)
- Firewall provisioning (ufw is intentionally not installed or configured)
- Desktop GUI applications (browser, IM, IDE) — not enumerated in this spec; add later as needed by extending the package lists
- Secrets management beyond what `chezmoi`'s encrypted files provide
- Containerized workflows (distrobox, devcontainers) — not enumerated
- macOS / non-Arch targets

## Architecture Overview

Two independent repositories combined by a single bootstrap script:

1. **`eos-bootstrap`** (this repo) — Ansible manages the "coarse" layer: package installation, system services, kernel parameters, NetworkManager, user groups, sudoers.
2. **dotfiles** (separate, pre-existing) — `chezmoi` manages the "fine" layer: every dotfile under `~`, including the i3wm ecosystem, themes, agent config, and `mise` tool version declarations.

**Execution flow (idempotent end-to-end):**

```
bootstrap.sh
  1. pacman: install git, base-devel, ansible (--needed)
  2. install paru from AUR (skip if present)
  3. ansible-playbook ansible/playbook.yml
  4. install chezmoi (pacman or AUR)
  5. chezmoi init --apply <dotfiles-repo>
     ├── applies all dotfiles
     └── runs `run_once_after_*` scripts (e.g., `mise install`)
```

**Boundary rule:**

- Ansible never writes files under `~` of a user.
- `chezmoi` never installs system packages or enables systemd services.
- The only place both are coordinated is `bootstrap.sh`.

## Components

### `bootstrap.sh`

Single entry point. Bash, `set -euo pipefail`. Performs the five steps above. Safe to run repeatedly — each step checks for prior state.

### Ansible side (`ansible/`)

**`playbook.yml`** — single playbook, runs all roles in order:

1. `packages` — pacman + AUR + conditional hardware packages (bluetooth)
2. `mise` — install `mise` package, declare tools
3. `network` — deploy NetworkManager connection profiles
4. `services` — enable core systemd services
5. `kernel` — sysctl + modules-load
6. `user` — group membership, sudoers, polkit rules

**Roles:**

| Role | Purpose | Idempotency |
|------|---------|-------------|
| `packages` | Install `pacman` and AUR packages, hardware-conditional installs | `community.general.pacman` with `state: present`; AUR via `paru` with `--needed` |
| `mise` | Install the `mise` binary via pacman; tool versions are NOT installed here | pacman is idempotent; tool installation is deferred to chezmoi's `run_once_after_*` |
| `network` | Drop `*.nmconnection` files into `/etc/NetworkManager/system-connections/`; reload NM | `copy` + `nmcli connection reload` |
| `services` | `systemctl enable --now` for `core_services` list | `ansible.builtin.systemd` module |
| `kernel` | Template `/etc/sysctl.d/99-eos.conf` and `/etc/modules-load.d/eos.conf` | `template` + `ansible.builtin.sysctl` |
| `user` | Add user to groups; drop sudoers fragment; drop polkit rules | `ansible.builtin.user` (groups), `copy` for sudoers/polkit |

### `chezmoi` side (dotfiles repo, owned separately)

Pre-existing repo currently managed by `rcup`. This spec requires migrating it to `chezmoi` (rename files with `dot_` prefix, etc.). The dotfiles repo is responsible for:

- All `~/.*` and `~/.config/**` files
- `i3`, `polybar`, `rofi`, `dunst`, `picom` configs
- GTK theme files (`~/.config/gtk-3.0/`, `~/.config/gtk-4.0/`), `~/.Xresources`
- `~/.ssh/config` (chezmoi template with `{{ .chezmoi.hostname }}` branches if needed)
- `~/.config/mise/config.toml` declaring go, python, node, rust versions
- `~/.config/environment.d/` for agent / desktop env vars
- A `run_once_after_*.sh` script that runs `mise install` after dotfiles are first applied

## Data Model

### `group_vars/all.yml` (coarse layer — Ansible variables)

```yaml
target_user: "{{ ansible_facts['user_id'] }}"

# Optional services (extra to core_services); empty by default
optional_services: []

# User groups to add target_user to
user_groups:
  - wheel
  - docker
  - input
  - video
  - network
  - audio

# Dotfiles repo URL — used by bootstrap.sh (not by Ansible)
dotfiles_repo: "git@github.com:you/dotfiles.git"
```

### `roles/services/vars/core_services.yml` (hardcoded, code-reviewed)

```yaml
# Services every machine of this type runs. Changes require code review.
core_services:
  - NetworkManager.service
  - docker.service
  - fstrim.timer
  - sshd.service
# Note: bluetooth.service is NOT here — it is conditionally enabled
# by roles/packages/tasks/bluetooth.yml based on hardware detection.
```

Loaded via `ansible.builtin.include_vars: core_services.yml` at the top of `roles/services/tasks/main.yml`. This is required because the file is not named `main.yml` and therefore not auto-loaded from `vars/`. Placing the list in `defaults/` would conflict with the spec's "hardcoded, code-reviewed, not overridable" intent (defaults are the lowest-precedence layer and are meant to be overridable). The `include_vars` approach preserves the hardcoded semantic while making the variable visible to role tasks.

### `roles/packages/vars/pacman_packages.yml` and `aur_packages.yml`

**Renamed/moved to `roles/packages/defaults/main.yml`.**

The original spec placed the package lists in `roles/packages/vars/` as `pacman_packages.yml` and `aur_packages.yml`. Implementation revealed that Ansible only auto-loads `vars/main.yml` from a role, not sibling files in `vars/`. The original layout caused `'pacman_packages' is undefined` errors at runtime.

The fix: move the lists to `roles/packages/defaults/main.yml` with `pacman_packages` and `aur_packages` as top-level keys. `role defaults/` is auto-loaded. The lists may be overridden by `group_vars/all.yml` or `--extra-vars`, which is consistent with the spec's earlier statement that GUI app packages and other opt-in selections are variable-driven.

### `roles/packages/tasks/bluetooth.yml` (conditional)

Hardware detection via `lspci -k` and `lsusb`, looking for the substring `bluetooth`. If detected, install `bluez` and `bluez-utils` and enable `bluetooth.service`. If not detected, skip silently.

## Data Flow

**Fresh install path:**

```
user runs bootstrap.sh
  → pacman installs git, base-devel, ansible
  → paru cloned and built
  → ansible-playbook runs roles
      → packages role installs OS packages
      → bluetooth role checks hardware; installs bluez iff found
      → mise role installs mise binary
      → network role drops nmconnection files
      → services role enables core_services
      → kernel role writes sysctl and modules-load
      → user role adds user to groups
  → chezmoi installed
  → chezmoi init applies dotfiles
      → mise config.toml triggers mise install (run_once)
```

**Drift-recovery path (re-running bootstrap):**

- pacman `--needed` skips installed packages
- paru `--needed` skips installed AUR packages
- Ansible re-runs are no-ops unless state changed
- `chezmoi init --apply` does NOT re-clone or pull when the source dir already exists, but it DOES regenerate the config from `.chezmoi.<format>.tmpl` and re-apply. For subsequent runs `chezmoi update --init` is the canonical command — it pulls remote changes, regenerates config from the template, and applies in one step.

**Day-to-day update path:**

- Add a package: edit `roles/packages/defaults/main.yml`, run `ansible-playbook`
- Add a service: edit `core_services.yml`, run `ansible-playbook`
- Change a dotfile: edit in dotfiles repo, `chezmoi apply`

## Error Handling

- `bootstrap.sh` uses `set -euo pipefail`; any unhandled step aborts immediately.
- Ansible roles fail loudly: `failed_when: true` is the default; no swallowed errors.
- `paru` build failure: clear error message, manual intervention required (network/AUR outage).
- Hardware detection: `failed_when: false` on the `lspci/lsusb` check; outcome is a boolean, not an error.
- Idempotency script (`tests/idempotency.sh`) runs the playbook twice and diffs `ansible-playbook --check --diff` output — non-empty diff is a failure.

## Testing

- **`tests/lint.sh`** — runs `ansible-lint`, `shellcheck` on `bootstrap.sh`, `yamllint`.
- **`tests/idempotency.sh`** — runs the playbook twice; expects no `changed=` tasks on the second run.
- **Manual smoke test** — documented in `docs/runbook.md`: fresh VM, run `bootstrap.sh`, verify i3 starts, services running, `mise list` shows installed tools.

## Repository Layout

```
eos-bootstrap/
├── README.md
├── bootstrap.sh
├── .gitignore
│
├── ansible/
│   ├── ansible.cfg
│   ├── requirements.yml
│   ├── inventory/
│   │   └── localhost.yml
│   ├── playbook.yml
│   ├── group_vars/
│   │   └── all.yml
│   └── roles/
│       ├── packages/
│       │   ├── defaults/main.yml    # pacman_packages, aur_packages
│       │   └── tasks/
│       │       ├── main.yml
│       │       ├── pacman.yml
│       │       ├── aur.yml
│       │       ├── bluetooth.yml
│       │       └── cloud_init.yml
│       ├── mise/
│       │   ├── tasks/main.yml
│       │   └── handlers/main.yml
│       ├── network/
│       │   ├── defaults/main.yml
│       │   ├── files/nmconnection/
│       │   └── tasks/main.yml
│       ├── services/
│       │   ├── vars/core_services.yml
│       │   ├── defaults/main.yml
│       │   └── tasks/main.yml
│       ├── kernel/
│       │   ├── defaults/main.yml
│       │   ├── tasks/
│       │   │   ├── sysctl.yml
│       │   │   └── modules.yml
│       │   └── templates/
│       │       ├── sysctl.d.conf.j2
│       │       └── modules-load.d.conf.j2
│       └── user/
│           ├── defaults/main.yml
│           ├── tasks/
│           │   ├── groups.yml
│           │   ├── sudoers.yml
│           │   └── polkit.yml
│           └── files/polkit/
│
├── tests/
│   ├── lint.sh
│   └── idempotency.sh
│
└── docs/
    ├── runbook.md
    └── superpowers/
        └── specs/
            └── 2026-06-12-eos-bootstrap-design.md
```

## Migration Plan (dotfiles repo)

The existing dotfiles repo uses `rcup`. To migrate to `chezmoi`:

1. In the dotfiles repo, rename files with the `dot_` prefix convention chezmoi uses.
2. Replace any `rcup`-specific symlinking logic with `chezmoi` templates or `run_once` scripts.
3. Add `dot_config/mise/config.toml` with current tool versions.
4. Add a `run_once_after_install-mise-tools.sh` that runs `mise install`.
5. Add i3 ecosystem files (`dot_config/i3/`, `dot_config/polybar/`, `dot_config/rofi/`, `dot_config/dunst/`, `dot_config/picom/`) as part of the dotfiles repo.
6. Add theme files (`dot_config/gtk-3.0/`, `dot_config/gtk-4.0/`, `dot_Xresources`).

Detailed migration steps belong in an implementation plan, not this design spec.

## Risks and Trade-offs

- **Single machine scope** — no inventory generalization. A second machine would need a new repo or refactor. Accepted because of stated single-machine goal.
- **No firewall** — relies on network perimeter or local policy. Accepted per user direction.
- **No desktop GUI enumeration** — leaving the `desktop_gui_packages` variable as a placeholder. A real workstation will want some, but listing them was deferred.
- **Tool versions in dotfiles** — moving the machine to a new tool version requires a dotfiles commit, not an Ansible change. This is intentional (developer machine, not infrastructure), but means a dotfiles-only update is needed for version bumps.
- **paru bootstrap is bash, not Ansible** — the bootstrap script must do `makepkg` for paru, since paru is needed for AUR roles. This means the first run is not 100% Ansible-managed, but it is still idempotent (`if command -v paru` guard).
- **Ansible is in pacman, not AUR** — `community/ansible` is in the official Arch repos, so we don't need AUR for Ansible itself, simplifying the bootstrap ordering.

## Out-of-Scope Follow-ups

These were considered and explicitly deferred:

- Distrobox / devcontainers for isolated dev environments
- Container runtimes beyond docker (podman, nerdctl)
- Hardened kernel / secure boot config
- Backup tooling (snapper, restic)
- Secrets in `chezmoi`'s age-encrypted format (the existing dotfiles repo may already do this; verify during implementation)
