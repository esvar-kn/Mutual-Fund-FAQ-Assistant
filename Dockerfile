FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install build dependencies for chroma and sentence-transformers,
# plus curl/tar used to fetch the prebuilt vector index at startup
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files (see .dockerignore: no .env, no data/, no .git)
COPY . .
RUN chmod +x scripts/fetch_index.sh

# Set container environment settings
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose server port
EXPOSE 8080

# Fetch the prebuilt index published by CI, then serve.
# The index is not baked into the image, so a redeploy always picks up the
# latest published data without rebuilding.
CMD ./scripts/fetch_index.sh && uvicorn src.api:app --host 0.0.0.0 --port $PORT
