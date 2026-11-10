FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock.txt /app/requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt && useradd --uid 10001 --create-home studio
COPY backend /app/backend
COPY alembic.ini /app/alembic.ini
COPY deploy/container-backend.sh /app/entrypoint.sh
RUN mkdir -p /app/data && chown studio:studio /app/data && chmod +x /app/entrypoint.sh
USER studio
ENTRYPOINT ["/app/entrypoint.sh"]
