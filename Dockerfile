# Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN groupadd -r opentrace && useradd -r -g opentrace opentrace

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Sanity check: ensure frontend files are included in the build context
# Fail fast with clear message so build logs reveal missing files
RUN if [ ! -f frontend/index.html ]; then echo "ERROR: frontend/index.html missing in build context"; echo "Contents of /app:"; ls -la /app || true; echo "Contents of /app/frontend (if any):"; ls -la /app/frontend || true; exit 1; fi

# Change ownership to non-root user
RUN chown -R opentrace:opentrace /app

# Switch to non-root user
USER opentrace

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run the application
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]