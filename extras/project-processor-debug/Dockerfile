FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir fastapi uvicorn
CMD ["uvicorn", "iso_listener:app", "--host", "0.0.0.0", "--port", "9000"]
