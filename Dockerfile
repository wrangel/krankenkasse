# syntax=docker/dockerfile:1
#
# Two stages, like the abstractaltitudes backend: build with everything, run
# with little. The result carries neither a pip cache nor build tools.

FROM python:3.13-slim AS build
WORKDIR /app

# Copy only the dependency list, so the install layer is reused for as long as
# nothing in it changes.
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt


FROM python:3.13-slim AS runtime

# No root, as in the abstractaltitudes backend.
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

WORKDIR /app
COPY --from=build /install /usr/local

# Only what is needed at runtime. Tests, check scripts and the tools for
# refreshing the reference data do not belong in the image.
COPY app.py common.py theme.py persistence.py i18n.py ./
COPY view_person.py view_household.py ./
COPY calculation.py constants.py main.py ./
COPY data/insurers.json data/premium_regions.json ./data/
COPY locales/ ./locales/
COPY scripts/docker-entrypoint.sh ./

# The BAG premium file is fetched on first use and stored here. Mounted as a
# volume it survives a container restart - otherwise every start costs the six
# or so seconds needed to parse the 12 MB file.
RUN mkdir -p /app/.cache && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8501

# Streamlit ships its own liveness endpoint.
#
# The start period covers the entrypoint's warm-up, not just Streamlit booting.
# A genuinely cold start downloads 12 MB and parses 220,000 rows, which on the
# Synology is minutes rather than seconds; at 40s Docker would call the
# container unhealthy while it was doing exactly what it should.
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# The entrypoint warms the premium cache first, so the first visitor after a
# cold start does not wait for a 12 MB download and a 220,000-row parse.
CMD ["./docker-entrypoint.sh"]
