# Reusable Python/dbt image for pi_dbt CI.
# Pins the same interpreter and packages that pi_dbt currently
# installs on every GitLab/GitHub job (python:3.11-slim + dbt-bigquery).
FROM python:3.11-slim

LABEL org.opencontainers.image.title="dbt" \
      org.opencontainers.image.description="Python 3.11 + dbt-bigquery for pi_dbt CI" \
      org.opencontainers.image.source="https://github.com/predictive-paul/python_dbt_image"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# git is required for `dbt deps` (dbt Hub packages).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

CMD ["dbt", "--version"]
