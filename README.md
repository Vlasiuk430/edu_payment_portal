# Edu Payment Portal

Flask-приложение для онлайн-оплаты обучения.

## Быстрый старт локально
```bash
python -m venv .venv
source .venv/bin/activate  # или .venv\Scripts\activate в Windows
pip install -r requirements.txt
python app.py
# открой http://127.0.0.1:5000
```

## Деплой на Render
- Подключи репозиторий с этим проектом
- Render сам прочитает `render.yaml` или используй Procfile
- В переменных окружения добавь (опционально) `SECRET_KEY`
- SQLite-файл создаётся автоматически при старте

## Логин админа
- username: `admin`
- password: `AdminPass123`
