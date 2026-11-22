SHELL:=/bin/bash
MAKEFLAGS += --silent

.PHONY: host-env
host-env:
	uv venv --allow-existing
	uv pip install -r requirements.txt

.PHONY: sim-build sim-on sim-off sim-logs sim-enter
sim-build:
	bash docker_sim/host-build.sh

sim-on:
	bash docker_sim/host-on.sh

sim-off:
	bash docker_sim/host-off.sh

sim-logs:
	bash docker_sim/host-logs.sh

sim-enter:
	bash docker_sim/host-enter.sh
