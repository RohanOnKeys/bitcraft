FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000
# Load the latest ML artifacts (no-op failure if none yet), then serve.
CMD ["sh", "-c", "python -m app.loader || echo 'no artifacts loaded'; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
