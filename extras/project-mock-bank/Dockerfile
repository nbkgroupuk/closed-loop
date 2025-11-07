FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir fastapi uvicorn
CMD ["uvicorn", "bank_app:app", "--host", "0.0.0.0", "--port", "5002"]
