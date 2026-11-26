# syntax=docker/dockerfile:1
# Multi-stage Dockerfile for UNIX Data Pipeline & Iragi Quality Engine

FROM python:3.14-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir iragi pytest


FROM python:3.14-slim-bookworm AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LC_ALL=C.UTF-8 \
    PATH="/opt/venv/bin:${PATH}"

# Install required UNIX filters, PostgreSQL client, gnuplot, jq, shellcheck, and ACL tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    acl \
    bash \
    coreutils \
    curl \
    gawk \
    git \
    gnuplot-nox \
    grep \
    jq \
    make \
    postgresql-client \
    sed \
    shellcheck \
    tar \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# Create non-root user and workspace structure with explicit permissions
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --create-home --shell /bin/bash appuser && \
    mkdir -p /workspace/data/raw /workspace/data/processed /workspace/data/reports \
             /workspace/data/visualizations /workspace/backups && \
    chown -R appuser:appgroup /workspace && \
    chmod -R 755 /workspace

WORKDIR /workspace
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import iragi" && jq --version >/dev/null && gnuplot --version >/dev/null || exit 1

CMD ["bash"]
