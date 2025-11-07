# Dockerfile (common pattern) - use this in backend/, gateway/, processor/ (adapt copy/entry)
FROM python:3.11

# create non-root user if you like (optional), set workdir
WORKDIR /app

# copy requirements and install (assumes requirements.txt present in the same folder)
COPY requirements.txt /app/requirements.txt

# Update apt and install build deps if needed (uncomment if your requirements need gcc)
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# install python deps
RUN pip install --no-cache-dir -r /app/requirements.txt

# copy app contents
COPY . /app

# set environment defaults (override at docker run)
ENV PYTHONUNBUFFERED=1

# default command - override at docker run if needed
# for backend we use app.server:app, for gateway app.server:app, processor may run its own entry
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]

FROM nginx:alpine
COPY . /usr/share/nginx/html
