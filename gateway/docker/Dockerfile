FROM python:3.11-slim
WORKDIR /app

# copy the gateway source directory into /app so gateway_app.py ends up at /app/gateway_app.py
COPY . /app/

# install FastAPI + runtime deps
RUN apt-get update -y \
 && apt-get install -y --no-install-recommends gcc libc-dev \
 && pip install --no-cache-dir fastapi uvicorn requests flask flask-cors web3 \
 && apt-get remove -y gcc libc-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

EXPOSE 9002
CMD ["uvicorn", "gateway_app:app", "--host", "0.0.0.0", "--port", "9002"]
