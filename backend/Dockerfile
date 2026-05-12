FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

COPY --from=builder /root/.local /home/appuser/.local

ENV PATH=/home/appuser/.local/bin:$PATH

COPY requirements.txt .
COPY config.py .
COPY database.py .
COPY main.py .
COPY api/ ./api/
COPY checkers/ ./checkers/
COPY core/ ./core/
COPY middleware/ ./middleware/
COPY migrations/ ./migrations/
COPY models/ ./models/
COPY schemas/ ./schemas/
COPY services/ ./services/
COPY tasks/ ./tasks/
COPY templates/ ./templates/
COPY utils/ ./utils/
COPY websocket/ ./websocket/
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health').read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
