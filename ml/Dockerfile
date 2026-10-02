FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ml/ ./ml/

# datasets/ is mounted from the host by docker-compose; artifacts go to a
# volume. Missing datasets are fetched from the GitHub release (SHA-256
# verified) on the first run; files already present are never downloaded.
CMD ["sh", "-c", "python -m ml.dataset download && exec python -m ml.pipeline --datasets datasets --output ml/artifacts"]
