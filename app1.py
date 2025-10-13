import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request

app = Flask(__name__)

# Подключение к PostgreSQL через DATABASE_URL
def get_db():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL не задана в переменных окружения")
    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    return conn

# Инициализация базы (создание таблицы)
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100)
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

# Простой API
@app.route("/")
def index():
    return "Edu Payment Portal is running!"

@app.route("/students", methods=["GET", "POST"])
def students():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        data = request.json
        cur.execute(
            "INSERT INTO students (name, email) VALUES (%s, %s) RETURNING id",
            (data["name"], data["email"])
        )
        student_id = cur.fetchone()["id"]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"id": student_id, "name": data["name"], "email": data["email"]}), 201
    else:
        cur.execute("SELECT * FROM students")
        students = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(students)

if __name__ == "__main__":
    # Инициализация базы при старте
    init_db()
    
    # Используем порт Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
