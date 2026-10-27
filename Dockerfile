FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
  PORT=10000 \
  APP_ENV=production \
  COOKIE_SECURE=true \
  SEED_DEMO_DATA=false \
  SESSION_TTL_SECONDS=28800

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd --system app && useradd --system --gid app --home-dir /app app
COPY --chown=app:app . .
RUN mkdir -p /app/data && chown -R app:app /app/data

USER app
EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '10000') + '/api/health', timeout=2)" || exit 1

CMD ["python", "server.py"]
