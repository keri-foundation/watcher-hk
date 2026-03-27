#!/bin/bash

kli init --name verifier --salt 0ACDEyMzQ1Njc4OWxtbZvery --nopasscode --config-dir ${WATOPNET_SCRIPT_DIR} --config-file verifier
kli incept --name verifier --alias verifier --file ${WATOPNET_SCRIPT_DIR}/data/verifier.json

WATCHER=$(curl -s -XPOST http://localhost:7631/watchers -d'{"aid": "EMnf4sSkO1_F53mSDCgPnkG2XVuCTcRKy7EuZeoqKsZY"}' -H "Content-Type: application/json")
echo "${WATCHER}"
OOBI=$(echo "${WATCHER}" | jq -r .oobis[0])

kli oobi resolve --name verifier --oobi-alias watcher0 --oobi "${OOBI}"

kli oobi resolve --name verifier --oobi-alias controller --oobi http://localhost:5632/oobi/ENcOes8_t2C7tck4X4j61fSm0sWkLbZrEZffq7mSn8On/witness
kli watcher add --name verifier --alias verifier --watcher watcher0 --watched controller
