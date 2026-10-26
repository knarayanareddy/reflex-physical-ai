# Reflex — API image.
#
# Build from the REPOSITORY ROOT, not from jobs/:
#
#   docker build -f jobs/Dockerfile -t reflex:0.1.0 .
#
# Notes on the choices here:
#   * The base image is pinned to an exact patch release. Before submission, replace the
#     tag with the digest (`docker buildx imagetools inspect python:3.12.7-slim-bookworm`)
#     so "the same image" cannot become a different filesystem tomorrow. A floating
#     `python:3.12-slim` tag is not acceptable for a project whose thesis is reproducibility.
#   * Dependencies come from backend/uv.lock with --frozen, so the image matches the
#     lockfile rather than whatever resolves on build day.
#   * Runs as an unprivileged user; the ledger directory is a volume so the audit trail
#     survives the container.
FROM python:3.12.7-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    REFLEX_LEDGER_PATH=/data/runs/ledger.jsonl \
    REFLEX_VETO_LEDGER_PATH=/data/runs/veto-ledger.jsonl

WORKDIR /app

# Only what the build needs. The venv lives outside /app so the source tree stays clean.
COPY backend/uv.lock backend/pyproject.toml backend/README.md /app/backend/
RUN pip install --no-cache-dir uv==0.13.5 \
 && cd /app/backend && uv sync --frozen --no-dev --no-install-project

COPY backend/ /app/backend/
COPY schemas/ /app/schemas/
COPY data/ /app/data/
COPY LICENSE NOTICE /app/
RUN cd /app/backend && uv sync --frozen --no-dev

# The ledger and the veto ledger are the product's evidence; do not bake them in.
RUN groupadd --gid 10001 reflex \
 && useradd --uid 10001 --gid reflex --no-create-home --shell /usr/sbin/nologin reflex \
 && mkdir -p /data/runs && chown -R reflex:reflex /data
USER 10001:10001

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

ENTRYPOINT ["/app/backend/.venv/bin/python", "-m", "app.main"]
