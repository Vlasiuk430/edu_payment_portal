import os
import sqlite3
import re
import datetime
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from docx import Document
from openpyxl import Workbook
import csv
from io import StringIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXT = {'pdf', 'png', 'jpg', 'jpeg', 'docx'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change_this_to_secret')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(seed=True):
    conn = get_db()
    cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role_id INTEGER,
        FOREIGN KEY(role_id) REFERENCES roles(id)
    );
    CREATE TABLE IF NOT EXISTS tariffs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        fio TEXT,
        program TEXT,
        contract_number TEXT,
        amount REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        doc_type TEXT,
        uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        message TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        ip TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT,
        message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'open'
    );
    CREATE TABLE IF NOT EXISTS tariff_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tariff_id INTEGER,
        name TEXT,
        description TEXT,
        price REAL,
        changed_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    cur.execute("SELECT COUNT(*) FROM roles")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO roles (name) VALUES (?)", [('admin',), ('manager',), ('client',)])

    cur.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if cur.fetchone()[0] == 0:
        pw = generate_password_hash('AdminPass123')
        cur.execute("INSERT INTO users (username, email, password, role_id) VALUES (?, ?, ?, ?)", ('admin', 'admin@example.com', pw, 1))

    if seed:
        cur.execute("SELECT COUNT(*) FROM tariffs")
        if cur.fetchone()[0] == 0:
            cur.executemany("INSERT INTO tariffs (name, description, price) VALUES (?, ?, ?)", [
                ('Базовый', 'Базовый тариф для студентов', 1000.0),
                ('Стандарт', 'Стандартный пакет услуг', 2500.0),
                ('Премиум', 'Полный пакет с поддержкой', 5000.0),
            ])
    conn.commit()
    conn.close()

# Ensure DB on startup (Render)
try:
    init_db(seed=True)
    print("✅ Database initialized:", DB_PATH)
except Exception as e:
    print("⚠️ Database init failed:", e)

def current_user():
    if 'user_id' in session:
        conn = get_db()
        u = conn.execute("SELECT users.*, roles.name as role_name FROM users JOIN roles ON users.role_id=roles.id WHERE users.id = ?", (session['user_id'],)).fetchone()
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

# -------------------- Public pages --------------------
@app.route('/')
def index():
    conn = get_db()
    tariffs = conn.execute("SELECT * FROM tariffs ORDER BY price ASC").fetchall()
    conn.close()
    return render_template('index.html', user=current_user(), tariffs=tariffs, breadcrumbs=[('Главная', url_for('index'))])

@app.route('/about')
def about():
    return render_template('about.html', breadcrumbs=[('Главная', url_for('index')), ('О проекте', None)])

@app.route('/services')
def services():
    return render_template('services.html', breadcrumbs=[('Главная', url_for('index')), ('Услуги', None)])

@app.route('/pricing')
def pricing():
    conn = get_db()
    tariffs = conn.execute("SELECT * FROM tariffs ORDER BY price ASC").fetchall()
    conn.close()
    return render_template('pricing.html', tariffs=tariffs, breadcrumbs=[('Главная', url_for('index')), ('Тарифы', None)])

@app.route('/docs')
def docs():
    return render_template('docs.html', breadcrumbs=[('Главная', url_for('index')), ('Документы', None)])

@app.route('/faq')
def faq():
    return render_template('faq.html', breadcrumbs=[('Главная', url_for('index')), ('Вопрос-ответ', None)])

@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip()
        msg = request.form.get('message','').strip()
        if not name or not email or not msg:
            flash('Заполните все поля')
            return redirect(url_for('contact'))
        if not EMAIL_RE.match(email):
            flash('Некорректный email')
            return redirect(url_for('contact'))
        conn = get_db()
        conn.execute("INSERT INTO contacts (name, email, message) VALUES (?, ?, ?)", (name, email, msg))
        conn.commit()
        conn.close()
        flash('Сообщение отправлено. Спасибо!')
        return redirect(url_for('contact'))
    return render_template('contact.html', breadcrumbs=[('Главная', url_for('index')), ('Контакты', None)])

@app.route('/support')
def support():
    return render_template('services.html', breadcrumbs=[('Главная', url_for('index')), ('Поддержка', None)])

# -------------------- Auth --------------------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        email = request.form.get('email','').strip()
        password = request.form.get('password','').strip()
        if not username or not email or not password:
            flash('Заполните все поля')
            return redirect(url_for('register'))
        if not EMAIL_RE.match(email):
            flash('Некорректный email')
            return redirect(url_for('register'))
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username, email, password, role_id) VALUES (?, ?, ?, 3)", (username, email, generate_password_hash(password)))
            conn.commit()
            flash('Регистрация прошла успешно. Войдите.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Имя пользователя занято')
        finally:
            conn.close()
    return render_template('register.html', breadcrumbs=[('Главная', url_for('index')), ('Регистрация', None)])

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
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

