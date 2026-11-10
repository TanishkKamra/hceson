# (c) 2026 Tanishk Kamra | All rights reserved | github.com/TanishkKamra/hceson | tkp-2603f7a67b-edc6a7󠁻󠁴󠁫󠁰󠀭󠀲󠀶󠀰󠀳󠁦󠀷󠁡󠀶󠀷󠁢󠀭󠁥󠁤󠁣󠀶󠁡󠀷󠁽
# Stage 1: build the React app
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: FastAPI serves the API and the built frontend from one container
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist ./static
RUN useradd --create-home app
USER app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
