# Molecule Integration Tests — watcher\_host Role

Validates that the Ansible role works under real systemd security hardening,
catching the class of failure documented in ADR-056 (ProtectSystem=strict +
ProtectHome=true vs. hio filesystem paths), while keeping the local Molecule OS
and Python surface aligned with the proven DigitalOcean host baseline.

## Prerequisites

| Dependency | Version | Notes |
|---|---|---|
| Docker Desktop | 28.x+ | Daemon must be **running** |
| Python 3.12+ | — | For Molecule itself |
| molecule | ≥ 5.1.0 | `pip install -r molecule/requirements.txt` |
| molecule-plugins\[docker\] | ≥ 23.5.3 | Docker driver |

Install Molecule deps (role root):

```bash
pip install -r molecule/requirements.txt
```

Molecule's Galaxy prerun resolves dependency files relative to the role root, so
this role keeps them at `molecule/requirements.yml` and
`molecule/collections.yml`. The scenario points to those files explicitly, and
Molecule installs the declared collections during the dependency phase.

## DigitalOcean parity

The current production proof host reports:

```bash
cat /etc/lsb-release
DISTRIB_ID=Ubuntu
DISTRIB_RELEASE=25.10
DISTRIB_CODENAME=questing
DISTRIB_DESCRIPTION="Ubuntu 25.10"
```

The Molecule scenario therefore builds a custom systemd-ready image from
`ubuntu:25.10` instead of using the older Ubuntu 24.04 Ansible image. This keeps
the local validation lane aligned with the DigitalOcean release and makes
`python3.14` available for the watcher stack's current dependency floor.

## Quick start

From the **repo root** (`watcher-hk/`):

```bash
make molecule-test      # Full cycle: create → converge → verify → destroy
make molecule-converge  # Apply the role (re-runnable for iteration)
make molecule-verify    # Run systemd-hardening assertions only
make molecule-destroy   # Tear down the container
make molecule-login     # Shell into the running container
```

Or from the role directory directly:

```bash
cd ansible/roles/watcher_host
molecule test
```

The scenario keeps only role-specific playbooks inside `molecule/default/` and
keeps dependency manifests at the role-root `molecule/` directory to match
Molecule's documented search behavior.

The tracked `make molecule-test` path uses a custom Molecule `test_sequence`
that runs `syntax`, `create`, `prepare`, `converge`, `verify`, and `destroy`.
It intentionally skips Molecule's default idempotence step because this role's
integration target is a host-shaped systemd deployment that stages local source
and installs an editable Python package during converge.

## What verify checks

The verify playbook (`molecule/default/verify.yml`) asserts:

1. **Service running** — `circusd-watcher.service` is active and enabled
2. **Security directives present** — `ProtectSystem=strict`, `ProtectHome=true`,
   `NoNewPrivileges=true`, and `/usr/local/var/keri` in `ReadWritePaths`
3. **IPC socket exists** — Circus control socket at expected path
4. **Log files exist** — stdout.log and stderr.log created
5. **Circus reports active** — `circusctl status` shows `watopnet-watcher`
6. **Process stability** — PID sampled twice 3s apart, must be the same (not crash-looping)
7. **Ports bound** — 7631 (boot) and 7632 (HTTP) listening
8. **No Permission Denied** — Fresh stdout log has no filesystem errors
9. **hio path writable** — `/usr/local/var/keri` writable by service user
10. **HOME in Circus env** — Circus config includes `HOME` override

The scenario now includes a `prepare.yml` step that refreshes the apt cache on the
Ubuntu container before the role attempts package installation.

## Platform notes

- Base image: `ubuntu:25.10`
- Molecule builds a custom Docker image with systemd, `python3.14`,
  `python3.14-venv`, and the packages required by the watcher role.
- This keeps the container closer to the proven DigitalOcean host baseline than the
  previous Ubuntu 24.04 approximation.
- Requires privileged mode and `cgroupns_mode: host` for systemd-in-Docker.

## Known limitations

- Docker's systemd support does not perfectly replicate a bare-metal kernel.
  Some `systemd-analyze security` checks behave differently in containers.
- The watcher Python app is installed from the repo source tree during converge.
  Build failures (missing C deps like libsodium) surface at converge, not verify.
