# eos-bootstrap Runbook

Day-to-day operations for this bootstrap.

## Add a package

Pacman:

```yaml
# ansible/roles/packages/defaults/main.yml
pacman_packages:
  - <new-package>
```

Then re-run:

```bash
./bootstrap.sh
```

AUR:

```yaml
# ansible/roles/packages/defaults/main.yml
aur_packages:
  - <new-aur-package>
```

## Add a core service

```yaml
# ansible/roles/services/vars/core_services.yml
core_services:
  - <service>.service
```

Then `./bootstrap.sh`. (Service additions go through code review because this file is hardcoded.)

## Add an optional service

```yaml
# ansible/group_vars/all.yml
optional_services:
  - <service>.service
```

## Add a NetworkManager connection

Drop a `.nmconnection` file into `ansible/roles/network/files/nmconnection/`. Permissions are forced to `0600` (root) at deploy time.

## Add a kernel tunable

Edit `ansible/roles/kernel/templates/sysctl.d.conf.j2`. The handler `Apply sysctl` re-applies on change.

## Add a kernel module

Edit `ansible/roles/kernel/defaults/main.yml`:

```yaml
kernel_modules:
  - <module-name>
```

## Add a user group

```yaml
# ansible/group_vars/all.yml
user_groups:
  - <group-name>
```

## Add a polkit rule

Drop a `.rules` file into `ansible/roles/user/files/polkit/`.

## Lint

```bash
tests/lint.sh
```

## Idempotency check

```bash
tests/idempotency.sh
```

## Re-apply dotfiles only

```bash
chezmoi apply
```

## Encrypted dotfiles (age)

When your dotfiles repo contains files encrypted with
[age](https://age-encryption.org) (files with an `.age` suffix in the chezmoi
source state), enable the encryption guard:

```yaml
# ansible/group_vars/all.yml
dotfiles_use_encryption: true
```

Before running `./bootstrap.sh`, place your age private key:

```bash
mkdir -p ~/.config/chezmoi
# Paste or copy your age identity into this file:
vim ~/.config/chezmoi/key.txt
```

Alternatively, set `AGE_KEY_FILE` to point to your identity:

```bash
export AGE_KEY_FILE=/path/to/age-identity
./bootstrap.sh
```

If `dotfiles_use_encryption` is `true` but no identity is found, `bootstrap.sh`
will `die` with a clear message before invoking chezmoi. The `age` binary is
installed by the `packages` Ansible role.

The encryption recipient configuration (`[encryption.age] recipient`) lives in
the dotfiles repo at `.chezmoi/chezmoi.toml` — do not manage it here.

## Re-apply Ansible only

```bash
ansible-playbook ansible/playbook.yml --ask-become-pass
```

## Update mise tool versions

Edit `~/.config/mise/config.toml` in the dotfiles repo, then `chezmoi apply` triggers `run_once_after_*` which runs `mise install`.

## Smoke test (fresh VM)

1. Boot EndeavourOS installer, install base system.
2. Install git: `sudo pacman -S git`.
3. `git clone <this-repo> && cd eos-bootstrap`.
4. Edit `ansible/group_vars/all.yml` to set `dotfiles_repo` to your dotfiles repo URL.
   Optionally set `dotfiles_branch` to clone a specific branch on first init
   (leave empty for the remote's default branch).
   If the dotfiles repo contains age-encrypted files, set
   `dotfiles_use_encryption: true` and place your age private key at
   `~/.config/chezmoi/key.txt` (or set `$AGE_KEY_FILE`).
5. If running inside a Proxmox/QEMU/KVM guest, also set `vm_services` to the
   list of systemd units to enable (see the variable's inline comment for the
   standard Proxmox set). On bare metal, leave it as `[]`.
6. `./bootstrap.sh`.
7. Verify: `systemctl is-active NetworkManager docker`, `i3` starts at login,
   `mise list` shows go/python/node/rust. On a VM guest, also verify
   `systemctl is-active qemu-guest-agent cloud-init-local cloud-init
   cloud-config cloud-final`.

## Add a VM-specific service (cloud-init, qemu-guest-agent)

The packages `cloud-init` and `qemu-guest-agent` are installed by default in
`ansible/roles/packages/defaults/main.yml`. Service enablement is
controlled separately by the `vm_services` list in `group_vars/all.yml`:

```yaml
# ansible/group_vars/all.yml
vm_services:
  - cloud-init-local.service
  - cloud-init.service
  - cloud-config.service
  - cloud-final.service
  - qemu-guest-agent.service
```

Then re-run `./bootstrap.sh`. The `packages` role's `cloud_init.yml` task
enables and starts each listed service. Leave `vm_services: []` for
bare-metal installs; the packages are harmless when not in a VM (cloud-init
no-ops without a datasource, qemu-guest-agent no-ops without the virtio
serial channel).
