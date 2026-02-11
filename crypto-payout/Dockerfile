FROM python:3.11-slim
WORKDIR /app

# Copy the crypto-payout entrypoint and also the main app source
COPY . .

RUN pip install --no-cache-dir fastapi uvicorn requests web3 web3
RUN pip install --no-cache-dir fastapi uvicorn prometheus-client

CMD ["uvicorn", "crypto_app:app", "--host", "0.0.0.0", "--port", "9001"]
