FROM python:3.11-slim AS builder

WORKDIR /app

# Копируем только файл зависимостей — это кэшируется отдельно
COPY requirements.txt .

# Устанавливаем зависимости в отдельную директорию
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---------- Стадия 2: финальный образ ----------
FROM python:3.11-slim

WORKDIR /app

# Копируем установленные зависимости из стадии builder
COPY --from=builder /install /usr/local

# Копируем код приложения
COPY app.py .

EXPOSE 5000

# Точка входа — gunicorn
ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

