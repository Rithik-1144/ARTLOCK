FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm ci --prefix frontend
COPY frontend ./frontend
RUN npm --prefix frontend run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY migrations /app/migrations
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist
WORKDIR /app/backend
EXPOSE 10000
CMD ["sh", "-c", "cd /app && flask --app backend/run.py db upgrade && exec gunicorn --chdir /app/backend -w 2 -b 0.0.0.0:${PORT} run:app"]
