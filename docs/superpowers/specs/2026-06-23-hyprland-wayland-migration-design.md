# Hyprland/Wayland Migration Design

## Scope

In-place replacement of the X11/i3 display stack with Wayland/Hyprland in **this repo only** (eos-bootstrap). Changes to the dotfiles repo (chezmoi-managed user configs) are documented for reference but implemented separately.

## Decisions

| Decision | Choice |
|---|---|
| Migration mode | Hard switch — remove X11 entirely |
| xrdp remote desktop | Drop entirely |
| Launch chain | tty1 autologin → `~/.zprofile` execs Hyprland |
| fcitx5 input method | Switch to native Wayland IM module |
| Hyprland source | pacman (stable) |
| Sunshine remote streaming | Adapt for Wayland, keep installed |
| Implementation scope | This repo only; dotfiles repo gets a spec appendix |

## Package Swaps

### Remove from `pacman_packages`

| Package | Reason |
|---|---|
| `xorg-server` | X11 display server |
| `xorg-xinit` | startx / xinitrc chain |
| `xclip` | X11 clipboard (replaced by wl-clipboard) |
| `tigervnc` | VNC server (x0vncserver, X11-coupled) |
| `i3-wm` | i3 window manager |
| `i3status` | i3 status line |
| `i3lock` | i3 screen lock |
| `polybar` | X11-native bar |
| `rofi` | X11-native launcher |
| `dunst` | X11-native notifications |
| `picom` | X11 compositor (Wayland compositor is built-in) |
| `feh` | X11 wallpaper setter |
| `arandr` | X11 display layout (replaced by wdisplays) |
| `lxappearance` | X11 GTK theme config (replaced by nwg-look) |

### Add to `pacman_packages`

| Package | Role | Replaces |
|---|---|---|
| `hyprland` | Wayland compositor | i3-wm, picom |
| `waybar` | Status bar | polybar |
| `anyrun` | Application launcher | rofi |
| `mako` | Notification daemon | dunst |
| `hyprpaper` | Wallpaper setter | feh |
| `grim` | Screenshot capture | maim (from dotfiles) |
| `slurp` | Region selection for screenshot | — |
| `swaylock` | Screen locker | i3lock |
| `wl-clipboard` | Wayland clipboard | xclip |
| `wlogout` | Logout/power menu | rofi powermenu (from dotfiles) |
| `wdisplays` | Display layout GUI | arandr |
| `nwg-look` | GTK theme config | lxappearance |
| `xdg-desktop-portal-hyprland` | Screen share, file picker portal | — |

### Remove from `aur_packages`

| Package | Reason |
|---|---|
| `xrdp` | RDP server — X11-coupled, user chose "Drop xrdp entirely" |

### Kept unchanged

- `mesa`, `mesa-utils` — display-server-agnostic
- `fcitx5*` — same packages, Wayland IM module is a runtime config change
- `wezterm` — native Wayland support
- Theming (`gtk3`, `gtk4`, `papirus-icon-theme`, fonts) — unchanged
- `spice-vdagent` — works on Wayland via `xdg-desktop-portal`
- `sunshine` — stays in AUR list, task adapted (see below)

## Task File Changes

### Delete

- `ansible/roles/packages/tasks/xrdp.yml` — 156 lines, X11-coupled
- `ansible/roles/packages/templates/xrdp.ini.j2` — xrdp config template
- `ansible/roles/packages/templates/x0vncserver.service.j2` — hardcodes `DISPLAY=:0`, `XAUTHORITY`

### Modify

- **`ansible/roles/packages/tasks/main.yml`**: Remove the xrdp include block (lines 27-30)
- **`ansible/roles/packages/handlers/main.yml`**: Remove `Restart xrdp`, `Reload user systemd`, `Restart x0vncserver` handlers. Keep `Regenerate initramfs` and `Reload systemd`.

### No changes needed

