# watopnet — Watcher Operational Network

`watopnet` is a [KERI](https://github.com/WebOfTrust/keri) watcher service that monitors Autonomic Identifiers (AIDs) and verifies key-event consistency across witnesses. It exposes a dual-server HTTP architecture:

- **Boot server** (default port `7631`): management API for provisioning and deleting watchers
- **Watcher server** (default port `7632`): KERI event intake, OOBI resolution, and key-state query replies

Watchers are provisioned dynamically via the boot API. Each watcher instance manages its own KERI key store, tracks a set of observed AIDs, polls their witnesses for key state, and answers signed key-state queries from authorised controllers.

## Relationship to witopnet

`watopnet` was written in tandem with [`witopnet`](https://github.com/keri-foundation/witness-hk), the companion witness service. The dependency is directional:

1. **Witnesses must exist first.** An AID must be incepted with witnesses and have its key event log receipted before a watcher can monitor it — the watcher queries those witnesses to verify key state consistency.
2. **Sample deployment order:** start `witopnet` (ports `5631`/`5632`) → incept controller AID with witnesses → start `watopnet` (ports `7631`/`7632`) → provision watcher → register watched AID.

The `scripts/verifier.sh` script in this repo assumes `witopnet` is already running on `localhost:5632` and `/path/to/witness-hk/scripts/controller.sh` has already been run.

## Requirements

- Python >= 3.12.6
- `libsodium` (required by the `keri` package)

### Installing libsodium

**macOS:**
```bash
brew install libsodium
```

**Ubuntu/Debian:**
```bash
sudo apt-get install libsodium-dev
```

## Installation

### From PyPI

```bash
pip install watopnet
```

### For development

```bash
git clone https://github.com/keri-foundation/watcher-hk.git
cd watcher-hk
pip install -e ".[dev]"
```

## Configuration

The watcher server reads a KERI config file. A sample is provided at `scripts/keri/cf/watopnet.json`:

```json
{
  "dt": "2022-01-20T12:57:59.823350+00:00",
  "watopnet": {
    "dt": "2022-01-20T12:57:59.823350+00:00",
    "curls": ["http://localhost:7632/"]
  }
}
```

The `curls` field sets the URL(s) this watcher advertises externally. Place your config file in a directory you will pass to `--config-dir`.

> **Note:** `--config-dir` must point to the directory *above* `keri/cf/` — KERI appends `keri/cf/` internally when locating `watopnet.json`. For local dev this is the `scripts/` directory; for production it is wherever `keri/cf/watopnet.json` lives one level up.

## Running

### CLI

After installation, the `watopnet` CLI is available:

```bash
watopnet start \
  --config-dir /path/to/config \
  --host 0.0.0.0 \
  --http 7632 \
  --boothost 127.0.0.1 \
  --bootport 7631
```

**Key flags:**

| Flag | Default | Description |
|---|---|---|
| `--host` / `-o` | `127.0.0.1` | Host the watcher server listens on |
| `--http` / `-H` | `7632` | Port the watcher server listens on |
| `--boothost` / `-bh` | `127.0.0.1` | Host the boot server listens on |
| `--bootport` / `-bp` | `7631` | Port the boot server listens on |
| `--base` / `-b` | `""` | Optional path prefix for the KERI keystore |
| `--config-dir` / `-c` | — | Directory containing KERI config files (above `keri/cf/`) |
| `--config-file` | — | Config filename override |
| `--loglevel` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `--logfile` | — | Path to write log output |

Set `DEBUG_WATCHER=1` in your environment to print full tracebacks on errors.

## HTTP API

### Boot server (`localhost:7631`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/watchers` | Provision a new watcher for a controller AID. Body: `{"aid": "<qb64-AID>", "oobi": "<optional-oobi-url>"}`. Returns `{cid, eid, oobis}`. |
| `DELETE` | `/watchers/{eid}` | Delete a watcher by its endpoint identifier. |
| `GET` | `/watchers/{eid}/status` | Get watcher status: all observed AIDs and per-witness key state results. |

### Watcher server (`localhost:7632`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/` | Submit a KERI event (KEL/EXN/QRY) with CESR attachments. Requires `CESR-Destination` header. |
| `PUT` | `/` | Push raw CESR bytes into the inbound stream. Requires `CESR-Destination` header. |
| `GET` | `/oobi/{aid}` | OOBI resolution endpoint. |
| `GET` | `/oobi/{aid}/{role}` | OOBI with role. |
| `GET` | `/oobi/{aid}/{role}/{eid}` | OOBI with role and participant EID. |

## Scripts

All scripts that reference `${WATOPNET_SCRIPT_DIR}` require you to source `env.sh` first.

### `env.sh`

Sets `WATOPNET_SCRIPT_DIR` to the absolute path of the `scripts/` directory:

```bash
source scripts/env.sh
```

### `watopnet-sample.sh`

Launches the watcher and boot servers. Works for both local development (after `source scripts/env.sh`) and production deployment.

| Variable | Default | Description |
|---|---|---|
| `WATOPNET_VENV` | *(unset)* | Path to a venv `activate` script. Sourced if the file exists; warns and skips if set but not found; ignored if unset. |
| `WATOPNET_CONFIG_DIR` | `scripts/` directory | Directory containing `keri/cf/watopnet.json` (one level above `keri/cf/`). |
| `WATOPNET_HOST` | `0.0.0.0` | External host the watcher server binds to. |
| `WATOPNET_BOOT_HOST` | `127.0.0.1` | Host the boot/management server binds to. Keep on localhost in production. |
| `WATOPNET_HTTP_PORT` | `7632` | Watcher server port. |
| `WATOPNET_BOOT_PORT` | `7631` | Boot/management server port. |

Local dev (no env vars needed after sourcing `env.sh`):

```bash
source scripts/env.sh
./scripts/watopnet-sample.sh
```

Production example:

```bash
WATOPNET_VENV=/opt/healthkeri/watopnet/venv/bin/activate \
WATOPNET_CONFIG_DIR=/opt/healthkeri/watopnet/config \
./scripts/watopnet-sample.sh
```

### `verifier.sh`

Demonstrates provisioning a watcher and registering a watched AID. Requires `witopnet` running on `localhost:5631`/`5632` and `kli` (KERI CLI) installed.

```bash
source scripts/env.sh
./scripts/verifier.sh
```

Steps performed:
1. Initialises a `verifier` keystore and inceives the `verifier` AID
2. Provisions a new watcher via `POST /watchers` on the boot server and resolves the returned OOBI
3. Resolves the monitored controller's OOBI from the running witness
4. Registers the controller with the watcher via `kli watcher add`

### `package.sh`

Builds and publishes the package to PyPI. Requires `build` and `twine`:

```bash
pip install build twine

./scripts/package.sh          # publish to PyPI
./scripts/package.sh --test   # publish to TestPyPI
```

## Testing

Install the package in editable mode with dev dependencies, then run pytest:

```bash
pip install -e ".[dev]"
pytest tests/
```

Tests use temporary in-memory KERI keystores so no external services are required.

To run a specific test file:

```bash
pytest tests/watopnet/core/test_watching.py -v
```

## Project structure

```
src/watopnet/
├── app/
│   ├── cli/
│   │   ├── commands/start.py   # `watopnet start` subcommand
│   │   └── watcher.py          # CLI entry point
│   └── watching.py             # Watchery, Watcher, boot/watcher HTTP server setup
└── core/
    ├── basing.py               # LMDB Baser and dataclasses (Wat, WitnessQuery, Requests)
    ├── eventing.py             # KeveryQueryShim / QueryKeveryShim (KERI event routing)
    ├── httping.py              # HttpEnd (KERI event HTTP endpoint) + Throttle middleware
    ├── oobing.py               # OOBIEnd (OOBI HTTP endpoint)
    └── tcp/serving.py          # Directant (TCP server) + Reactant (per-connection handler)
```

## License

Apache-2.0. See [LICENSE](LICENSE).