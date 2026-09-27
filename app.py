import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
load_dotenv()
app = Flask(__name__)

# Собираем строку подключения из переменных окружения
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Visit(db.Model):
    __tablename__ = "visits"

    id = db.Column(db.Integer, primary_key=True)
    visited_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ip_address = db.Column(db.String(45), nullable=False)


@app.route("/hello", methods=["GET"])
def hello():
    # 1. Текущее время
    now = datetime.utcnow()

    # 2. IP-адрес клиента 
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    # 3. Сохраняем запись
    visit = Visit(visited_at=now, ip_address=ip)
    db.session.add(visit)
    db.session.commit()

    # 4. Возвращаем 200 OK с телом "Hello"
    return "Hello", 200


# Создание таблиц при старте приложения
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
