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
