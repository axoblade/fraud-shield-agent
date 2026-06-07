# Stage 1: Build React frontend
FROM node:22-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# Stage 2: Runtime, Python + Node.js (Node.js needed for MCP server via npx)
FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y nodejs npm curl --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g mongodb-mcp-server

WORKDIR /app

# Backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Built frontend (served by FastAPI via StaticFiles)
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Application code
COPY agent/ ./agent/
COPY api/ ./api/
COPY queries/ ./queries/

EXPOSE 8000
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
