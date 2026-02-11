FROM python:3.10-slim

WORKDIR /app

# Copy only worker files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker script
COPY worker.py .

ENV PYTHONUNBUFFERED=1
CMD ["python3", "-u", "worker.py"]


