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

Run from `ansible/`:

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

## Deployment Evidence Checklist

For AI-assisted deployment work, do not treat a successful apply as proof that the deployment is correct. Capture evidence from the controller, the host, and the running service.

### Minimum Evidence For A Deployment Change

1. **Task scope**
  - record what was intended to change
  - note what was not supposed to change
2. **Controller-side validation**
  - run `ansible-lint`
  - run `make watcher-preflight`
  - run `make watcher-check`
3. **Apply evidence**
  - run `make watcher-apply`
  - keep the terminal output or summarize the important state changes
4. **Post-apply verification**
  - run `make watcher-verify`
  - run `make watcher-status`
  - run `make watcher-logs`
5. **Human review of host state**
  - confirm the service manager sees the unit as healthy
  - confirm Circus sees the watcher process as healthy
  - confirm the wrapper-backed runtime contract still matches the expected launch path
  - confirm expected ports or sockets are reachable
  - confirm recent logs are reviewed using the current boot or current start window, not just the tail of append-only files
  - confirm a smoke check passed where the lane supports one

### What Counts As Enough Evidence

At minimum, the operator should be able to say:

1. what changed
2. what commands were run
3. what outputs were reviewed directly
4. whether the host converged cleanly
5. whether any ambiguity remains

### Operational Notes

1. A running PID is not enough. Treat `systemctl status` as one input, not the final proof.
2. If logs are append-only, tie any error review to the current run window before concluding the service is still broken.
3. If repeated runs do not converge cleanly, stop and investigate instead of normalizing the drift.
4. Save or summarize the evidence in the task record or PR notes so the review trail survives after the terminal scrollback is gone.

## Directory Layout

```
ansible/
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
4. Copies the tracked local `watcher-hk` project files into `/opt/watcher-hk`
5. Creates a Python 3.14 venv at `/opt/watcher-hk/.venv`
6. Installs `circus` and the local `watcher-hk` package into the venv
7. Renders `/etc/watopnet/keri/cf/main/watopnet.json`
8. Renders `/opt/watcher-hk/ops/run-watopnet.sh`
9. Renders `/etc/watopnet/circus-watcher.ini`
10. Renders `/etc/systemd/system/circusd-watcher.service`
11. Enables and starts the `circusd-watcher` systemd unit