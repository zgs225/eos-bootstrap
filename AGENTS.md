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
- `ansible/roles/packages/tasks/keyd.yml` + `ansible/roles/packages/templates/keyd/default.conf.j2` — system-wide keyd remapping (`/etc/keyd/default.conf`). `keyd.service` is enabled via `core_services`. Per-application overrides (`~/.config/keyd/app.conf`) and the i3 autostart line live in the dotfiles repo — boundary rule applies.
- `ansible/roles/display/tasks/autologin.yml` — creates a systemd drop-in at `/etc/systemd/system/getty@tty1.service.d/autologin.conf` to auto-login `target_user` on tty1 (VM autologin → startx → i3 chain). Defaults `display_autologin_tty: tty1`.
- `ansible/roles/display/tasks/touchpad.yml` + `templates/touchpad-natural-scroll.conf.j2` — deploys `/etc/X11/xorg.conf.d/40-touchpad-natural-scroll.conf`, an InputClass that enables macOS-style natural scrolling (`Option "NaturalScrolling" "on"`) for all touchpads. Gated by `display_touchpad_natural_scroll` (default `true`); set `false` to remove the drop-in.

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
- **Display chain needs dotfiles-repo coordination.** The `display` role installs Xorg packages, configures agetty autologin on tty1, and deploys the touchpad natural-scrolling Xorg drop-in. The rest of the chain is in the dotfiles repo: `~/.xinitrc` must exec i3, and `~/.zprofile` must conditionally run `startx` on tty1 (`[ -z "${DISPLAY}" ] && [ "${XDG_VTNR}" -eq 1 ] && exec startx`). These are user-level files, so they belong in chezmoi, not this repo.
- **Touchpad natural scrolling is an Xorg InputClass, not a runtime `xinput set-prop`.** The drop-in in `/etc/X11/xorg.conf.d/40-touchpad-natural-scroll.conf` is re-applied by Xorg on every device add, so it survives suspend/resume hotplug — the failure mode of the old dotfiles-repo `~/.config/i3/scripts/natural-scroll` (`exec_always` + `xinput set-prop`), which reset to the libinput default after the touchpad was re-enumerated and only re-ran on i3 reload. That i3 script and its `exec_always` line are now redundant and should be removed from the dotfiles repo. The drop-in only takes effect on the next X server start/login, not the running session.
- **`keyd.service` requires `target_user` in the `keyd` group** to access `/run/keyd.socket` for `keyd-application-mapper`. The group is added via `user_groups` in `group_vars/all.yml`, but the new membership only takes effect after the user logs out and back in (or runs `newgrp keyd`). The mapper will silently fail to apply per-app overrides until then.
- **keyd config hot-reload uses `keyd reload`, not `systemctl reload`.** The upstream `keyd.service` has no `ExecReload=`, so `Reload keyd` handler invokes the binary's IPC reload subcommand. The handler accepts rc 0/1 to tolerate the rare "daemon not yet up" race on first deploy.
- **i3 `$mod = Alt` collides with app Alt-shortcuts.** Apps use Alt heavily (Alt+F4, Alt+Tab, Alt+Enter in Firefox menu accelerators, etc.). Because keyd rebinds Alt+c/v/x/a to Ctrl+c/v/x/a via the `alt` layer, expect to whitelist more apps in `~/.config/keyd/app.conf` over time. Check `~/.config/keyd/app.log` for the matched WM_CLASS strings.
- **Right-Alt loses AltGr semantics.** The keyd template explicitly rebinds `rightalt = layer(alt)` which overrides the upstream default of `layer(altgr)`. Right-Alt international character entry (e.g. `AltGr+E` for `€` on European layouts) no longer works. Acceptable because CJK input goes through fcitx5; if you switch to a European layout later, change the rightalt line to `layer(altgr)` in `default.conf.j2`.

## Proxy support

- When bootstrapping behind a restrictive network, set standard proxy env vars before running `./bootstrap.sh`:
  ```bash
  export HTTP_PROXY=http://10.0.0.1:7890
  export HTTPS_PROXY=http://10.0.0.1:7890
  export ALL_PROXY=socks5://10.0.0.1:1080
  ./bootstrap.sh
  ```
- Supported variables: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY` (uppercase only; `bootstrap.sh` exports lowercase equivalents internally).
- `ALL_PROXY` with `socks5://` scheme works for curl/pacman (see ArchWiki: Proxy server).
- No `group_vars` changes needed — proxy is runtime-only, not machine identity.
- `setup_proxy()` in `bootstrap.sh` also overrides `sudo` to `sudo -E` so proxy vars survive into privileged commands.
- Ansible receives proxy vars via a play-level `environment` block (see `ansible/playbook.yml`), ensuring `become: true` tasks also use the proxy.
