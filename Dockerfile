FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .

# Устанавливаем зависимости в отдельную директорию
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY app.py .

EXPOSE 5000

# Точка входа — gunicorn
ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

