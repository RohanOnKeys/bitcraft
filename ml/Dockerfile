FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ml/ ./ml/

# datasets/ is mounted read-only by docker-compose; artifacts go to a volume.
CMD ["python", "-m", "ml.pipeline", "--datasets", "datasets", "--output", "ml/artifacts"]
