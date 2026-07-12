FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .
RUN pip install --no-cache-dir -e .

# Build both benchmarks at image-build time
RUN python -m rs_rating.cli --update && \
    python -m rs_rating.cli --update --market india

EXPOSE 8000

CMD ["uvicorn", "rs_rating.api:app", "--host", "0.0.0.0", "--port", "8000"]
