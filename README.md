# WisdomTea Mini App

## Структура
```
wisdomtea_webapp/
├── app.py           ← Flask сервер
├── bot.py           ← Telegram бот (уведомления)
├── db.py            ← База данных (без изменений)
├── templates/
│   └── index.html   ← Весь интерфейс
├── requirements.txt
└── Procfile
```

## Запуск локально
```bash
pip install -r requirements.txt
python app.py
```
Открой http://localhost:5000

## Деплой на Railway (бесплатно)

1. Зарегистрируйся на https://railway.app (через GitHub)
2. Создай новый проект → "Deploy from GitHub repo"
3. Загрузи папку на GitHub (можно через GitHub Desktop)
4. В Railway добавь переменные окружения:
   - `BOT_TOKEN` = токен вашего бота
   - `ADMIN_ID` = ваш Telegram ID
5. Railway автоматически запустит сервер

## Подключить мини-апп к боту

В @BotFather:
1. /mybots → выбери бота → Bot Settings → Menu Button
2. Вставь URL от Railway (например: https://wisdomtea.up.railway.app)
3. Название кнопки: "Открыть магазин"

Готово! Кнопка появится в чате с ботом.
