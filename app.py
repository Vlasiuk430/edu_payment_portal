import os, sqlite3, re, datetime
from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import stripe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change_this_to_secret')

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_replace_me')
STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', 'pk_test_replace_me')
STRIPE_CURRENCY = os.environ.get('STRIPE_CURRENCY', 'usd')

EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(seed=True):
    conn = get_db()
    cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role_id INTEGER);
    CREATE TABLE IF NOT EXISTS tariffs (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, price REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, fio TEXT, program TEXT, contract_number TEXT, amount REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, stripe_session_id TEXT, status TEXT DEFAULT 'created');
    CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    # seed base
    cur.execute("SELECT COUNT(*) FROM roles")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO roles (name) VALUES (?)", [('admin',), ('manager',), ('client',)])
    cur.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO users (username,email,password,role_id) VALUES (?,?,?,1)",
                    ('admin','admin@example.com', generate_password_hash('AdminPass123')))
    if seed:
        cur.execute("SELECT COUNT(*) FROM tariffs")
        if cur.fetchone()[0] == 0:
            cur.executemany("INSERT INTO tariffs (name, description, price) VALUES (?,?,?)", [
                ('Бакалавриат (очная форма)','Оплата за семестр обучения по программам бакалавриата очной формы',82000.0),
                ('Бакалавриат (заочная форма)','Оплата за семестр обучения по программам бакалавриата заочной формы',46000.0),
                ('Магистратура','Оплата за семестр обучения по магистерским программам',95000.0),
                ('Переподготовка и повышение квалификации','Стоимость курса профессиональной переподготовки / повышения квалификации',25000.0),
            ])
    conn.commit(); conn.close()

try:
    init_db(seed=True)
    print('✅ Database initialized:', DB_PATH)
except Exception as e:
    print('⚠️ DB init failed:', e)

def current_user():
    if 'user_id' in session:
        conn = get_db()
        u = conn.execute("SELECT users.*, roles.name as role_name FROM users LEFT JOIN roles ON users.role_id=roles.id WHERE users.id = ?", (session['user_id'],)).fetchone()
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

@app.route('/')
def index():
    conn = get_db()
    tariffs = conn.execute("SELECT * FROM tariffs ORDER BY price DESC").fetchall()
    conn.close()
    return render_template('index.html', user=current_user(), tariffs=tariffs, breadcrumbs=[('Главная', url_for('index'))])

@app.route('/tuition')
def tuition():
    conn = get_db()
    tariffs = conn.execute("SELECT * FROM tariffs ORDER BY price DESC").fetchall()
    conn.close()
    return render_template('tuition.html', tariffs=tariffs, breadcrumbs=[('Главная', url_for('index')), ('Оплата обучения', None)])

# старый маршрут /pricing для совместимости
@app.route('/pricing')
def pricing_alias():
    return redirect(url_for('tuition'))

@app.route('/faq')
def faq():
    return render_template('faq.html', breadcrumbs=[('Главная', url_for('index')), ('FAQ', None)])

@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip()
        msg = request.form.get('message','').strip()
        if not name or not email or not msg:
            flash('Заполните все поля'); return redirect(url_for('contact'))
        if not EMAIL_RE.match(email):
            flash('Некорректный email'); return redirect(url_for('contact'))
        conn = get_db()
        conn.execute("INSERT INTO contacts (name,email,message) VALUES (?,?,?)",(name,email,msg))
        conn.commit(); conn.close()
        flash('Сообщение отправлено. Спасибо!'); return redirect(url_for('contact'))
    return render_template('contact.html', breadcrumbs=[('Главная', url_for('index')), ('Контакты', None)])

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        email = request.form.get('email','').strip()
        password = request.form.get('password','').strip()
        if not username or not email or not password:
            flash('Заполните все поля'); return redirect(url_for('register'))
        if not EMAIL_RE.match(email):
            flash('Некорректный email'); return redirect(url_for('register'))
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username,email,password,role_id) VALUES (?,?,?,3)",
                         (username,email,generate_password_hash(password)))
            conn.commit(); flash('Регистрация прошла успешно. Войдите.')
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
        u = conn.execute("SELECT * FROM users WHERE username=?",(username,)).fetchone()
        conn.close()
        if u and check_password_hash(u['password'], password):
            session['user_id'] = u['id']; session['username'] = u['username']
            flash('Вход выполнен'); return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль')
    return render_template('login.html', breadcrumbs=[('Главная', url_for('index')), ('Вход', None)])

