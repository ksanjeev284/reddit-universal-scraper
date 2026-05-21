FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies (for some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY main.py .
COPY config.py .
COPY analytics/ ./analytics/
COPY alerts/ ./alerts/
COPY dashboard/ ./dashboard/
COPY export/ ./export/
COPY scheduler/ ./scheduler/
COPY scraper/ ./scraper/
COPY search/ ./search/
COPY plugins/ ./plugins/
COPY api/ ./api/
COPY docs/ ./docs/

# Create data directory with subdirectories
RUN mkdir -p data/backups data/parquet

# Expose ports
# 8501 = Streamlit Dashboard
# 8000 = REST API
EXPOSE 8501 8000

# Health check for API mode
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start Streamlit dashboard
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
