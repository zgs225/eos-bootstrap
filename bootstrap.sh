#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="${REPO_ROOT}/ansible"
GROUP_VARS="${ANSIBLE_DIR}/group_vars/all.yml"

log() { printf '\033[1;34m[bootstrap]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[bootstrap]\033[0m %s\n' "$*" >&2; exit 1; }

command -v sudo >/dev/null 2>&1 || die "sudo is required"

setup_proxy() {
  local proxy_vars="HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY"
  local found=0
  for v in $proxy_vars; do
    if [[ -n "${!v:-}" ]]; then
      found=1
      break
    fi
  done
  if [[ $found -eq 0 ]]; then
    return
  fi

  for v in $proxy_vars; do
    if [[ -n "${!v:-}" ]]; then
      local lower="${v,,}"
      export "$lower"="${!v}"
      log "proxy: ${lower}=${!v}"
    fi
  done

  sudo() { command sudo -E "$@"; }
  log "proxy environment active (sudo -E enabled)"
}

setup_proxy

# Resolve DOTFILES_REPO and DOTFILES_BRANCH from group_vars/all.yml.
DOTFILES_REPO=""
DOTFILES_BRANCH=""
DOTFILES_USE_ENCRYPTION="false"
if [[ -f "${GROUP_VARS}" ]]; then
  DOTFILES_REPO="$(grep -E '^\s*dotfiles_repo:' "${GROUP_VARS}" \
    | sed -E 's/.*dotfiles_repo:\s*"?([^"]+)"?\s*/\1/')"
  DOTFILES_BRANCH="$(grep -E '^\s*dotfiles_branch:' "${GROUP_VARS}" \
    | sed -E 's/.*dotfiles_branch:\s*"?([^"]*)"?\s*/\1/')"
  raw_enc="$(grep -E '^\s*dotfiles_use_encryption:' "${GROUP_VARS}" \
    | sed -E 's/.*dotfiles_use_encryption:\s*"?([^"]*)"?\s*/\1/' \
    | tr '[:upper:]' '[:lower:]')"
  case "${raw_enc}" in
    true) DOTFILES_USE_ENCRYPTION="true" ;;
  esac
fi
if [[ -z "${DOTFILES_REPO}" ]]; then
  die "dotfiles_repo not set in ${GROUP_VARS}"
fi

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
  trap 'rm -rf "$tmp"' EXIT
  git clone https://aur.archlinux.org/paru.git "$tmp/paru"
  (cd "$tmp/paru" && makepkg -si --noconfirm)
  trap - EXIT
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
if [[ "${DOTFILES_USE_ENCRYPTION}" == "true" ]]; then
  key_ok=0
  if [[ -n "${AGE_KEY_FILE:-}" && -s "${AGE_KEY_FILE}" ]]; then
    key_ok=1
  elif [[ -s "${HOME}/.config/chezmoi/key.txt" ]]; then
    key_ok=1
  fi
  if [[ "${key_ok}" -ne 1 ]]; then
    die "dotfiles_use_encryption is true but no age identity found. Place your age private key at ${HOME}/.config/chezmoi/key.txt (or set \$AGE_KEY_FILE), then re-run ./bootstrap.sh"
  fi
  log "age identity present, continuing with dotfiles"
fi
if [[ -d "${HOME}/.local/share/chezmoi" ]]; then
  log "Dotfiles already initialized; running chezmoi update --init (pull + regen config + apply)"
  chezmoi update --init
else
  if [[ -n "${DOTFILES_BRANCH}" ]]; then
    log "Initializing dotfiles from ${DOTFILES_REPO} (branch: ${DOTFILES_BRANCH})"
    chezmoi init --apply --branch "${DOTFILES_BRANCH}" "${DOTFILES_REPO}"
  else
    log "Initializing dotfiles from ${DOTFILES_REPO}"
    chezmoi init --apply "${DOTFILES_REPO}"
  fi
fi

log "bootstrap complete"