# -------------------- Payments --------------------
@app.route('/pay', methods=['GET','POST'])
@login_required
def pay():
    conn = get_db()
    tariffs = conn.execute("SELECT * FROM tariffs ORDER BY price ASC").fetchall()
    conn.close()
    if request.method == 'POST':
        fio = request.form.get('fio','').strip()
        program = request.form.get('program','').strip()
        contract = request.form.get('contract','').strip()
        try:
            amount = float(request.form.get('amount', '0').strip())
        except:
            amount = 0.0
        if not fio or amount <= 0:
            flash('Проверьте ФИО и сумму')
            return redirect(url_for('pay'))
        conn = get_db()
        conn.execute("INSERT INTO payments (user_id, fio, program, contract_number, amount, created_at) VALUES (?, ?, ?, ?, ?, ?)", (session['user_id'], fio, program, contract, amount, datetime.datetime.now().isoformat()))
        conn.commit()
        payment_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        conn.close()
        log_action(session.get('user_id'), f'payment {amount}')
        flash('Платёж сохранён')
        return render_template('success.html', fio=fio, amount=amount, breadcrumbs=[('Главная', url_for('index')), ('Оплата', None)])
    return render_template('pay.html', tariffs=tariffs, breadcrumbs=[('Главная', url_for('index')), ('Оплата', None)])

