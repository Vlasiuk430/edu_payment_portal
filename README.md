
# EDU Payment Portal — PRO PLUS (Витте)
- Роли: admin / manager / client (demo: student/Student123)
- Stripe Checkout + Webhook `/stripe/webhook` (TEST MODE)
- PDF-квитанция (ReportLab), Email (SMTP/Mailtrap)
- Экспорт: Excel (.xlsx) и Word (.docx) в админ-панели
- Автосоздание БД и начальных данных

## Локальный запуск
pip install -r requirements.txt
python app.py

## Переменные окружения (Render)
SECRET_KEY, STRIPE_PUBLIC_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_CURRENCY
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TO_BILLING