@app.route('/logout')
def logout():
    session.clear(); flash('Вы вышли'); return redirect(url_for('login'))

# Stripe checkout (Оплата обучения)
@app.route('/checkout/<int:tariff_id>')
def checkout(tariff_id):
    # доступ даже без авторизации, но можем потребовать вход
    # if 'user_id' not in session:
    #     flash('Войдите, чтобы оплатить'); return redirect(url_for('login'))
    conn = get_db()
    t = conn.execute("SELECT * FROM tariffs WHERE id=?", (tariff_id,)).fetchone()
    conn.close()
    if not t:
        flash('Направление не найдено'); return redirect(url_for('tuition'))

    # черновик платежа (user_id может быть None)
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO payments (user_id,fio,program,amount,status) VALUES (?,?,?,?,?)",
                (session.get('user_id'), session.get('username'), t['name'], float(t['price']), 'created'))
    payment_id = cur.lastrowid; conn.commit(); conn.close()

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': STRIPE_CURRENCY,
                'product_data': {'name': f"Оплата обучения — {t['name']} (семестр)"},
                'unit_amount': int(float(t['price'])*100),
            },
            'quantity': 1,
        }],
        mode='payment',
        metadata={'payment_id': str(payment_id), 'user_id': str(session.get('user_id') or '')},
        success_url=url_for('payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('payment_cancel', _external=True),
    )

    conn = get_db()
    conn.execute("UPDATE payments SET stripe_session_id=? WHERE id=?", (checkout_session.id, payment_id))
    conn.commit(); conn.close()

    return render_template('checkout.html', amount=float(t['price']), checkout_session_id=checkout_session.id, public_key=STRIPE_PUBLIC_KEY, breadcrumbs=[('Главная', url_for('index')), ('Оплата обучения', url_for('tuition')), ('Платёж', None)])

@app.route('/payment/success')
def payment_success():
    session_id = request.args.get('session_id')
    if not session_id:
        flash('Не найден идентификатор оплаты'); return redirect(url_for('tuition'))
    try:
        s = stripe.checkout.Session.retrieve(session_id, expand=['payment_intent'])
    except Exception:
        flash('Не удалось подтвердить платёж'); return redirect(url_for('tuition'))
    if s.payment_status == 'paid':
        payment_id = s.metadata.get('payment_id')
        conn = get_db()
        conn.execute("UPDATE payments SET status='paid', created_at=? WHERE id=?", (datetime.datetime.now().isoformat(), payment_id))
        tariff_name = conn.execute("SELECT program FROM payments WHERE id=?", (payment_id,)).fetchone()['program']
        conn.commit(); conn.close()
        return render_template('success.html', tariff_name=tariff_name, breadcrumbs=[('Главная', url_for('index')), ('Оплата обучения', url_for('tuition')), ('Успех', None)])
    flash('Платёж не подтверждён'); return redirect(url_for('tuition'))

@app.route('/payment/cancel')
def payment_cancel():
    return render_template('cancel.html', breadcrumbs=[('Главная', url_for('index')), ('Оплата обучения', url_for('tuition')), ('Отмена', None)])

@app.route('/dashboard')
def dashboard():
    return render_template('user/dashboard.html', breadcrumbs=[('Личный кабинет', url_for('dashboard'))])

@app.errorhandler(404)
def nf(e): return render_template('404.html', breadcrumbs=[('Ошибка', None)]), 404

@app.errorhandler(500)
def se(e):
    try: return render_template('500.html', breadcrumbs=[('Ошибка', None)]), 500
    except: return "<h1>Ошибка 500</h1>", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
