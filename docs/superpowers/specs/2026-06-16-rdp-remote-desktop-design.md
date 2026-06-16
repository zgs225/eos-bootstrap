# RDP Remote Desktop (xrdp + Xorg)

## Summary

Enable RDP remote desktop access on the EndeavourOS workstation using xrdp with Xorg backend (hardware acceleration). Each RDP connection creates an independent i3wm session (does not share the local console). Intended for LAN-only access, always enabled as a core service.

## Architecture

```
RDP client → xrdp (0.0.0.0:3389) → sesman → Xorg :10+ → i3wm
```

- xrdp listens on port 3389 (standard RDP).
- sesman forks a new Xorg process per connection (display numbers start at 10).
- Each session runs i3wm via `~/.xsession` (managed by the dotfiles repo).
- Sessions persist after disconnect; user logs out explicitly to destroy them.
- Xorg backend provides GPU acceleration for applications like wezterm.

## Packages

| Package  | Source  | Purpose          |
|----------|---------|------------------|
| xrdp     | pacman  | RDP server       |
| xorgxrdp | pacman  | Xorg backend     |

`tigervnc` is intentionally excluded (Xvnc backend provides no GPU acceleration; this design uses Xorg for hardware-accelerated rendering).

## Configuration

### /etc/xrdp/xrdp.ini

Default configuration is sufficient. Key defaults that require no changes:

- `port=3389`
- Session type is `Xorg` (configured in sesman.ini)

### /etc/xrdp/sesman.ini

Override the `[Xorg]` section parameters to use the full path to Xorg and configure for xrdp.

```ini
[Xorg]
param=/usr/lib/Xorg
param=-config
param=xrdp/xorg.conf
param=-nolisten
param=tcp
```

The `[Xvnc]` section can be removed entirely (not needed for Xorg backend).

### ~/.xsession

This file is owned by the **dotfiles repo**, not this repo. The dotfiles repo must provide `~/.xsession` that execs i3 (similar to `~/.xinitrc`). xrdp sesman executes `~/.xsession` when starting a session. If the file is missing, sesman falls back to `/etc/X11/xinit/Xsession`, which may not start i3 correctly.

**Action for dotfiles repo**: Add `~/.xsession` that does `exec i3`.

## Ansible Changes

### packages role

- `roles/packages/defaults/main.yml`: Add `xrdp` and `xorgxrdp` to `pacman_packages`. Remove `tigervnc`.

### services role

- `roles/services/vars/core_services.yml`: Add `xrdp.service` to `core_services`.

### New task: roles/packages/tasks/xrdp.yml

Deploys xrdp configuration:

1. Ensure `/etc/xrdp/` directory exists.
2. Deploy `sesman.ini` via `ansible.builtin.template` (using a `sesman.ini.j2` template) with the `[Xorg]` section configured. Using a template ensures the full file is declarative and idempotent.
3. Optionally deploy custom `/etc/xrdp/xorg.conf` if needed for GPU passthrough (see Hardware Acceleration note below).
4. Notify handler `Restart xrdp` on config change.

Include this task from `roles/packages/tasks/main.yml` with tags `[packages, xrdp]`.

### Handler

Add handler `Restart xrdp` to the packages role (or a shared handlers file) that restarts `xrdp.service`.

## Security

- **Authentication**: PAM (system username/password). Standard Linux login credentials.
- **Network scope**: Listens on `0.0.0.0:3389`, accessible from LAN. No firewall rules added (project convention: no ufw).
- **No TLS configuration**: On LAN, the default xrdp SSL cert is sufficient. No custom cert management needed.

## Hardware Acceleration

The Xorg backend provides GPU acceleration by running a real Xorg server (instead of Xvnc's software rendering). This is required for:

- wezterm GPU rendering
- Other hardware-accelerated applications

**Shared GPU consideration:** The Xorg session uses the same graphics driver as the local console. This works automatically on most systems with open-source drivers (amdgpu, intel, nouveau). Proprietary drivers (NVIDIA) may require additional configuration for multi-seat access.

## Boundary Compliance

- Ansible writes only to `/etc/xrdp/` (system-level config). Does not write under `~`.
- `~/.xsession` is managed by the dotfiles repo (chezmoi).
- `xrdp.service` enablement is in core_services (coarse system layer), consistent with the two-repo model.

## Testing

- After playbook run, connect from a LAN device using an RDP client (e.g., Microsoft Remote Desktop, FreeRDP).
- Verify: independent i3wm session starts, PAM login required, session persists after disconnect.
- Idempotency: second playbook run must show no changed tasks for xrdp configuration.
