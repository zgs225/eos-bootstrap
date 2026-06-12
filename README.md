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
2. Runs the Ansible playbook in `ansible/` (packages, mise, network, services, kernel, user).
3. Installs `chezmoi` and applies the dotfiles repo (set `dotfiles_branch` in `group_vars/all.yml` to clone a non-default branch on first init; set `dotfiles_use_encryption: true` to require an age identity for encrypted dotfiles).
4. The dotfiles repo handles `mise` tool installs via `run_once_after`.

## Architecture

Two-repo model:

- **This repo** — coarse layer: system packages, services, kernel, NetworkManager, user groups.
- **Dotfiles repo** (separate) — fine layer: all dotfiles, i3 ecosystem, themes, `mise` config.

See [docs/superpowers/specs/2026-06-12-eos-bootstrap-design.md](docs/superpowers/specs/2026-06-12-eos-bootstrap-design.md) for the full design.

## Day-to-day

- Add a package: edit `ansible/roles/packages/defaults/main.yml` and run `./bootstrap.sh`.
- Add a service: edit `ansible/roles/services/vars/core_services.yml` and run `./bootstrap.sh`.
- Add a dotfile: edit in the dotfiles repo, then `chezmoi update`.
