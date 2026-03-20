FROM python:3.11-slim
WORKDIR /app
COPY worker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY worker /app/worker
CMD ["python", "worker/worker.py"]
