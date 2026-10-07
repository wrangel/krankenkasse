# The same three steps as in abstractaltitudes, just without pnpm:
#
#   make dev    run the app locally from the virtual environment
#   make test   build an image for this machine and check it in a container
#   make prod   build the image for the Synology (linux/amd64) and publish it

.PHONY: dev test prod check

dev:
	@./scripts/dev.sh

test:
	@./scripts/test.sh

prod:
	@./scripts/prod.sh

check:
	@$${VENV:-$$HOME/.venvs/viaprima}/bin/python test_calculation.py
	@$${VENV:-$$HOME/.venvs/viaprima}/bin/python check_data_sources.py
