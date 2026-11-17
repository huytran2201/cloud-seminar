# Dockerfile cho AIOps Worker (Isolation Forest + Flask)
FROM python:3.11-slim

WORKDIR /app

# Cài dependencies (scikit-learn cần build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY detector.py .

# Expose port cho Prometheus scrape metrics AI
EXPOSE 8001

CMD ["python", "detector.py"]
