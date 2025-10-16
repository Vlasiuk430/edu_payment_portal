# Университет Витте — Оплата обучения (Stripe TEST)

Flask-портал с оплатой обучения через Stripe (тестовый режим), оформленный под стиль Витте.

## Направления (примерные цены за семестр)
- Бакалавриат (очная форма) — 82 000 ₽
- Бакалавриат (заочная форма) — 46 000 ₽
- Магистратура — 95 000 ₽
- Переподготовка и повышение квалификации — 25 000 ₽

## Render — переменные окружения
- `STRIPE_PUBLIC_KEY` = pk_test_...
- `STRIPE_SECRET_KEY` = sk_test_...
- `STRIPE_CURRENCY` = `usd` (или валюта, поддерживаемая в твоём аккаунте Stripe)
- `SECRET_KEY` генерируется автоматически (render.yaml)

## Тестовая карта Stripe
- 4242 4242 4242 4242 — любая будущая дата, любой CVC

## Запуск локально
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export STRIPE_PUBLIC_KEY=pk_test_xxx
export STRIPE_SECRET_KEY=sk_test_xxx
python app.py
```
Открыть: http://127.0.0.1:5000
