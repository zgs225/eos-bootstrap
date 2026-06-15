# AGENTS.md

## What this repo is

- `bootstrap.sh` chains: pacman (git/base-devel/ansible) → AUR (`paru`) → `ansible-playbook` → `chezmoi` → `chezmoi init --apply` (or `chezmoi update --init`). The `--init` flag on the `update` branch regenerates `~/.config/chezmoi/chezmoi.toml` from the dotfiles repo's `.chezmoi.<format>.tmpl` before applying, so re-running bootstrap picks up edits to that template. When `dotfiles_use_encryption: true`, it checks for an age identity at `~/.config/chezmoi/key.txt` (or `$AGE_KEY_FILE`) before invoking chezmoi and `die`s if missing. See `README.md` for the overview and `docs/runbook.md` for day-to-day edits.

## Two-repo model (load-bearing)

- **This repo** owns the *coarse* system layer: packages, systemd services, kernel tunables, NetworkManager connection profiles, user groups, sudoers, polkit.
- **Dotfiles repo** (separate, URL in `ansible/group_vars/all.yml::dotfiles_repo`, branch in `dotfiles_branch`) owns the *fine* user layer: `~/.config/**`, i3/polybar/rofi/dunst/picom configs, GTK themes, and `~/.config/mise/config.toml`.

Boundary rule — do not violate:
- Ansible never writes under `~`.
- `chezmoi` never installs packages or enables services.
- `bootstrap.sh` is the only place both sides are coordinated.

## Layout (entry points)

- `bootstrap.sh` — top-level entry; resolves `dotfiles_repo` / `dotfiles_branch` / `dotfiles_use_encryption` by **grepping `ansible/group_vars/all.yml`** (not via `ansible-inventory`). Keep those grep patterns stable.
- `ansible/playbook.yml` — single playbook, `hosts: localhost`, `become: true`. Role order is significant: `packages → mise → services → network → kernel → user → display`.
- `ansible/group_vars/all.yml` — the only place to set per-machine identity: `target_user`, `user_groups`, `optional_services`, `vm_services`, `dotfiles_repo`, `dotfiles_branch`, `dotfiles_use_encryption`.
- `ansible/roles/services/vars/core_services.yml` — hardcoded, code-review required. `optional_services` (in `group_vars`) is the free-form list.
- `ansible/roles/packages/vars/pacman_packages.yml` and `aur_packages.yml` — package lists. AUR is installed via `paru` with `become_user: target_user` and `PARU=1`; requires `paru` to already be on PATH (installed by `bootstrap.sh` step 2, not by Ansible).
- `ansible/roles/network/files/nmconnection/*.nmconnection` — drop-in: any file here is `copy`-deployed to `/etc/NetworkManager/system-connections/` as `root:root 0600` and triggers a NetworkManager reload. `.gitkeep` is intentionally excluded by the glob.
- `ansible/roles/user/files/polkit/{*.rules,*.pkla}` — same drop-in pattern to `/etc/polkit-1/rules.d/`.
- `ansible/roles/kernel/templates/sysctl.d.conf.j2` — sysctl tunables (file-max, inotify, swappiness, BBR). Handler `Apply sysctl` runs `sysctl --system`.
- `ansible/roles/kernel/defaults/main.yml::kernel_modules` — append module names here; rendered to `/etc/modules-load.d/eos.conf`.
- `ansible/roles/packages/tasks/bluetooth.yml` — auto-detects bluetooth via `lspci -k` / `lsusb` and conditionally installs `bluez` + `bluez-utils` and enables `bluetooth.service`. No manual gate.
- `ansible/roles/display/tasks/autologin.yml` — creates a systemd drop-in at `/etc/systemd/system/getty@tty1.service.d/autologin.conf` to auto-login `target_user` on tty1 (VM autologin → startx → i3 chain). Defaults `display_autologin_tty: tty1`.

## Commands

```bash
# Full bootstrap (asks for sudo, idempotent end-to-end)
./bootstrap.sh

# Re-apply Ansible only
ansible-playbook ansible/playbook.yml --ask-become-pass

# Re-apply dotfiles only
chezmoi update --init

# Lint (ansible-lint, yamllint, shellcheck)
tests/lint.sh

# Idempotency check — runs playbook twice, fails if second run has changed=[1-9] in PLAY RECAP
tests/idempotency.sh
```

