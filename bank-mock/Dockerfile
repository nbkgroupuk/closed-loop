FROM python:3.11-slim
WORKDIR /app
COPY bank_mock.py .
RUN pip install --no-cache-dir fastapi uvicorn
EXPOSE 9000
CMD ["uvicorn", "bank_mock:app", "--host", "0.0.0.0", "--port", "9000"]
