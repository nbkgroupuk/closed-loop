# processor/Dockerfile
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install common system build deps for wheels (cryptography, psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ libpq-dev libssl-dev libffi-dev python3-dev curl git \
    && rm -rf /var/lib/apt/lists/*

# pip upgrade
RUN python -m pip install --upgrade pip setuptools wheel

# copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . ./app/app/app

# default command (you may override at run)
CMD ["sh", "-c", "uvicorn app.server:app --host 0.0.0.0 --port 8000"]

COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]










