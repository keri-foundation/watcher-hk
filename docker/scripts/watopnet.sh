#!/bin/bash
# Container entrypoint for a single watcher-hk (watopnet) replica running as one pod
# in a StatefulSet. Each replica multiplexes an arbitrary number of watcher identities
# provisioned at runtime via POST /watchers, so the only thing that varies per replica
# is the externally-advertised hostname, which is derived here from the pod's ordinal
# rather than passed in per-replica by the chart.
#
# Required env vars (set by the Helm chart):
#   WATOPNET_BASE_DOMAIN   Base domain for per-instance hostnames. This pod becomes
#                          reachable at watcher-<ordinal>.<WATOPNET_BASE_DOMAIN>.
#   WATOPNET_HTTP_PORT     Watcher server port (see .Values.ports.watcher).
#   WATOPNET_BOOT_PORT     Boot/management server port (see .Values.ports.boot).
set -euo pipefail

# A StatefulSet sets $HOSTNAME to "<statefulset-name>-<ordinal>" automatically.
ordinal="${HOSTNAME##*-}"
external_host="watcher-${ordinal}.${WATOPNET_BASE_DOMAIN}"

# keripy's Configer resolves config at {config-dir}/keri/cf/{base}/{name}.json with
# base="main" (default) and name="watopnet" — hence the "main/" segment below.
mkdir -p /usr/local/var/keri/cf/main
dt="$(date -u +%Y-%m-%dT%H:%M:%S.%6N+00:00)"
cat > /usr/local/var/keri/cf/main/watopnet.json <<EOF
{
  "dt": "${dt}",
  "watopnet": {
    "dt": "${dt}",
    "curls": ["https://${external_host}/"]
  }
}
EOF

# Refresh the seed OOBI list baked into the image onto the PVC-backed config dir on
# every start, so upgrading the image also updates the seed file already on disk.
cp /app/watcher-hk/scripts/keri/cf/main/watcher-oobis.json /usr/local/var/keri/cf/main/watcher-oobis.json

# Can't be set from outside the container reliably; production runs this at process
# start for the same reason (scripts/watopnet-sample.sh).
ulimit -S -n 65536

# TLS is terminated at the Ingress, matching how curls above is "https://" while this
# process itself only speaks HTTP. Boot host binds 0.0.0.0 (not 127.0.0.1) so the
# kubelet's readiness/liveness probes, which hit the pod IP from outside the container's
# network namespace, can reach it — the boot port is still never exposed by a Service
# or Ingress outside the cluster.
exec watopnet start \
  --config-dir /usr/local/var \
  --host 0.0.0.0 \
  --http "${WATOPNET_HTTP_PORT}" \
  --boothost 0.0.0.0 \
  --bootport "${WATOPNET_BOOT_PORT}"
