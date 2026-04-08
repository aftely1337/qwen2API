# Stage 1: Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend + Final Image
FROM python:3.10-slim
WORKDIR /workspace

# Install system dependencies required for headless browser (Camoufox/Firefox)
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    libx11-xcb1 \
    libdbus-glib-1-2 \
    libxt6 \
    libgtk-3-0 \
    libasound2 \
    libpulse0 \
    libdrm2 \
    libgbm1 \
    libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN python -m camoufox fetch

COPY backend/ ./backend/
COPY start.py ./
COPY --from=frontend-builder /app/dist ./frontend/dist

# The API gateway port
EXPOSE 8080

# Environment defaults
ENV PORT=8080
ENV FRONTEND_DIST_DIR=/workspace/frontend/dist
ENV ACCOUNTS_FILE=/workspace/data/accounts.json
ENV USERS_FILE=/workspace/data/users.json
ENV CAPTURES_FILE=/workspace/data/captures.json
ENV PYTHONPATH=/workspace

CMD ["python", "-m", "backend.main"]
