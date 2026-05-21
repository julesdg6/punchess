FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY server /app/server
COPY clients /app/clients
ENV PUNCHESS_PORT=2700 \
    PUNCHESS_REPORT_DIR=/app/reports \
    PUNCHESS_MOVE_TIMEOUT_SECONDS=30 \
    PUNCHESS_ILLEGAL_MOVE_LIMIT=1 \
    PUNCHESS_DISCONNECT_GRACE_SECONDS=10 \
    PUNCHESS_AUTO_START=true
EXPOSE 2700
CMD ["sh", "-c", "uvicorn server.app.main:app --host 0.0.0.0 --port ${PUNCHESS_PORT:-2700}"]
