# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 KENNY_HOST=0.0.0.0 PORT=3000 KENNY_DATA_DIR=/data
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.lock; \
    else \
      pip install --no-cache-dir -r requirements.lock; \
    fi
RUN groupadd --gid 10001 kenny && useradd --uid 10001 --gid 10001 --no-create-home kenny && mkdir /data && chown kenny:kenny /data
COPY --chown=kenny:kenny . .
USER kenny
VOLUME ["/data"]
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:3000/api/health', timeout=3)" || exit 1
CMD ["python", "-m", "backend.server"]
