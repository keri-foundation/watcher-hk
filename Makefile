SHELL := /bin/bash

ROOT_DIR := $(CURDIR)
ANSIBLE_DIR := $(ROOT_DIR)/ansible
ANSIBLE_WRAPPER := $(ANSIBLE_DIR)/with-op-ssh-agent.sh
ANSIBLE_INVENTORY := inventories/pilot/hosts.yml
ANSIBLE_PLAYBOOK := ansible-playbook -i $(ANSIBLE_INVENTORY)
ANSIBLE_ADHOC := ansible -i $(ANSIBLE_INVENTORY)
ONEPASSWORD_SSH_AUTH_SOCK ?= $(HOME)/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock
WATCHER_HOST ?= watcher-do-01
WATCHER_LOG_LINES ?= 40
WATCHER_SYSTEMD_SERVICE := circusd-watcher
WATCHER_SYSTEMD_UNIT := /etc/systemd/system/circusd-watcher.service
WATCHER_CIRCUSCTL_BIN := /opt/watcher-hk/.venv/bin/circusctl
WATCHER_CIRCUS_ENDPOINT := ipc:///var/run/watopnet-circus/ctrl.sock
WATCHER_STDOUT_LOG := /var/log/watopnet/watcher/stdout.log
WATCHER_STDERR_LOG := /var/log/watopnet/watcher/stderr.log

define require_watcher_host
[[ "$(WATCHER_HOST)" =~ ^[A-Za-z0-9_.-]+$$ ]] || { \
	echo "Invalid WATCHER_HOST: $(WATCHER_HOST)" >&2; \
	echo "Expected a single inventory hostname containing only letters, digits, dot, underscore, or dash." >&2; \
	exit 1; \
}
endef

define require_watcher_log_lines
[[ "$(WATCHER_LOG_LINES)" =~ ^[1-9][0-9]*$$ ]] || { \
	echo "Invalid WATCHER_LOG_LINES: $(WATCHER_LOG_LINES)" >&2; \
	echo "Expected WATCHER_LOG_LINES to be a positive integer." >&2; \
	exit 1; \
}
endef

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
	@$(require_watcher_host)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -m ping'

.PHONY: watcher-check
watcher-check: ## Run preflight, ping, and bootstrap dry-run in one auth batch
	@$(require_watcher_host)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/watcher-preflight.yml && \
		$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -m ping && \
		$(ANSIBLE_PLAYBOOK) playbooks/watcher-bootstrap.yml --check --diff'

.PHONY: watcher-apply
watcher-apply: ## Run preflight and apply the watcher bootstrap in one auth batch
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/watcher-preflight.yml && \
		$(ANSIBLE_PLAYBOOK) playbooks/watcher-bootstrap.yml'

.PHONY: watcher-verify
watcher-verify: ## Run the post-bootstrap watcher verification playbook
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/watcher-verify.yml'

.PHONY: watcher-all
watcher-all: ## Run preflight, ping, apply, and verify in one auth batch
	@$(require_watcher_host)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/watcher-preflight.yml && \
		$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -m ping && \
		$(ANSIBLE_PLAYBOOK) playbooks/watcher-bootstrap.yml && \
		$(ANSIBLE_PLAYBOOK) playbooks/watcher-verify.yml'

.PHONY: watcher-status
watcher-status: ## Show systemd and Circus watcher status for the watcher host
	@$(require_watcher_host)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -b -m shell -a '\''systemctl status $(WATCHER_SYSTEMD_SERVICE) --no-pager --lines=20; printf "\\n=== circusctl ===\\n"; $(WATCHER_CIRCUSCTL_BIN) --endpoint $(WATCHER_CIRCUS_ENDPOINT) status'\'''

.PHONY: watcher-systemd-verify
watcher-systemd-verify: ## Run systemd-analyze verify for the watcher unit on the host
	@$(require_watcher_host)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -b -m shell -a '\''systemd-analyze verify $(WATCHER_SYSTEMD_UNIT)'\'''

.PHONY: watcher-logs
watcher-logs: ## Tail watcher stdout and stderr logs from the host
	@$(require_watcher_host)
	@$(require_watcher_log_lines)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WATCHER_HOST)" -b -m shell -a '\''printf "=== stdout ===\\n"; tail -n $(WATCHER_LOG_LINES) $(WATCHER_STDOUT_LOG); printf "\\n=== stderr ===\\n"; tail -n $(WATCHER_LOG_LINES) $(WATCHER_STDERR_LOG)'\'''