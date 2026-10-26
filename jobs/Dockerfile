FROM python:3.12-slim
WORKDIR /app
COPY backend/ /app/backend/
RUN pip install --no-cache-dir ./backend
ENTRYPOINT ["python", "-m", "app.main"]
