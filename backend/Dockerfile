FROM python:3.11-slim-bookworm

# Install system deps from stable bookworm repos (no flaky trixie mirrors)
RUN apt-get update && apt-get install -y --no-install-recommends \
        default-libmysqlclient-dev \
        build-essential \
        pkg-config \
        libmagic1 \
        ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY . .

RUN mkdir -p logs media staticfiles

EXPOSE 8000
