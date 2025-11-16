FROM python:3.11-slim
WORKDIR /app

# copy everything first
COPY . /app

# install requirements if present
RUN if [ -f /app/requirements.txt ]; then pip install --no-cache-dir -r /app/requirements.txt; fi

ENV PYTHONUNBUFFERED=1

# ✅ add this line
COPY app/server.py /app/server.py

# start the processor fastapi app
CMD ["python", "run_server.py"]
FROM python:3.11-slim
WORKDIR /app

# copy everything first (works whether compose build context is project root or ./processor)
COPY . /app

# install requirements if present
RUN if [ -f /app/requirements.txt ]; then pip install --no-cache-dir -r /app/requirements.txt; fi

ENV PYTHONUNBUFFERED=1

# start the processor fastapi app (file: processor/app/app/server.py -> module path app.server)
CMD ["python", "run_server.py"]
