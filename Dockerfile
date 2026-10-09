FROM python:3.11-slim

WORKDIR /app

# Ensure tzdata, sqlite3 and curl are available
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=America/Santo_Domingo
ENV PORT=8000
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

COPY . /app

# Expose HTTP port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/ || exit 1

CMD ["python3", "app.py"]
