SHELL := /bin/bash

ROOT_DIR := $(CURDIR)
ANSIBLE_DIR := $(ROOT_DIR)/deploy/ansible
ANSIBLE_WRAPPER := $(ANSIBLE_DIR)/with-op-ssh-agent.sh
ANSIBLE_INVENTORY := inventories/pilot/hosts.yml
ANSIBLE_PLAYBOOK := ansible-playbook -i $(ANSIBLE_INVENTORY)
ANSIBLE_ADHOC := ansible -i $(ANSIBLE_INVENTORY)
ONEPASSWORD_SSH_AUTH_SOCK ?= $(HOME)/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock
WATCHER_HOST ?= watcher-do-01
WATCHER_LOG_LINES ?= 40

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available make targets
	@echo
	@echo "Available commands for watcher-hk:"
	@echo
	@awk 'BEGIN {FS = ":.*?##"; printf "Usage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_.-]+:.*?##/ { printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo

##@ Watcher Deployment

.PHONY: watcher-preflight
watcher-preflight: ## Validate 1Password-backed inventory values without opening SSH
	@cd "$(ANSIBLE_DIR)" && "$(ANSIBLE_WRAPPER)" --no-ssh-agent \
		$(ANSIBLE_PLAYBOOK) playbooks/watcher-preflight.yml

.PHONY: watcher-ping
watcher-ping: ## Check SSH connectivity to the configured watcher host
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$(ONEPASSWORD_SSH_AUTH_SOCK)" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -m ping'

.PHONY: watcher-check
watcher-check: ## Run preflight, ping, and bootstrap dry-run in one auth batch
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$(ONEPASSWORD_SSH_AUTH_SOCK)" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/watcher-preflight.yml && \
		$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -m ping && \
		$(ANSIBLE_PLAYBOOK) playbooks/watcher-bootstrap.yml --check --diff'

.PHONY: watcher-apply
watcher-apply: ## Run preflight and apply the watcher bootstrap in one auth batch
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$(ONEPASSWORD_SSH_AUTH_SOCK)" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/watcher-preflight.yml && \
		$(ANSIBLE_PLAYBOOK) playbooks/watcher-bootstrap.yml'

.PHONY: watcher-verify
watcher-verify: ## Run the post-bootstrap watcher verification playbook
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$(ONEPASSWORD_SSH_AUTH_SOCK)" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/watcher-verify.yml'

.PHONY: watcher-all
watcher-all: ## Run preflight, ping, apply, and verify in one auth batch
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$(ONEPASSWORD_SSH_AUTH_SOCK)" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/watcher-preflight.yml && \
		$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -m ping && \
		$(ANSIBLE_PLAYBOOK) playbooks/watcher-bootstrap.yml && \
		$(ANSIBLE_PLAYBOOK) playbooks/watcher-verify.yml'

.PHONY: watcher-status
watcher-status: ## Show systemd and Circus watcher status for the watcher host
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$(ONEPASSWORD_SSH_AUTH_SOCK)" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -b -m shell -a '\''systemctl status circusd-watcher --no-pager --lines=20; printf "\\n=== circusctl ===\\n"; /opt/watcher-hk/.venv/bin/circusctl --endpoint ipc:///var/run/watopnet-circus/ctrl.sock status'\'''

.PHONY: watcher-logs
watcher-logs: ## Tail watcher stdout and stderr logs from the host
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$(ONEPASSWORD_SSH_AUTH_SOCK)" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -b -m shell -a '\''printf "=== stdout ===\\n"; tail -n $(WATCHER_LOG_LINES) /var/log/watopnet/watcher/stdout.log; printf "\\n=== stderr ===\\n"; tail -n $(WATCHER_LOG_LINES) /var/log/watopnet/watcher/stderr.log'\'''