# eos-bootstrap Runbook

Day-to-day operations for this bootstrap.

## Add a package

Pacman:

```yaml
# ansible/roles/packages/vars/pacman_packages.yml
pacman_packages:
  - <new-package>
```

Then re-run:

```bash
./bootstrap.sh
```

AUR:

```yaml
# ansible/roles/packages/vars/aur_packages.yml
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
5. `./bootstrap.sh`.
6. Verify: `systemctl is-active NetworkManager docker`, `i3` starts at login, `mise list` shows go/python/node/rust.
