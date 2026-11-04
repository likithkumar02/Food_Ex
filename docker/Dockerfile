FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --system --create-home app \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["gunicorn", "food_ex.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
