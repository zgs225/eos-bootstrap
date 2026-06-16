# i915 SR-IOV Guest Driver Design

## Summary

Install the `i915-sriov-dkms` kernel module and supporting userspace libraries on VM guests that have an Intel GPU VF passed through via SR-IOV or GVT-g. Detection is automatic based on PCI device enumeration.

## Scope

- **Guest-side only.** Host-side SR-IOV configuration (sriov_numvfs, VF driver binding) is out of scope.
- **No VM environment detection.** The task triggers solely on Intel VGA device presence; the repo is assumed to run on the correct machine.
- **No Secure Boot handling.** Users must disable Secure Boot or sign the module themselves.

## Hardware Detection

Detect Intel VGA device via `lspci -nn`:

```
lspci -nn | grep -qiE '\[0300\].*8086:'
```

This matches lines like:

```
00:10.0 VGA compatible controller [0300]: Intel Corporation Alder Lake-P GT2 [Iris Xe Graphics] [8086:46a6] (rev 0c)
```

When matched, set `i915_sriov_detected: true`. All subsequent tasks are gated on this flag. Uses `failed_when: rc not in [0, 1]` to avoid failing when no Intel GPU is present (same pattern as `bluetooth.yml`).

## Package Installation

### Unconditional (pacman_packages default list)

| Package | Purpose |
|---|---|
| `linux-headers` | DKMS compilation dependency; universally useful |

### Conditional (installed only when `i915_sriov_detected`)

| Package | Source | Purpose |
|---|---|---|
| `i915-sriov-dkms` | AUR | SR-IOV patched i915 driver |
| `intel-media-driver` | pacman | VAAPI hardware acceleration (Broadwell+) |
| `libva-utils` | pacman | `vainfo` diagnostic tool |
| `intel-opencl-icd` | pacman | OpenCL support |
| `clinfo` | pacman | OpenCL diagnostic tool |

The 5 conditional packages are installed inline in the task file, not added to `pacman_packages` or `aur_packages` default lists.

## Kernel Parameters

Required parameters for i915 mode: `i915.enable_guc=3 module_blacklist=xe`

### Bootloader Detection

1. Check if `/boot/loader/entries/` exists → systemd-boot
2. Else check if `/etc/default/grub` exists → GRUB
3. Else fail with message instructing manual configuration

### systemd-boot

For each `.conf` file in `/boot/loader/entries/`, append the parameters to the `options` line if not already present. This uses `lineinfile` with `regexp` to match the `options` line and `backrefs: true` for idempotent appending.

### GRUB

Use `lineinfile` on `/etc/default/grub` to append parameters to `GRUB_CMDLINE_LINUX_DEFAULT` if not already present. Then run `grub-mkconfig -o /boot/grub/grub.cfg`.

### Idempotency

Both paths grep for `i915.enable_guc=3` before making changes. If parameters already exist, no change is made.

## initramfs Rebuild

After DKMS module installation or kernel parameter changes, trigger `mkinitcpio -P` via an Ansible handler. The handler is notified by:
- DKMS package installation task
- Kernel parameter modification tasks

## File Changes

| File | Change |
|---|---|
| `ansible/roles/packages/defaults/main.yml` | Add `linux-headers` to `pacman_packages` |
| `ansible/roles/packages/tasks/i915-sriov.yml` | **New**: detection, conditional package install, kernel parameter config |
| `ansible/roles/packages/tasks/main.yml` | Add `include_tasks: i915-sriov.yml` with tag `[packages, i915-sriov]` |
| `ansible/roles/packages/handlers/main.yml` | Add `Regenerate initramfs` handler (`mkinitcpio -P`) |

## Task Flow (i915-sriov.yml)

1. Detect Intel VGA via `lspci -nn` → register `i915_sriov_detected`
2. Install `i915-sriov-dkms` via paru (AUR), gated on detection
3. Install VAAPI/OpenCL packages via pacman, gated on detection
4. Detect bootloader type → register `bootloader_type`
5. Configure kernel parameters for systemd-boot or GRUB, gated on detection
6. Notify `Regenerate initramfs` handler when changes are made

## Conventions Followed

- `set -o pipefail` in shell commands
- `failed_when: rc not in [0, 1]` for detection commands (matches bluetooth.yml)
- `changed_when: false` and `check_mode: false` for AUR install (matches aur.yml)
- All tasks tagged `[packages, i915-sriov]`
- `become: true` at playbook level; `become_user: {{ target_user }}` for AUR
