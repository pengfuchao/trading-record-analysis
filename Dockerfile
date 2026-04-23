FROM python:3.11-slim

WORKDIR /app

# psycopg2-binary ships its own libpq, so no extra system packages needed.
# If you switch to psycopg2 (non-binary), add: libpq-dev gcc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Repo root must be the working directory so src.main.python.* imports resolve
# and src/main/resources/config/ paths are correct.
ENV PYTHONPATH=/app

EXPOSE 8000

RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["./docker-entrypoint.sh"]
