# Dieselben drei Schritte wie bei abstractaltitudes, nur ohne pnpm:
#
#   make dev    App örtlich aus der virtuellen Umgebung starten
#   make test   Abbild für diesen Rechner bauen und im Container prüfen
#   make prod   Abbild für die Synology bauen (linux/amd64) und veröffentlichen

.PHONY: dev test prod pruefen

dev:
	@./scripts/dev.sh

test:
	@./scripts/test.sh

prod:
	@./scripts/prod.sh

pruefen:
	@$${VENV:-$$HOME/.venvs/krankenkasse}/bin/python test_berechnung.py
	@$${VENV:-$$HOME/.venvs/krankenkasse}/bin/python pruefe_datenquellen.py
