# Этап 1: сборка интерфейса
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# Этап 2: API + собранный интерфейс
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
    PORT=8000 SUPPLYLINE_SANDBOX=1 SUPPLYLINE_MOCK_LATENCY=1 \
    SUPPLYLINE_DB=/tmp/supplyline/template.sqlite3 SUPPLYLINE_SESSIONS_DIR=/tmp/supplyline/sessions
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY adapters/ adapters/
COPY api/ api/
COPY db/__init__.py db/models.py db/seed.py db/
COPY engine/ engine/
COPY docs/model/SupplyLine_financial_model.xlsx docs/model/
COPY --from=web /web/dist web/dist
RUN useradd --create-home --uid 10001 app && mkdir -p /tmp/supplyline && chown app /tmp/supplyline
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health',timeout=2)"
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
