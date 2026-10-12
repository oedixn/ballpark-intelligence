FROM python:3.11-slim-bookworm

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -o Acquire::Retries=3 \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        cron \
        wget \
        unzip \
        curl \
        gnupg \
        chromium \
        chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY crontab /etc/cron.d/kbo-cron
RUN chmod 0644 /etc/cron.d/kbo-cron \
    && crontab /etc/cron.d/kbo-cron

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
