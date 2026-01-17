FROM python:3.12.0-slim

WORKDIR /app

# Install system dependencies (no Google Cloud SDK)
RUN apt-get update && apt-get install -y \
    curl build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN python -m pip install --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app (place your baked models in the repo, e.g. `models/`, so they are included)
COPY . .

# Env and port
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# Run the app; allows overriding PORT at runtime with -e PORT=...
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
