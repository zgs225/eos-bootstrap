# xrdp Remote Desktop Design

**Date:** 2026-06-18
**Status:** design

## Purpose

Add xrdp (RDP server) with xorgxrdp backend to enable remote desktop access from other systems (Mac/Windows). The local i3 desktop on tty1 continues to work side-by-side; each RDP connection starts a new independent i3 session.

## Requirements

1. **Variable-gated**: `xrdp_enabled: false` in `group_vars/all.yml` controls whether xrdp is configured and its services are enabled.
2. **xorgxrdp backend**: Hardware-accelerated Xorg sessions via xrdp's xorgxrdp module.
3. **No display manager**: xrdp-sesman manages X sessions independently; no gdm/lightdm/sddm.
4. **New session per connection**: `Policy=UBDC` — each RDP connect starts a fresh i3 session; disconnect terminates it.
5. **Coexistence with local desktop**: xorgxrdp uses independent X displays (default `:10+`); tty1 autologin/startx/i3 chain is unaffected.
6. **Dotfiles integration**: The xrdp session startup script sources `.xprofile` (for fcitx5 env vars) and launches i3 via a zsh login shell so that `~/.zshrc` configs (mise, PATH, editor, etc.) are available in terminals opened from i3.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| `bool` gate (`xrdp_enabled`) not service list | Only 2 services (xrdp, xrdp-sesman), always enabled together — a list adds no flexibility |
| Task file in `packages` role, not new role | Follows existing patterns (bluetooth, sunshine, i915-sriov, cloud-init); minimal surface area |
| `startwm.sh` execs `zsh -l -c "exec i3"` | Ensures full login-shell environment (mise, PATH, etc.) in xrdp terminals without duplicating dotfiles logic |
| Service enabled in xrdp.yml directly | Same pattern as bluetooth.yml; does not pollute services/core_services.yml or optional_services |
| Port 3389 exposed, no firewall | Project explicitly has no firewall by design; security note in docs, no new firewall rules |
| AUR packages in `aur_packages.yml` | `xrdp` and `xorgxrdp` are AUR-only on Arch; packages install unconditionally (harmless), services are gated |

## Implementation Overview

### New Files

| File | Purpose |
|------|---------|
| `ansible/roles/packages/tasks/xrdp.yml` | Entry point: deploy configs + enable services, gated by `xrdp_enabled` |
| `ansible/roles/packages/templates/xrdp.ini.j2` | xrdp main config (port 3389, xorg backend) |
| `ansible/roles/packages/templates/sesman.ini.j2` | Session manager config (UBDC policy, Xorg backend config) |
| `ansible/roles/packages/templates/startwm.sh.j2` | Session startup: source `.xprofile`, set XDG vars, exec `zsh -l -c "exec i3"` |

### Modified Files

| File | Change |
|------|--------|
| `ansible/group_vars/all.yml` | Add `xrdp_enabled: false` |
| `ansible/roles/packages/defaults/main.yml` | Add `xrdp` and `xorgxrdp` to `aur_packages` list |
| `ansible/roles/packages/handlers/main.yml` | Add `Restart xrdp` handler |
| `ansible/roles/packages/tasks/main.yml` | Add `include_tasks: xrdp.yml` with `when: xrdp_enabled`, tags `[packages, xrdp]` |

### Configuration Templates

#### xrdp.ini.j2 — Key Sections

```ini
[Globals]
port=3389
crypt_level=high
certificate=
key_file=

[Xorg]
name=Xorg
lib=libxup.so
username=ask
password=ask
ip=127.0.0.1
port=-1
code=20
```

#### sesman.ini.j2 — Key Sections

```ini
[Globals]
ListenAddress=127.0.0.1
ListenPort=3350
MaxSessions=10
KillDisconnected=false
Policy=UBDC
AlwaysGroupCheck=false

[Sessions]
MaxSessions=10

[Xorg]
param=-config
param=xrdp/xorg.conf
param=-noreset
param=-nolisten
param=tcp
```

#### startwm.sh.j2 — Session Startup

```bash
#!/bin/sh
# xrdp session startup script for i3
# Managed by Ansible — do not edit by hand.

{% raw %}
if [ -r "$HOME/.xprofile" ]; then
    . "$HOME/.xprofile"
fi

export XDG_CURRENT_DESKTOP=i3
export XDG_SESSION_TYPE=x11

exec /usr/bin/zsh -l -c "exec i3"
{% endraw %}
```

### xrdp.yml Task File

```yaml
---
- name: Deploy xrdp configuration
  ansible.builtin.template:
    src: "{{ item.src }}"
    dest: "{{ item.dest }}"
    owner: root
    group: root
    mode: "{{ item.mode }}"
  loop:
    - { src: xrdp.ini.j2, dest: /etc/xrdp/xrdp.ini, mode: "0644" }
    - { src: sesman.ini.j2, dest: /etc/xrdp/sesman.ini, mode: "0644" }
    - { src: startwm.sh.j2, dest: /etc/xrdp/startwm.sh, mode: "0755" }
  notify: Restart xrdp

- name: Enable and start xrdp services
  ansible.builtin.systemd:
    name: "{{ item }}"
    enabled: true
    state: started
  loop:
    - xrdp.service
    - xrdp-sesman.service
```

### Handler

```yaml
# in packages/handlers/main.yml
- name: Restart xrdp
  ansible.builtin.systemd:
    name: "{{ item }}"
    state: restarted
  loop:
    - xrdp.service
    - xrdp-sesman.service
```

### Variable Gating in packages/tasks/main.yml

```yaml
- name: Configure xrdp when xrdp_enabled is true
  ansible.builtin.include_tasks: xrdp.yml
  when: xrdp_enabled | default(false) | bool
  tags: [packages, xrdp]
```

## Session Startup Flow

```
xrdp client connects (3389)
  → xrdp-sesman authenticates locally
  → xorgxrdp starts a new X server (display :10, :11, ...)
  → /etc/xrdp/startwm.sh runs as the authenticated user:
    1. source ~/.xprofile        (fcitx5: GTK_IM_MODULE, QT_IM_MODULE, XMODIFIERS, SDL_IM_MODULE)
    2. export XDG_CURRENT_DESKTOP=i3, XDG_SESSION_TYPE=x11
    3. exec zsh -l -c "exec i3"
       → zsh login shell loads: .zshenv → .zprofile (startx guard not triggered — DISPLAY is set)
       → .zshrc: p10k, functions, configs (mise, PATH, editor, etc.)
       → exec i3 replaces zsh
         → i3 autostarts: feh, picom, polybar, dunst, fcitx5 -d, sunshine
       → terminals opened via Mod+Enter run interactive zsh with full env
```

The local tty1 session is untouched — `startx` runs on `:0`, xorgxrdp on `:10+`.

## Testing

- **Manual**: Enable `xrdp_enabled: true` in `group_vars/all.yml`, run the playbook, connect with an RDP client to `<ip>:3389`, verify i3 starts with polybar/picom/fcitx5 working.
- **Idempotency**: Run `tests/idempotency.sh` — second playbook run must not produce `changed` tasks.
- **Coexistence**: Verify local tty1 i3 still works while an RDP session is active.

## Security Note

No firewall is installed by this project (by design). When `xrdp_enabled: true`, port 3389/TCP is exposed on all interfaces. The user is responsible for securing the network perimeter (e.g., VPN, host firewall, or SSH tunnel).
