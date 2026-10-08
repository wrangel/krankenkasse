#!/bin/sh
# Warm the premium data before Streamlit accepts a single request.
#
# Parsing 220,000 rows out of the Excel file costs about six seconds on a fast
# machine and considerably more on the Synology. Without this, whoever arrives
# first after a cold start pays that, and the 12 MB download on top. Nobody
# should want to be that visitor.
#
# The cache volume already survives redeployment, so this only does real work
# on a genuinely cold start: the first deploy, or after the seven-day refresh
# in download_file. Otherwise it reads the pickle and returns in milliseconds.
#
# Deliberately non-fatal. If the BAG is unreachable the app still starts and
# shows the message in error.data_unavailable - an app that refuses to boot
# because a third party is down is worse than one that explains itself.
#
# The health endpoint only answers once Streamlit is up, which is after this
# finishes, so scripts/syno-deploy.sh waits for the warm-up rather than
# declaring success while the data is still loading.

echo "Warming the premium cache..."
if python -c "from calculation import load_premiums; load_premiums()" 2>&1; then
    echo "Premium data ready."
else
    echo "WARNING: could not load the premium data; starting anyway."
fi

exec streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