## Conventions

- Bash: `set -euo pipefail`; `log`/`die` helpers; colors via ANSI escapes.
- Ansible: localhost only, `forks=4`, `host_key_checking=False`, `pipelining=True` (`ansible/ansible.cfg`). `community.general >= 8.0.0` is required (`ansible/requirements.yml`).
- All roles tag tasks (e.g., `tags: [packages, pacman]`) so individual steps can be run with `--tags`.
- The `aur` task uses `changed_when: false` and `check_mode: false` — its idempotency is enforced by `paru --needed`, not by Ansible's change detection.
- The `bluetooth` task uses `failed_when: rc not in [0, 1]` — detection must not error when hardware is absent.
- The `sudoers` drop validates with `visudo -cf %s` before writing.

## Gotchas an agent would otherwise miss

- **`dotfiles_repo` must be set** in `ansible/group_vars/all.yml` before `./bootstrap.sh` runs; the script dies with `dotfiles_repo not set` otherwise. SSH URLs (e.g., `git@github.com:...`) are fine and are the default.
- **`dotfiles_use_encryption` requires a pre-placed age identity.** When `true`, `bootstrap.sh` checks for `~/.config/chezmoi/key.txt` (or `$AGE_KEY_FILE`) before invoking chezmoi. The `age` package is installed by the `packages` role. The encryption config (`[encryption.age] recipient`) lives in the dotfiles repo's `.chezmoi/chezmoi.toml`. Do not add identity-fetching logic to `bootstrap.sh` — key placement is manual by design.
- **`vm_services` gates service enablement only.** `cloud-init` and `qemu-guest-agent` packages always install via `pacman_packages.yml`; they're harmless on bare metal (no-op without a virtio serial channel / datasource). Set `vm_services` to the standard Proxmox set (5 units) only on VM guests.
- **Mise tool versions live in the dotfiles repo**, not here. `ansible/roles/mise/tasks/main.yml` only installs the `mise` binary; `mise install` runs from a `run_once_after_*` script in the dotfiles repo.
- **`chezmoi update` alone does not regenerate `chezmoi.toml`.** The dotfiles repo's `.chezmoi.<format>.tmpl` is only re-rendered when `update --init` (or a fresh `init --apply`) runs. Plain `chezmoi update` does `git pull` + `apply` but leaves the existing config file untouched. `bootstrap.sh` uses `update --init` for that reason; if you ever invoke chezmoi by hand, prefer `chezmoi update --init` (or `chezmoi apply --init` after pulling) so template edits take effect.
- **First run is not 100% Ansible-managed**: `paru` is bootstrapped by bash (no Ansible module for building it). The guard `if ! command -v paru` keeps re-runs safe.
- **Single-machine scope is intentional.** No inventory generalization, no multi-host support — adding a second machine is explicitly out of scope per the design spec.
- **`tests/idempotency.sh` greps the PLAY RECAP** for `changed=[1-9]`, not the task list. New roles must not produce `changed=` tasks on a steady-state re-run; if a task is inherently non-idempotent, add a `creates:`/`removes:` guard or use `changed_when: false`.
- **No firewall (`ufw`) is installed or configured** by design. Don't add it without a spec change.
- **`user_groups` is appended**, not replaced (`append: true` in `groups.yml`) — adding a new group won't drop existing memberships.
- The dotfiles repo is expected to be writable via the user's normal SSH key; the bootstrap script does not configure `~/.ssh/config` — that's the dotfiles repo's job.
- **Display chain needs dotfiles-repo coordination.** The `display` role only installs Xorg packages and configures agetty autologin on tty1. The rest of the chain is in the dotfiles repo: `~/.xinitrc` must exec i3, and `~/.zprofile` must conditionally run `startx` on tty1 (`[ -z "${DISPLAY}" ] && [ "${XDG_VTNR}" -eq 1 ] && exec startx`). These are user-level files, so they belong in chezmoi, not this repo.
