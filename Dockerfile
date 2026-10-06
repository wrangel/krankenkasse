# syntax=docker/dockerfile:1
#
# Zwei Stufen wie beim Backend von abstractaltitudes: bauen mit allem, laufen mit
# wenig. Das Ergebnis enthält weder pip-Cache noch Build-Werkzeuge.

FROM python:3.13-slim AS build
WORKDIR /app

# Nur die Abhängigkeitsliste kopieren, damit die Installationsschicht so lange
# wiederverwendet wird, wie sich an ihr nichts ändert.
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt


FROM python:3.13-slim AS runtime

# Kein root, wie beim Backend von abstractaltitudes.
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

WORKDIR /app
COPY --from=build /install /usr/local

# Nur das, was zur Laufzeit gebraucht wird. Tests, Prüfskripte und die
# Werkzeuge zum Nachführen der Stammdaten gehören nicht ins Abbild.
COPY app.py basis.py oberflaeche.py ansicht_person.py ansicht_haushalt.py ./
COPY utils.py constants.py main.py ./
COPY versicherer.json praemienregionen.json ./

# Die BAG-Prämiendatei wird beim ersten Aufruf geladen und hier abgelegt. Als
# Volume eingehängt übersteht sie einen Neustart des Containers - sonst kostet
# jeder Start die rund sechs Sekunden zum Einlesen der 12-MB-Datei.
RUN mkdir -p /app/.cache && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8501

# Streamlit bringt einen eigenen Endpunkt für Lebenszeichen mit.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
