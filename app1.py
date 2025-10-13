import os
import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from docx import Document
from openpyxl import Workbook
from datetime import datetime

# --- Настройка базы данных ---
DATABASE_URL = os.environ.get('DATABASE_URL')  # PostgreSQL
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, 'database.db')
USE_POSTGRES = DATABASE_URL is not None

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXT = {'pdf', 'png', 'jpg', 'jpeg', 'docx'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change_this_to_secret')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- База данных ---
def get_db():
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        return conn
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Инициализация базы данных"""
    if USE_POSTGRES:
        conn = get_db()
        cur = conn.cursor()
        # Создаем таблицы минимально, остальные можно расширять
        cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password TEXT NOT NULL,
            role_id INTEGER NOT NULL REFERENCES roles(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        # Добавляем роли и admin
        cur.execute("SELECT COUNT(*) FROM roles")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO roles (name) VALUES ('admin'), ('manager'), ('client')")
        cur.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
        if cur.fetchone()[0] == 0:
            pw = generate_password_hash('AdminPass123')
            cur.execute("INSERT INTO users (username,email,password,role_id) VALUES (%s,%s,%s,%s)",
                        ('admin','admin@example.com',pw,1))
        conn.close()
    else:
        # SQLite
        from pathlib import Path
        sql_file = Path(BASE_DIR) / 'models.sql'
        if sql_file.exists():
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql = f.read()
            conn = get_db()
            conn.executescript(sql)
            cur = conn.cursor()
            # роли и admin
            cur.execute("SELECT COUNT(*) FROM roles")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO roles (name) VALUES ('admin'), ('manager'), ('client')")
            cur.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
            if cur.fetchone()[0] == 0:
                pw = generate_password_hash('AdminPass123')
                cur.execute("INSERT INTO users (username,email,password,role_id) VALUES (?,?,?,?)",
                            ('admin','admin@example.com',pw,1))
            conn.commit()
            conn.close()

# --- Вспомогательные функции ---
def current_user():
    if 'user_id' in session:
        conn = get_db()
        if USE_POSTGRES:
            import psycopg2.extras
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute("SELECT users.*, roles.name as role_name FROM users JOIN roles ON users.role_id=roles.id WHERE users.id=%s",(session['user_id'],))
            u = cur.fetchone()
            cur.close()
            conn.close()
            return dict(u) if u else None
        else:
            u = conn.execute("SELECT users.*, roles.name as role_name FROM users JOIN roles ON users.role_id=roles.id WHERE users.id=?",(session['user_id'],)).fetchone()
            conn.close()
            return u
    return None

def login_required(f):
    from functools import wraps
    @wraps(f)
    def inner(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return inner

def role_required(role_name):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            u = current_user()
            if not u or u['role_name'] != role_name:
                flash('Доступ запрещён')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return inner
    return decorator

# --- Публичные маршруты ---
@app.route('/')
def index():
    return render_template('index.html', user=current_user(), breadcrumbs=[('Главная', url_for('index'))])

@app.route('/about')
def about():
    return render_template('about.html', breadcrumbs=[('Главная', url_for('index')), ('О проекте', None)])

@app.route('/services')
def services():
    return render_template('services.html', breadcrumbs=[('Главная', url_for('index')), ('Услуги', None)])

@app.route('/pricing')
def pricing():
    return render_template('pricing.html', breadcrumbs=[('Главная', url_for('index')), ('Тарифы', None)])

@app.route('/docs')
def docs():
    return render_template('docs.html', breadcrumbs=[('Главная', url_for('index')), ('Документы', None)])

@app.route('/faq')
def faq():
    return render_template('faq.html', breadcrumbs=[('Главная', url_for('index')), ('Вопрос-ответ', None)])

@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        msg = request.form['message']
        conn = get_db()
        if USE_POSTGRES:
            cur = conn.cursor()
            cur.execute("INSERT INTO contacts (name,email,message) VALUES (%s,%s,%s)", (name,email,msg))
            cur.close()
            conn.close()
        else:
            conn.execute("INSERT INTO contacts (name,email,message) VALUES (?,?,?)",(name,email,msg))
            conn.commit()
            conn.close()
        flash('Сообщение отправлено')
        return redirect(url_for('contact'))
    return render_template('contact.html', breadcrumbs=[('Главная', url_for('index')), ('Контакты', None)])

# --- Auth (register/login/logout) ---
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        conn = get_db()
        try:
            if USE_POSTGRES:
                cur = conn.cursor()
                cur.execute("INSERT INTO users (username,email,password,role_id) VALUES (%s,%s,%s,%s)",
                            (username,email,password,3))
                cur.close()
                conn.close()
            else:
                conn.execute("INSERT INTO users (username,email,password,role_id) VALUES (?,?,?,?)",
                             (username,email,password,3))
                conn.commit()
                conn.close()
            flash('Регистрация прошла успешно. Войдите')
            return redirect(url_for('login'))
        except:
            flash('Имя пользователя занято')
    return render_template('register.html', breadcrumbs=[('Главная', url_for('index')), ('Регистрация', None)])

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        if USE_POSTGRES:
            import psycopg2.extras
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute("SELECT * FROM users WHERE username=%s",(username,))
            u = cur.fetchone()
            cur.close()
            conn.close()
        else:
            u = conn.execute("SELECT * FROM users WHERE username=?",(username,)).fetchone()
            conn.close()
        if u and check_password_hash(u['password'], password):
            session['user_id'] = u['id']
            session['username'] = u['username']
            flash('Вход выполнен')
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль')
    return render_template('login.html', breadcrumbs=[('Главная', url_for('index')), ('Вход', None)])

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли')
    return redirect(url_for('login'))

# --- Старт приложения ---
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
