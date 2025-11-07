FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir fastapi uvicorn requests
CMD ["uvicorn", "crypto_app:app", "--host", "0.0.0.0", "--port", "9001"]
