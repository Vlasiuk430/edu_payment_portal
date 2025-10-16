-- SQL schema (optional). The app creates these tables automatically too.
CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role_id INTEGER, FOREIGN KEY(role_id) REFERENCES roles(id));
CREATE TABLE IF NOT EXISTS tariffs (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, price REAL NOT NULL);
CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, fio TEXT, program TEXT, contract_number TEXT, amount REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));
CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT, doc_type TEXT, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, message TEXT, is_read INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));
CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, ip TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS support_tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, subject TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'open');
CREATE TABLE IF NOT EXISTS tariff_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, tariff_id INTEGER, name TEXT, description TEXT, price REAL, changed_at TEXT DEFAULT CURRENT_TIMESTAMP);
-- Seed
INSERT OR IGNORE INTO roles (id,name) VALUES (1,'admin'),(2,'manager'),(3,'client');
INSERT OR IGNORE INTO users (id,username,email,password,role_id) VALUES (1,'admin','admin@example.com','__REPLACE_WITH_HASH__',1);
INSERT OR IGNORE INTO tariffs (id,name,description,price) VALUES
  (1,'Базовый','Базовый тариф для студентов',1000.0),
  (2,'Стандарт','Стандартный пакет услуг',2500.0),
  (3,'Премиум','Полный пакет с поддержкой',5000.0);
