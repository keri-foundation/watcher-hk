# watopnet — Watcher Operational Network

`watopnet` is a [KERI](https://github.com/WebOfTrust/keri) watcher service that monitors Autonomic Identifiers (AIDs) and verifies key-event consistency across witnesses. It exposes a dual-server HTTP architecture:

- **Boot server** (default port `7631`): management API for provisioning and deleting watchers
- **Watcher server** (default port `7632`): KERI event intake, OOBI resolution, and key-state query replies

Watchers are provisioned dynamically via the boot API. One `watopnet` process hosts any number of watchers; each watcher is a separate non-transferable identifier with its own KERI keystore, bound to exactly one controller AID. A watcher tracks the AIDs its controller asks it to observe, periodically polls each observed AID's witnesses for key state, compares it with its local copy of the KEL, and records the result (`even`, `ahead`, `behind`, `duplicitous`, or `unresponsive`) for retrieval via the status endpoint.

## Relationship to witopnet

`watopnet` was written in tandem with [`witopnet`](https://github.com/keri-foundation/witness-hk), the companion witness service. The dependency is directional:

1. **Witnesses must exist first.** An AID must be incepted with witnesses and have its key event log receipted before a watcher can monitor it — the watcher queries those witnesses to verify key state consistency.
2. **Sample deployment order:** start `witopnet` (ports `5631`/`5632`) → incept controller AID with witnesses → start `watopnet` (ports `7631`/`7632`) → provision watcher → register watched AID.

The `scripts/verifier.sh` script in this repo assumes `witopnet` is already running on `localhost:5632` and `/path/to/witness-hk/scripts/controller.sh` has already been run (it hard-codes that script's controller AID and witness OOBI).

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

The watcher server reads a KERI config file. A sample is provided at `scripts/keri/cf/main/watopnet.json`:

```json
{
  "dt": "2022-01-20T12:57:59.823350+00:00",
  "watopnet": {
    "dt": "2022-01-20T12:57:59.823350+00:00",
    "curls": ["http://localhost:7632/"]
  }
}
```

The `curls` field sets the URL(s) this service advertises externally; the first entry supplies the scheme, hostname and port used in the OOBI URLs returned when a watcher is provisioned (a second entry, if present, sets a TCP port that is currently unused — see [Project structure](#project-structure)). The `curls` entry is only honoured when the `watopnet` section also contains a `dt` field.

> **Note:** `--config-dir` must point to the directory *above* `keri/cf/` — KERI's `Configer` resolves the file as `<config-dir>/keri/cf/main/watopnet.json` (the `main/` segment is KERI's default config base). For local dev, `--config-dir scripts/` finds `scripts/keri/cf/main/watopnet.json`. If the file is not found at that path, **no error is raised**: an empty config is used and the watcher advertises `http://127.0.0.1:7632` in its OOBIs. (`scripts/keri/cf/watopnet.json` is a stale copy at a path KERI does not read.)

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
| `--config-dir` / `-c` | — | Directory above `keri/cf/main/` containing `watopnet.json` |
| `--config-file` | — | Accepted but currently ignored; the config file is always `watopnet.json` |
| `--passcode` / `-p` | — | Accepted but currently ignored; watcher keystores are created unencrypted |
| `--keypath`, `--certpath`, `--cafilepath` | — | TLS key, certificate and CA bundle. Applied to the **boot server only**; the watcher server always speaks plain HTTP (terminate TLS at a proxy/Ingress) |
| `--loglevel` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `--logfile` | — | Path to write log output |
| `--version` / `-V` | — | Prints the version of the installed `keri` library |

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `DEBUG_WATCHER` | *(unset)* | If set, print full tracebacks on errors |
| `WATOPNET_DOIST_TOCK` | `0.03125` | Main event-loop tick, in seconds |
| `WATOPNET_ESCROW_TOCK` | `0.5` | How often each watcher processes its escrows, in seconds |
| `KERI_BASER_MAP_SIZE` | keripy default | LMDB map size; the sample script and Docker image set `1099511627776` |

Watcher keystores are unencrypted and stored in LMDB under the KERI data directory (`/usr/local/var/keri` if writable, else `~/.keri`); protect and back up that directory accordingly.

## HTTP API

### Boot server (`localhost:7631`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/watchers` | Provision a new watcher for a controller AID. Body: `{"aid": "<qb64-AID>", "oobi": "<optional-oobi-url>"}`; `oobi`, if given, is queued for the new watcher to resolve. Returns `200` with `{cid, eid, oobis}`; `400` if `aid` is missing/invalid; `503` if the process is out of file descriptors. Each call creates a new watcher — there is no de-duplication. |
| `DELETE` | `/watchers/{eid}` | Delete a watcher and its keystore (irreversible). `204` on success; `400` for a malformed `eid`. *(Known issue: an unknown but well-formed `eid` currently surfaces as a `500`, not a `404`.)* |
| `GET` | `/watchers/{eid}/status` | Latest per-witness key-state results for every AID the watcher has polled. `404` for an unknown `eid`, `400` if malformed. |
| `GET` | `/health` | Health check, returns `204 No Content`. |

The boot server is unauthenticated. Keep it on localhost / cluster-internal and never route it publicly.

### Watcher server (`localhost:7632`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/` | Submit a single KERI message with CESR attachments. The `CESR-Destination` header must be the target watcher's AID (`400` if missing, `404` if unknown). KEL/EXN/RPY messages are parsed into the watcher's keystore (`204`); QRY messages are answered inline (`200`, `application/json+cesr`, or `204` if there is nothing to return) and only if the querier is the watcher's controller; TEL and ACDC messages are rejected with `422`. |
| `PUT` | `/` | Push a raw CESR stream into the watcher's parser (`204`). Requires `CESR-Destination`. |
| `GET` | `/oobi/{aid}` | OOBI resolution for a **watcher** AID (`404` unless the watcher's own identity is fully witnessed). |
| `GET` | `/oobi/{aid}/{role}` | OOBI with role (e.g. `controller`). |
| `GET` | `/oobi/{aid}/{role}/{eid}` | OOBI with role and participant EID. |
| `GET` | `/oobi` | Always `404` (no default AID is configured). |

All watcher-server requests are rate-limited to 100 requests per 10-second window per client (`429` beyond that). *(Known issue: the limiter's client key is currently the first character of the client IP address rather than the full address, so clients can share a bucket.)* There is no `/health` route on the watcher server — use the boot server's, or `GET /oobi/<eid>/controller` for an external check.

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

The script also sets `KERI_BASER_MAP_SIZE=1099511627776` and raises the open-file limit (`ulimit -S -n 65536`) before launching.

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

Demonstrates provisioning a watcher and registering a watched AID. Requires `witopnet` running on `localhost:5631`/`5632`, the watcher service running on `localhost:7631`/`7632`, and `kli` (KERI CLI) and `jq` installed. It hard-codes the controller AID and witness OOBI produced by witness-hk's `scripts/controller.sh`.

```bash
source scripts/env.sh
./scripts/verifier.sh
```

Steps performed:
1. Initialises a `verifier` keystore and incepts the `verifier` AID
2. Provisions a new watcher via `POST /watchers` on the boot server and resolves the returned OOBI
3. Resolves the monitored controller's OOBI from the running witness
4. Registers the controller with the watcher via `kli watcher add`, which sends the watcher a controller-signed `/watcher/<eid>/add` reply. From then on the watcher polls that AID's witnesses.

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

Tests use temporary KERI keystores (`temp=True`) so no external services are required.

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
    ├── eventing.py             # QueryKeveryShim (HTTP) / KeveryQueryShim (TCP): query-only Kevery adapters
    ├── httping.py              # HttpEnd (KERI event HTTP endpoint) + Throttle middleware
    ├── oobing.py               # OOBIEnd (OOBI HTTP endpoint)
    └── tcp/serving.py          # Directant (TCP server) + Reactant — NOT currently wired into setup()
```

`app/watching.py` also contains `Sentinal`/`SentinalDoer` (the witness-polling logic) and the boot API endpoints. `CueDoer` and the `core/tcp` layer are retained from the witness codebase but are not started by `watching.setup()`, so the TCP port in `curls[1]` has no effect.

## How watching works

1. `POST /watchers` creates the watcher's identifier and records the controller AID it serves.
2. The controller (e.g. `kli watcher add`) posts its KEL and a signed `/watcher/<eid>/add` reply to `POST /` with `CESR-Destination: <eid>`; the reply carries the observed AID and an OOBI for it. The watcher resolves the OOBI to obtain the observed AID's KEL.
3. Every 30 s per enabled observed AID (60 s for the controller's own AID) a `Sentinal` asks each of that AID's witnesses for its key state and compares the sequence number and digest with the watcher's local KEL: same `sn`/digest → `even`; witness `sn` lower → `behind`; higher → `ahead`; same `sn` with different digest → `duplicitous`; no answer or missing witness endpoint → `unresponsive`. AIDs with no witnesses are skipped. If witnesses are ahead the watcher queries the missing events.
   Polling itself never changes the watcher's copy of the KEL (it only stores the witnesses' reported key state); the copy is seeded from the OOBI and KEL the controller supplied, and is otherwise advanced only by events the controller posts to the watcher or by this catch-up. The catch-up is a `SeqNoQuerier`, which uses keripy's `WitnessInquisitor` to send a `logs` query to one randomly chosen known endpoint for the AID (controller role first, then agent, then witness — not necessarily one of the witnesses that reported ahead). The events in the reply are processed like any other incoming KEL. Because no single source is treated as authoritative, the local copy and the witnesses can each disagree with the others; see `duplicitous` in the list above.
4. Results are stored per (watcher, AID, witness) and returned by `GET /watchers/{eid}/status`. Duplicity is currently only logged and reported in status; nothing is pushed to the controller.

## Container image and Helm chart

`docker/Dockerfile` builds the image (CI: `.github/workflows/build-push.yml`; see `docker/README.md`), and `charts/watcher-hk/` deploys it as a StatefulSet of independent nodes (`replicaCount` is the number of nodes, not watchers). The container entrypoint `docker/scripts/watopnet.sh` derives each pod's advertised host, `https://watcher-<ordinal>.<baseDomain>/`, writes `keri/cf/main/watopnet.json`, and binds the boot server to `0.0.0.0` (in-cluster only). See `charts/watcher-hk/README.md`.

## License

Apache-2.0. See [LICENSE](LICENSE).