FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
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
RUN chmod 0644 /etc/cron.d/kbo-cron
RUN crontab /etc/cron.d/kbo-cron

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
