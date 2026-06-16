# RDP Remote Desktop (xrdp + Xvnc)

## Summary

Enable RDP remote desktop access on the EndeavourOS workstation using xrdp with Xvnc backend. Each RDP connection creates an independent i3wm session (does not share the local console). Intended for LAN-only access, always enabled as a core service.

## Architecture

```
RDP client → xrdp (0.0.0.0:3389) → sesman → Xvnc :10+ → i3wm
```

- xrdp listens on port 3389 (standard RDP).
- sesman forks a new Xvnc process per connection (display numbers start at 10).
- Each session runs i3wm via `~/.xsession` (managed by the dotfiles repo).
- Sessions persist after disconnect; user logs out explicitly to destroy them.

## Packages

| Package  | Source  | Purpose          |
|----------|---------|------------------|
| xrdp     | pacman  | RDP server       |
| tigervnc | pacman  | Xvnc backend     |

No AUR packages required. `xorgxrdp` is intentionally excluded (only needed for the Xorg backend, which this design does not use).

## Configuration

### /etc/xrdp/xrdp.ini

Default configuration is sufficient. Key defaults that require no changes:

- `port=3389`
- Default session type is `Xvnc` (first entry in `[Xvnc]` section takes priority)

### /etc/xrdp/sesman.ini

Override the `[Xvnc]` section parameters to include `-securitytypes None`. This is safe because Xvnc only listens on loopback; all external access goes through xrdp's PAM authentication.

```ini
[Xvnc]
param=-securitytypes
param=None
```

Any additional Xvnc parameters (resolution, pixel depth) are left to client-side negotiation via the RDP protocol.

### ~/.xsession

This file is owned by the **dotfiles repo**, not this repo. The dotfiles repo must provide `~/.xsession` that execs i3 (similar to `~/.xinitrc`). xrdp sesman executes `~/.xsession` when starting a session. If the file is missing, sesman falls back to `/etc/X11/xinit/Xsession`, which may not start i3 correctly.

**Action for dotfiles repo**: Add `~/.xsession` that does `exec i3`.

## Ansible Changes

### packages role

- `roles/packages/defaults/main.yml`: Add `xrdp` and `tigervnc` to `pacman_packages`.

### services role

- `roles/services/vars/core_services.yml`: Add `xrdp.service` to `core_services`.

### New task: roles/packages/tasks/xrdp.yml

Deploys xrdp configuration:

1. Ensure `/etc/xrdp/` directory exists.
2. Deploy `sesman.ini` override via `ansible.builtin.template` (using a `sesman.ini.j2` template) to set `-securitytypes None` in the `[Xvnc]` param list. Using a template rather than lineinfile ensures the full file is declarative and idempotent.
3. Notify handler `Restart xrdp` on config change.

Include this task from `roles/packages/tasks/main.yml` with tags `[packages, xrdp]`.

### Handler

Add handler `Restart xrdp` to the packages role (or a shared handlers file) that restarts `xrdp.service`.

## Security

- **Authentication**: PAM (system username/password). Standard Linux login credentials.
- **Network scope**: Listens on `0.0.0.0:3389`, accessible from LAN. No firewall rules added (project convention: no ufw).
- **VNC layer**: `-securitytypes None` on Xvnc is safe because Xvnc binds only to loopback. External access requires PAM authentication through xrdp.
- **No TLS configuration**: On LAN, the default xrdp SSL cert is sufficient. No custom cert management needed.

## Boundary Compliance

- Ansible writes only to `/etc/xrdp/` (system-level config). Does not write under `~`.
- `~/.xsession` is managed by the dotfiles repo (chezmoi).
- `xrdp.service` enablement is in core_services (coarse system layer), consistent with the two-repo model.

## Testing

- After playbook run, connect from a LAN device using an RDP client (e.g., Microsoft Remote Desktop, FreeRDP).
- Verify: independent i3wm session starts, PAM login required, session persists after disconnect.
- Idempotency: second playbook run must show no changed tasks for xrdp configuration.
