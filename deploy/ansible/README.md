# Ansible Host-First Watcher Deployment

Ansible automation for deploying a KERI watcher node using the host-first
posture: Ansible prepares the host, Circus supervises the watcher process,
and systemd keeps `circusd` running across reboots.

## Architecture

```
systemd
  └── circusd-watcher.service
        └── circusd (Circus process manager)
              └── watopnet-watcher watcher
                    └── run-watopnet.sh  ->  watopnet start
```

Ansible owns the machine state: packages, users, directories, Python venv,
a synced local checkout of `watcher-hk`, rendered configs, and the systemd unit.
Circus owns the process lifecycle after the host is prepared.

## Prerequisites

- Ansible 2.14+ on the operator workstation
- 1Password CLI (`op`) signed in to your account
- `community.general` collection

Install the collection with:

```bash
ansible-galaxy collection install community.general
```

## First-Time Setup

1. Copy the secret-reference template and fill in your 1Password references:

   ```bash
   cp op.env.example op.env
   ```

2. Add a `host_vars/<your-host>.yml` following the pattern in
   `inventories/pilot/host_vars/watcher-do-01.yml`.

3. Add the host to `inventories/pilot/hosts.yml` under `watcher_hosts`.

4. Review the defaults in `inventories/pilot/group_vars/watcher_hosts.yml`.

5. Run the preflight check:

   ```bash
   ./with-op-ssh-agent.sh --no-ssh-agent \
     ansible-playbook -i inventories/pilot/hosts.yml playbooks/watcher-preflight.yml
   ```

## Operator Workflow

### From the repository root

```bash
make watcher-preflight
make watcher-check
make watcher-apply
make watcher-verify
make watcher-status
make watcher-logs
```

### Direct playbook invocation

Run from `deploy/ansible/`:

```bash
./with-op-ssh-agent.sh --no-ssh-agent \
  ansible-playbook -i inventories/pilot/hosts.yml playbooks/watcher-preflight.yml

./with-op-ssh-agent.sh \
  ansible -i inventories/pilot/hosts.yml watcher-do-01 -m ping

./with-op-ssh-agent.sh \
  ansible-playbook -i inventories/pilot/hosts.yml playbooks/watcher-bootstrap.yml --check --diff

./with-op-ssh-agent.sh \
  ansible-playbook -i inventories/pilot/hosts.yml playbooks/watcher-bootstrap.yml

./with-op-ssh-agent.sh \
  ansible-playbook -i inventories/pilot/hosts.yml playbooks/watcher-verify.yml
```

## Authentication

SSH authentication uses the native 1Password SSH agent. Controller-side values
(`ansible_user`, `ansible_host`, `ansible_become_password`) are injected via a
short-lived `op run` subprocess through `with-op-ssh-agent.sh`.

The current validated escalation path for the pilot host remains:

1. SSH as `keri`
2. `su` to `root`

`sudo` is not assumed.

## Lint

```bash
ansible-lint playbooks/watcher-bootstrap.yml \
            playbooks/watcher-preflight.yml \
            playbooks/watcher-verify.yml \
            roles/watcher_host
```

## Directory Layout

```
deploy/ansible/
├── .ansible-lint.yml
├── ansible.cfg
├── op.env.example
├── README.md
├── with-op-ssh-agent.sh
├── inventories/
│   └── pilot/
│       ├── hosts.yml
│       ├── group_vars/
│       │   └── watcher_hosts.yml
│       └── host_vars/
│           └── watcher-do-01.yml
├── playbooks/
│   ├── watcher-preflight.yml
│   ├── watcher-bootstrap.yml
│   └── watcher-verify.yml
└── roles/
    └── watcher_host/
        ├── handlers/main.yml
        ├── tasks/main.yml
        └── templates/
            ├── circus-watcher.ini.j2
            ├── circusd-watcher.service.j2
            ├── run-watopnet.sh.j2
            └── watopnet.json.j2
```

## What the Bootstrap Does

1. Installs system packages: `git`, `build-essential`, `libsodium-dev`,
   `python3.14`, `python3.14-venv`, `python3-pip`, `rsync`
2. Creates the `keri` system user and group
3. Creates directories for config, logs, runtime, and KERI data
4. Copies the current local `watcher-hk` checkout into `/opt/watcher-hk`
5. Creates a Python 3.14 venv at `/opt/watcher-hk/.venv`
6. Installs `circus` and the local `watcher-hk` package into the venv
7. Renders `/etc/watopnet/keri/cf/main/watopnet.json`
8. Renders `/opt/watcher-hk/ops/run-watopnet.sh`
9. Renders `/etc/watopnet/circus-watcher.ini`
10. Renders `/etc/systemd/system/circusd-watcher.service`
11. Enables and starts the `circusd-watcher` systemd unit