# -------------------- Uploads --------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('Файл не выбран')
        return redirect(request.referrer or url_for('index'))
    f = request.files['file']
    if f.filename == '':
        flash('Пустой файл')
        return redirect(request.referrer or url_for('index'))
    if f and allowed_file(f.filename):
        fn = secure_filename(f.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
        f.save(path)
        conn = get_db()
        conn.execute("INSERT INTO documents (user_id, filename, doc_type) VALUES (?, ?, ?)", (session['user_id'], fn, fn.rsplit('.',1)[1]))
        conn.commit()
        conn.close()
        flash('Файл загружен')
        return redirect(request.referrer or url_for('index'))
    else:
        flash('Недопустимый формат')
    return redirect(url_for('index'))

@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# -------------------- Document generation --------------------
@app.route('/generate/invoice/<int:payment_id>')
@login_required
def gen_invoice(payment_id):
    conn = get_db()
    p = conn.execute("SELECT payments.*, users.username FROM payments JOIN users ON payments.user_id = users.id WHERE payments.id = ?", (payment_id,)).fetchone()
    conn.close()
    if not p:
        flash('Платёж не найден')
        return redirect(url_for('index'))
    doc = Document()
    doc.add_heading('Счёт на оплату', level=1)
    doc.add_paragraph(f"Клиент: {p['fio']}")
    doc.add_paragraph(f"Программа: {p['program']}")
    doc.add_paragraph(f"Сумма: {p['amount']} ₽")
    fname = f"invoice_{payment_id}_{int(datetime.datetime.now().timestamp())}.docx"
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    doc.save(fpath)
    conn = get_db()
    conn.execute("INSERT INTO documents (user_id, filename, doc_type) VALUES (?, ?, ?)", (session['user_id'], fname, 'docx'))
    conn.commit()
    conn.close()
    flash('Счёт создан')
    return redirect(url_for('uploaded_file', filename=fname))

@app.route('/generate/report.xlsx')
@role_required('manager')
def gen_report():
    conn = get_db()
    rows = conn.execute("SELECT id, fio, program, amount, created_at FROM payments").fetchall()
    conn.close()
    wb = Workbook()
    ws = wb.active
    ws.append(['ID','ФИО','Программа','Сумма','Дата'])
    for r in rows:
        ws.append([r['id'], r['fio'], r['program'], r['amount'], r['created_at']])
    fname = f"report_{int(datetime.datetime.now().timestamp())}.xlsx"
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    wb.save(fpath)
    conn = get_db()
    conn.execute("INSERT INTO documents (user_id, filename, doc_type) VALUES (?, ?, ?)", (session['user_id'], fname, 'xlsx'))
    conn.commit()
    conn.close()
    return redirect(url_for('uploaded_file', filename=fname))

# -------------------- Admin --------------------
@app.route('/admin')
@role_required('admin')
def admin_index():
    conn = get_db()
    stats = {
        'users': conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()['c'],
        'payments': conn.execute("SELECT COUNT(*) AS c FROM payments").fetchone()['c'],
        'documents': conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()['c'],
    }
    conn.close()
    return render_template('admin/admin_index.html', breadcrumbs=[('Админ', url_for('admin_index'))], user=current_user(), stats=stats)

@app.route('/admin/users')
@role_required('admin')
def admin_users():
    conn = get_db()
    users = conn.execute("SELECT users.*, roles.name as role_name FROM users JOIN roles ON users.role_id=roles.id").fetchall()
    roles = conn.execute("SELECT * FROM roles").fetchall()
    conn.close()
    return render_template('admin/users.html', users=users, roles=roles, breadcrumbs=[('Админ', url_for('admin_index')), ('Пользователи', None)])

@app.route('/admin/payments')
@role_required('admin')
def admin_payments():
    conn = get_db()
    pays = conn.execute("SELECT payments.*, users.username FROM payments JOIN users ON payments.user_id=users.id").fetchall()
    conn.close()
    return render_template('admin/payments.html', payments=pays, breadcrumbs=[('Админ', url_for('admin_index')), ('Платежи', None)])

@app.route('/admin/files')
@role_required('admin')
def admin_files():
    conn = get_db()
    docs = conn.execute("SELECT documents.*, users.username FROM documents LEFT JOIN users ON documents.user_id=users.id").fetchall()
    conn.close()
    return render_template('admin/files.html', docs=docs, breadcrumbs=[('Админ', url_for('admin_index')), ('Файлы', None)])

@app.route('/admin/reports')
@role_required('admin')
def admin_reports():
    conn = get_db()
    tariffs = conn.execute("SELECT * FROM tariffs").fetchall()
    conn.close()
    return render_template('admin/reports.html', tariffs=tariffs, breadcrumbs=[('Админ', url_for('admin_index')), ('Отчёты', None)])

# -------------------- Tariffs CRUD --------------------
@app.route('/tariffs')
def tariffs_list():
    conn = get_db()
    tariffs = conn.execute("SELECT * FROM tariffs ORDER BY price ASC").fetchall()
    conn.close()
    return render_template('tariffs/list.html', tariffs=tariffs, breadcrumbs=[('Тарифы', url_for('tariffs_list'))])

@app.route('/tariffs/create', methods=['GET','POST'])
@role_required('admin')
def tariffs_create():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        description = request.form.get('description','').strip()
        try:
            price = float(request.form.get('price','0').strip())
        except:
            price = -1
        if not name or price < 0:
            flash('Проверьте название и цену тарифа')
            return redirect(url_for('tariffs_create'))
        conn = get_db()
        conn.execute("INSERT INTO tariffs (name, description, price) VALUES (?, ?, ?)", (name, description, price))
        conn.commit()
        conn.close()
        flash('Тариф создан')
        return redirect(url_for('tariffs_list'))
    return render_template('tariffs/create.html', breadcrumbs=[('Тарифы', url_for('tariffs_list')), ('Создать', None)])

@app.route('/tariffs/<int:tid>/edit', methods=['GET','POST'])
@role_required('admin')
def tariffs_edit(tid):
    conn = get_db()
    t = conn.execute("SELECT * FROM tariffs WHERE id = ?", (tid,)).fetchone()
    if not t:
        conn.close()
        abort(404)
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        description = request.form.get('description','').strip()
        try:
            price = float(request.form.get('price','0').strip())
        except:
            price = -1
        if not name or price < 0:
            flash('Проверьте название и цену тарифа')
            return redirect(url_for('tariffs_edit', tid=tid))
        # save version BEFORE update
        save_tariff_version(tid, t['name'], t['description'], t['price'])
        conn.execute("UPDATE tariffs SET name=?, description=?, price=? WHERE id = ?", (name, description, price, tid))
        conn.commit()
        conn.close()
        flash('Тариф обновлён')
        return redirect(url_for('tariffs_list'))
    conn.close()
    return render_template('tariffs/edit.html', t=t, breadcrumbs=[('Тарифы', url_for('tariffs_list')), ('Редактировать', None)])

@app.route('/tariffs/<int:tid>/delete', methods=['POST'])
@role_required('admin')
def tariffs_delete(tid):
    conn = get_db()
    conn.execute("DELETE FROM tariffs WHERE id = ?", (tid,))
    conn.commit()
    conn.close()
    flash('Тариф удалён')
    return redirect(url_for('tariffs_list'))

def save_tariff_version(tid, name, description, price):
    conn = get_db()
    conn.execute("INSERT INTO tariff_versions (tariff_id, name, description, price, changed_at) VALUES (?, ?, ?, ?, ?)", (tid, name, description, price, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

@app.route('/tariffs/<int:tid>/history')
@role_required('admin')
def tariffs_history(tid):
    conn = get_db()
    versions = conn.execute("SELECT * FROM tariff_versions WHERE tariff_id = ? ORDER BY changed_at DESC", (tid,)).fetchall()
    tariff = conn.execute("SELECT * FROM tariffs WHERE id = ?", (tid,)).fetchone()
    conn.close()
    return render_template('tariffs/history.html', versions=versions, tariff=tariff, breadcrumbs=[('Тарифы', url_for('tariffs_list')), ('История', None)])

# -------------------- CSV import/export for payments --------------------
@app.route('/admin/payments/export_csv')
@role_required('admin')
def payments_export_csv():
    conn = get_db()
    rows = conn.execute("SELECT id, fio, program, amount, created_at FROM payments").fetchall()
    conn.close()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['id','fio','program','amount','created_at'])
    for r in rows:
        writer.writerow([r['id'], r['fio'], r['program'], r['amount'], r['created_at']])
    output = si.getvalue().encode('utf-8')
    return (output, 200, {'Content-Type': 'text/csv; charset=utf-8','Content-Disposition': 'attachment; filename="payments.csv"'})

@app.route('/admin/payments/import_csv', methods=['GET','POST'])
@role_required('admin')
def payments_import_csv():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f:
            flash('Файл не выбран')
            return redirect(url_for('payments_import_csv'))
        stream = StringIO(f.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)
        conn = get_db()
        count = 0
        for row in reader:
            try:
                conn.execute("INSERT INTO payments (user_id, fio, program, contract_number, amount, created_at) VALUES (?, ?, ?, ?, ?, ?)", (None, row.get('fio'), row.get('program'), row.get('contract_number'), float(row.get('amount') or 0), row.get('created_at') or datetime.datetime.now().isoformat()))
                count += 1
            except Exception as e:
                print('skip row', e)
        conn.commit()
        conn.close()
        flash(f'Импортировано {count} записей')
        return redirect(url_for('admin_payments'))
    return render_template('admin/import_payments.html', breadcrumbs=[('Админ', url_for('admin_index')), ('Импорт платежей', None)])

# -------------------- Notifications --------------------
def push_notification(user_id, title, message):
    conn = get_db()
    conn.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)", (user_id, title, message))
    conn.commit()
    conn.close()

@app.route('/notifications')
@login_required
def notifications_list():
    conn = get_db()
    notes = conn.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC", (session['user_id'],)).fetchall()
    conn.close()
    return render_template('notifications.html', notes=notes, breadcrumbs=[('Уведомления', url_for('notifications_list'))])

@app.route('/notifications/<int:nid>/read', methods=['POST'])
@login_required
def notification_read(nid):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (nid, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('notifications_list'))

# -------------------- User dashboard --------------------
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    pays = conn.execute("SELECT COUNT(*) AS c FROM payments WHERE user_id = ?", (session['user_id'],)).fetchone()['c']
    docs = conn.execute("SELECT COUNT(*) AS c FROM documents WHERE user_id = ?", (session['user_id'],)).fetchone()['c']
    conn.close()
    return render_template('user/dashboard.html', user=current_user(), payments_count=pays, documents_count=docs, breadcrumbs=[('Личный кабинет', url_for('dashboard'))])

@app.route('/dashboard/profile')
@login_required
def profile():
    return render_template('user/profile.html', user=current_user(), breadcrumbs=[('Личный кабинет', url_for('dashboard')), ('Профиль', None)])

@app.route('/dashboard/payments')
@login_required
def user_payments():
    conn = get_db()
    pays = conn.execute("SELECT * FROM payments WHERE user_id = ?", (session['user_id'],)).fetchall()
    conn.close()
    return render_template('user/payments.html', payments=pays, breadcrumbs=[('Личный кабинет', url_for('dashboard')), ('Платежи', None)])

@app.route('/dashboard/documents')
@login_required
def user_documents():
    conn = get_db()
    docs = conn.execute("SELECT * FROM documents WHERE user_id = ?", (session['user_id'],)).fetchall()
    conn.close()
    return render_template('user/documents.html', docs=docs, breadcrumbs=[('Личный кабинет', url_for('dashboard')), ('Документы', None)])

@app.route('/dashboard/support')
@login_required
def user_support():
    conn = get_db()
    tickets = conn.execute("SELECT * FROM support_tickets WHERE user_id = ?", (session['user_id'],)).fetchall()
    conn.close()
    return render_template('user/support.html', tickets=tickets, breadcrumbs=[('Личный кабинет', url_for('dashboard')), ('Поддержка', None)])

# -------------------- Utilities --------------------
def log_action(user_id, action):
    conn = get_db()
    ip = request.remote_addr if request else '127.0.0.1'
    conn.execute("INSERT INTO logs (user_id, action, ip, created_at) VALUES (?, ?, ?, ?)", (user_id, action, ip, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

# -------------------- Error handlers --------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', breadcrumbs=[('Ошибка', None)]), 404

@app.errorhandler(500)
def server_error(e):
    try:
        return render_template('500.html', breadcrumbs=[('Ошибка', None)]), 500
    except Exception:
        return "<h1>Ошибка 500</h1><p>Произошла ошибка на сервере.</p>", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
