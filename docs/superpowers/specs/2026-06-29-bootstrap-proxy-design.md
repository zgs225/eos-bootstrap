# Bootstrap Proxy Support Design

## Problem

In some network environments, all outbound HTTP/HTTPS/SOCKS traffic must go through a proxy server. The bootstrap process (pacman, git clone AUR, paru, ansible-playbook, chezmoi) currently has no way to route through a proxy, making it impossible to bootstrap a machine behind a restrictive network.

## Goal

Allow users to temporarily configure HTTP and SOCKS5 proxies for the entire bootstrap pipeline by setting standard environment variables before running `bootstrap.sh`. No permanent configuration changes; no impact when proxy variables are absent.

## Design Decisions

- **Environment variables only** — no command-line flags, no `group_vars` entries. Proxy is temporary, not part of machine identity.
- **Uppercase input, both cases exported** — users set `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`; bootstrap.sh also exports lowercase equivalents (`http_proxy` etc.) for tools that only check those.
- **`sudo -E`** via shell function override — simplest way to pass proxy variables through sudo without modifying sudoers.
- **Ansible play-level `environment`** — Ansible's `become` (sudo) does not inherit env vars; play-level `environment` block with `lookup('env', ...)` makes proxy available to all tasks including `become: true`.

## Changes

### 1. `bootstrap.sh` — `setup_proxy()` function

Insert after the `command -v sudo` check, before step 1:

```bash
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
```

Behavior:
- If no proxy env vars are set, `setup_proxy` returns immediately — zero overhead.
- Exports lowercase equivalents so both `HTTP_PROXY` and `http_proxy` are available.
- Overrides `sudo` as a shell function that calls `command sudo -E`, preserving all environment variables through sudo. Acceptable in a bootstrap context; not a multi-user production environment.
- Logs each active proxy variable for debugging.

### 2. `bootstrap.sh` — call `setup_proxy`

Insert `setup_proxy` call after `command -v sudo` check:

```bash
command -v sudo >/dev/null 2>&1 || die "sudo is required"
setup_proxy
```

### 3. `ansible/playbook.yml` — play-level `environment` block

Add to the play definition:

```yaml
environment:
  http_proxy: "{{ lookup('env', 'http_proxy') }}"
  https_proxy: "{{ lookup('env', 'https_proxy') }}"
  all_proxy: "{{ lookup('env', 'all_proxy') }}"
  no_proxy: "{{ lookup('env', 'no_proxy') }}"
```

This ensures all tasks (including `become: true` tasks like pacman and paru) receive proxy variables. When the env vars are empty, `lookup('env', ...)` returns an empty string, which has no effect.

### 4. `AGENTS.md` — documentation

Add a "Proxy support" section noting:
- How to use: `export HTTP_PROXY=... ALL_PROXY=... && ./bootstrap.sh`
- Supported variables: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`
- `ALL_PROXY` with `socks5://` scheme works for curl/pacman
- No `group_vars` changes needed; proxy is runtime-only

## Out of Scope

- No `--proxy` CLI flags (env vars are sufficient and standard).
- No `group_vars/all.yml` proxy settings (proxy is temporary, not machine identity).
- No sudoers modification (function-based `sudo -E` is adequate for bootstrap).
- No SOCKS5-to-HTTP protocol conversion (user provides correct scheme in each variable).
- No persistent proxy configuration (e.g., `/etc/environment` or `/etc/profile.d/proxy.sh`).

## User Experience

```bash
# With proxy
export HTTP_PROXY=http://10.0.0.1:7890
export HTTPS_PROXY=http://10.0.0.1:7890
export ALL_PROXY=socks5://10.0.0.1:1080
./bootstrap.sh

# Without proxy (unchanged)
./bootstrap.sh
```

Fully backward compatible — no behavior change when proxy variables are absent.

## Coverage Matrix

| Step | Tool | Proxy mechanism |
|------|------|----------------|
| 1. pacman | curl (via pacman) | `http_proxy` / `all_proxy` (Ansible `environment` block) |
| 2. git clone AUR | git | `http_proxy` / `https_proxy` (inherited from bash env) |
| 2. makepkg | pacman/curl | `http_proxy` / `all_proxy` (via `sudo -E`) |
| 3. Ansible pacman | curl (via pacman) | `http_proxy` / `all_proxy` (Ansible `environment` block) |
| 3. Ansible paru | paru | `http_proxy` / `all_proxy` (Ansible `environment` block) |
| 4. pacman/paru (chezmoi) | curl/paru | `http_proxy` / `all_proxy` (via `sudo -E`) |
| 5. chezmoi init/update | git (via chezmoi) | `http_proxy` / `https_proxy` (inherited from bash env) |
