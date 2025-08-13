# Telegram Bot — сбор контактов + уведомление администратору

Бот задаёт вопросы (имя → компания → роль → email → дата/время → согласие) и:
- сохраняет их в SQLite (`bot.db`);
- отправляет все данные **в ваш Telegram** (по `ADMIN_CHAT_ID`).

## Как узнать ADMIN_CHAT_ID
1. В Telegram откройте бота **@userinfobot**.
2. Нажмите Start — бот покажет ваш **Id**. Скопируйте это число и вставьте в `.env` как `ADMIN_CHAT_ID`.

## Быстрый старт (локально)
```bash
python -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
Перед запуском заполните `.env`.

## Переменные окружения (.env)
```
BOT_TOKEN=...                # токен от @BotFather
POLICY_URL=...               # ссылка на политику ПДн
TZ=Asia/Almaty
ADMIN_CHAT_ID=123456789      # ваш чат id (из @userinfobot)
```

## Docker
```bash
docker build -t cybertech-bot .
docker run --name cybertech-bot --env-file .env -v $(pwd)/bot.db:/app/bot.db -d cybertech-bot
```

## Проверка
- Ссылка-QR: `https://t.me/<username_бота>?start=promo`
- После завершения опроса вы получите сообщение от бота с данными лида.
