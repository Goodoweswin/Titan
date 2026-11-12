# Multiarch index resolved from the official registry on 2026-11-12.
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY deploy/accounts/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && groupadd -g 10001 accounts && useradd -u 10001 -g accounts -M accounts
COPY --chown=10001:10001 services/accounts /app
COPY --chown=10001:10001 deploy/accounts/scripts/worker.py /app/worker.py
COPY --chown=10001:10001 deploy/accounts/scripts/entrypoint.sh /app/entrypoint.sh
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "2", "--timeout", "30", "--max-requests", "500", "--max-requests-jitter", "50", "--forwarded-allow-ips", "", "--error-logfile", "-"]
