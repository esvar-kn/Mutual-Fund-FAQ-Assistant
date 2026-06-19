FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install build dependencies for chroma and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set container environment settings
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose server port
EXPOSE 8080

# Run uvicorn server
CMD uvicorn src.api:app --host 0.0.0.0 --port $PORT
