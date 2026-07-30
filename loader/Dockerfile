FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y \
        libeccodes0 \
        unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY load_era5_land.py .

ENTRYPOINT ["python", "load_era5_land.py"]