# The reviewed source is recompiled INSIDE the build, so deployment cannot
# accidentally use out-of-date generated HTML from another commit.
FROM python:3.13-slim AS frontend-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends libcairo2 \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir 'Pillow>=11,<13' 'CairoSVG>=2.7,<3'
COPY build_frontend.py /build/
COPY source/ /build/source/
COPY static/ /build/static/
RUN python build_frontend.py

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt \
 && useradd -r -u 10001 -g users actcalc \
 && mkdir -p /data \
 && chown actcalc:users /data
COPY backend/ /app/backend/
COPY --from=frontend-builder /build/static/ /app/static/
USER actcalc
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1"]
