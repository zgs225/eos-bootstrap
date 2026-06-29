# Bootstrap Proxy Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add temporary proxy support to `bootstrap.sh` and `ansible/playbook.yml` so all network operations (pacman, git, paru, chezmoi) can route through HTTP or SOCKS5 proxies via standard environment variables.

**Architecture:** `bootstrap.sh` gains a `setup_proxy()` function that detects proxy env vars, exports lowercase equivalents, and overrides `sudo` to use `sudo -E`. `playbook.yml` gains a play-level `environment` block to pass proxy vars through Ansible's `become`. No `group_vars` changes; proxy is runtime-only.

**Tech Stack:** Bash (bootstrap.sh), Ansible (playbook.yml), shellcheck (lint)

## Global Constraints

- Bash: `set -euo pipefail`; `log`/`die` helpers; colors via ANSI escapes.
- Ansible: localhost only, `forks=4`, `host_key_checking=False`, `pipelining=True`.
- All lints must pass: `tests/lint.sh` (ansible-lint, yamllint, shellcheck).
- No `group_vars` changes — proxy is temporary, not machine identity.
- No sudoers modification — `sudo -E` via shell function override is sufficient.
- Fully backward compatible — no behavior change when proxy env vars are absent.

---

### Task 1: Add `setup_proxy()` function to `bootstrap.sh`

**Files:**
- Modify: `bootstrap.sh:11` (after `command -v sudo` check, before step 1)

**Interfaces:**
- Consumes: `log()` helper already defined in `bootstrap.sh`
- Produces: `setup_proxy` function; lowercase proxy env vars (`http_proxy`, `https_proxy`, `all_proxy`, `no_proxy`) exported when uppercase versions are present; `sudo` shell function override using `sudo -E`

- [ ] **Step 1: Add the `setup_proxy()` function definition**

Insert after line 11 (`command -v sudo >/dev/null 2>&1 || die "sudo is required"`), before the `# Resolve DOTFILES_REPO` block:

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

- [ ] **Step 2: Add the `setup_proxy` call**

Insert immediately after the `command -v sudo` check (line 11), before the `# Resolve DOTFILES_REPO` block:

```bash
setup_proxy
```

- [ ] **Step 3: Run shellcheck to verify**

Run: `shellcheck bootstrap.sh`
Expected: PASS (no errors or warnings)

- [ ] **Step 4: Commit**

```bash
git add bootstrap.sh
git commit -m "feat: add setup_proxy() for temporary proxy support"
```

---

### Task 2: Add play-level `environment` block to `playbook.yml`

**Files:**
- Modify: `ansible/playbook.yml`

**Interfaces:**
- Consumes: `http_proxy`, `https_proxy`, `all_proxy`, `no_proxy` env vars (exported by `setup_proxy` in Task 1)
- Produces: Proxy env vars available to all Ansible tasks including `become: true`

- [ ] **Step 1: Add `environment` block to the play**

Modify `ansible/playbook.yml` to add the `environment` key after `gather_facts: true`:

```yaml
---
- name: Bootstrap EndeavourOS i3wm workstation
  hosts: localhost
  become: true
  gather_facts: true
  environment:
    http_proxy: "{{ lookup('env', 'http_proxy') }}"
    https_proxy: "{{ lookup('env', 'https_proxy') }}"
    all_proxy: "{{ lookup('env', 'all_proxy') }}"
    no_proxy: "{{ lookup('env', 'no_proxy') }}"

  roles:
    - role: packages
    - role: mise
    - role: services
    - role: network
    - role: kernel
    - role: user
    - role: display
```

- [ ] **Step 2: Run yamllint and ansible-lint**

Run: `yamllint ansible/ && ansible-lint ansible/`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ansible/playbook.yml
git commit -m "feat: add proxy environment to ansible playbook"
```

---

### Task 3: Document proxy support in `AGENTS.md`

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: Design spec at `docs/superpowers/specs/2026-06-29-bootstrap-proxy-design.md`
- Produces: Documented proxy usage in AGENTS.md for future agents

- [ ] **Step 1: Add "Proxy support" section to AGENTS.md**

Insert a new section after "## Gotchas an agent would otherwise miss" (before the last line of the file):

```markdown

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
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: document proxy support in AGENTS.md"
```

---

### Task 4: Run full lint suite and verify

**Files:**
- None (verification only)

- [ ] **Step 1: Run the full lint suite**

Run: `tests/lint.sh`
Expected: All lints pass (ansible-lint, yamllint, shellcheck)

- [ ] **Step 2: Verify no behavior change without proxy vars**

Run: `shellcheck bootstrap.sh`
Expected: PASS, no warnings about `setup_proxy` or `sudo` function override
