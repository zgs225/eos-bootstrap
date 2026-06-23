# xrdp VNC Backend Design

## Problem

Current xrdp setup uses `xorgxrdp` backend which spawns independent X displays starting at `:10`. Software running in these sessions cannot access the Intel GPU (no VAAPI, Vulkan, OpenCL), breaking GPU-accelerated applications (wezterm, Chrome, etc.).

## Goal

Route xrdp RDP sessions through a VNC layer into the existing `:0` display (i3wm on Intel GPU), so all applications get native GPU acceleration. No remote GPU encoding is needed.

## Architecture

```
Mac RDP Client → xrdp :3389 → libvnc.so → x0vncserver :5900(localhost) → :0 (i3wm, Intel GPU)
                                                                             ↓
                                                                       Sunshine (game streaming)
```

- `:0` runs permanently via tty1 autologin → startx → i3
- `x0vncserver` (tigervnc) shares `:0` on `127.0.0.1:5900`, no encryption, no auth
- xrdp's VNC module (`libvnc.so`) connects to localhost VNC, wraps in RDP protocol
- `xrdp-sesman` is NOT used — no session lifecycle needed for a permanent display
- Sunshine coexists independently, both targeting `:0`

## Changes

### 1. Package lists (`ansible/roles/packages/defaults/main.yml`)

| Action | Package | List |
|--------|---------|------|
| Remove | `xorgxrdp` | `aur_packages` |
| Add | `tigervnc` | `pacman_packages` |
| Keep | `xrdp` | `aur_packages` |

### 2. Group vars (`ansible/group_vars/all.yml`)

- `display_autologin_enabled: false` → `true`
- `xrdp_enabled` stays `true`

### 3. xrdp configuration

**`xrdp.ini` template** — replace `[Xorg]` section with:
```ini
[VNC]
name=VNC
lib=libvnc.so
ip=127.0.0.1
port=5900
username=na
password=ask
```

Keep `[Globals]`, `[Logging]`, `[Channels]` sections as-is.

**Drop-in for `xrdp.service`** — clear `BindsTo=xrdp-sesman.service`:
- Path: `/etc/systemd/system/xrdp.service.d/unbind-sesman.conf`
- Content:
```ini
[Unit]
BindsTo=
```
- Setting `BindsTo=` to empty in a drop-in clears the directive inherited from the packaged unit.
- Task also runs `systemctl daemon-reload` after deploying.

**Templates no longer deployed** (files won't be written, harmless if leftover from prior runs):
- `sesman.ini` — sesman is stopped, config is irrelevant
- `startwm.sh` — no new WM sessions spawned (i3 already on `:0`)
- `Xwrapper.config` — xorgxrdp-specific; not needed for VNC backend

### 4. xrdp-sesman

- `xrdp-sesman.service`: **disable + stop** (unit file stays, package owns it)
- `xrdp.service`: **enable + start** (with cleared BindsTo)

### 5. x0vncserver systemd user service

New template: `ansible/roles/packages/templates/x0vncserver.service.j2`

Deployed to: `/home/{{ target_user }}/.config/systemd/user/x0vncserver.service`

```ini
[Unit]
Description=x0vncserver — share :0 via VNC
After=graphical-session.target
BindsTo=graphical-session.target

[Service]
ExecStart=/usr/bin/x0vncserver -display :0 -rfbport 5900 -localhost -SecurityTypes None
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
```

`-localhost` restricts to 127.0.0.1. If the tigervnc build lacks this flag, fallback to `-interface 127.0.0.1`. Either way, only local xrdp can reach the VNC port.

Deployed via `become: true` + `become_user: "{{ target_user }}"`, enabled with `systemctl --user enable --now`.

### 6. xrdp tasks (`ansible/roles/packages/tasks/xrdp.yml`)

Rewritten to:
- Deploy `xrdp.ini` template (VNC section)
- Deploy `xrdp.service` drop-in (unbind sesman)
- Enable `xrdp.service`, disable `xrdp-sesman.service`
- Deploy `x0vncserver.service` user unit
- Enable `x0vncserver.service` (user)
- Remove old files: `sesman.ini`, `startwm.sh`, `Xwrapper.config`

### 7. Unchanged

- `i915-sriov` tasks and kernel module config
- `sunshine` tasks and LizardByte repo
- `display` role (autologin reactivates via `display_autologin_enabled: true`)
- `services` role (no xrdp units in core_services)
- `network`, `kernel`, `user`, `mise` roles
- Handlers

## Idempotency

- `paru -S --needed xrdp`: idempotent (already installed)
- Template deployment: idempotent (content match)
- `systemctl enable/disable`: idempotent
- x0vncserver user service: idempotent
- Old file cleanup: `state: absent` with existing guard

## Testing

- `tests/lint.sh` — ansible-lint, yamllint, shellcheck
- `tests/idempotency.sh` — two-pass playbook, confirm zero `changed=` tasks on second run
- Manual: verify `DISPLAY=:0 glxinfo | grep "OpenGL renderer"` shows Intel GPU
- Manual: verify RDP connection from Mac shows i3 desktop on `:0`