- **`ansible/roles/packages/tasks/sunshine.yml`**: Sunshine uses KMS/VAAPI capture — display-server-agnostic. No X11 env vars in the task. Kept as-is.
- **`ansible/roles/packages/tasks/pacman.yml`**: Generic pacman installer — unchanged.
- **`ansible/roles/packages/tasks/aur.yml`**: Generic AUR installer — unchanged.
- **`ansible/roles/packages/tasks/bluetooth.yml`**: Unchanged.
- **`ansible/roles/packages/tasks/cloud_init.yml`**: Unchanged.
- **`ansible/roles/packages/tasks/i915-sriov.yml`**: GPU-level, unchanged.

## Display Role

The display role (`ansible/roles/display/`) only manages tty1 autologin. No structural changes — autologin is display-server-agnostic.

- `defaults/main.yml`: Unchanged (`display_autologin_tty: tty1`)
- `tasks/main.yml`: Unchanged
- `tasks/autologin.yml`: Unchanged
- `handlers/main.yml`: Unchanged

## Variable Changes in `group_vars/all.yml`

Remove:
```yaml
# xrdp remote desktop (VNC backend, shares :0 display).
# Set to true to enable xrdp (RDP) + x0vncserver (VNC sharing :0).
# xrdp-sesman is disabled; no separate X sessions.
# Package tigervnc provides x0vncserver; xrdp provides RDP listener.
xrdp_enabled: true
```

Update comment for autologin:
```yaml
# tty1 autologin → Hyprland (Wayland compositor).
display_autologin_enabled: true
```

No new variables. Hard switch — no compositor-selection gate.

## Bootstrap Script

No changes. `bootstrap.sh` greps `group_vars/all.yml` for `dotfiles_repo`/`dotfiles_branch`/`dotfiles_use_encryption` only, never touches display variables.

## Files Changed Summary

| File | Action |
|---|---|
| `ansible/roles/packages/defaults/main.yml` | Modify: swap packages |
| `ansible/roles/packages/tasks/main.yml` | Modify: remove xrdp include |
| `ansible/roles/packages/tasks/xrdp.yml` | Delete |
| `ansible/roles/packages/templates/xrdp.ini.j2` | Delete |
| `ansible/roles/packages/templates/x0vncserver.service.j2` | Delete |
| `ansible/roles/packages/handlers/main.yml` | Modify: remove xrdp handlers |
| `ansible/group_vars/all.yml` | Modify: remove xrdp_enabled, update comment |

## Idempotency & Lint

- Removed xrdp tasks had `changed_when`/`failed_when` guards — removing them reduces idempotency surface
- New pacman packages flow through `community.general.pacman` (inherently idempotent)
- `tests/lint.sh` (ansible-lint, yamllint, shellcheck) should pass
- `tests/idempotency.sh` — removing inherently non-idempotent xrdp tasks improves reliability

## Appendix: Dotfiles Repo Changes (Spec Only)

These changes are documented for reference but **not implemented in this repo**:

| Component | Path | Change |
|---|---|---|
| Launch chain | `~/.zprofile` | Replace `startx` with `exec Hyprland`, check `WAYLAND_DISPLAY` not `DISPLAY` |
| i3 config | `~/.config/i3/` | Remove or archive |
| Hyprland config | `dot_config/hypr/hyprland.conf.tmpl` | New — compositor, keybinds, window rules, autostart |
| Waybar config | `dot_config/waybar/config.tmpl` + `style.css.tmpl` | New |
| Anyrun config | `dot_config/anyrun/config.tmpl` + `style.css.tmpl` | New |
| Mako config | `dot_config/mako/config.tmpl` | New |
| Hyprpaper config | `dot_config/hypr/hyprpaper.conf.tmpl` | New |
| Screenshot script | `dot_local/share/bin/executable_screenshot.sh` | Replace maim with grim+slurp |
| Swaylock config | `dot_config/swaylock/config.tmpl` | New |
| Wlogout script | `dot_bin/executable_wlogout` | New or updated |
| Clipboard | `dot_tmux.conf` | Already handles wl-clipboard per mapping table |
| fcitx5 env | `~/.xprofile` | Remove, move `FCITX5_IM_MODULE=fcitx` to `~/.zprofile` or Hyprland config |
| xinit config | `~/.xinitrc` | Remove or archive |
