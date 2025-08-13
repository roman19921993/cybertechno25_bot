import asyncio
import re
from datetime import datetime
import os
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

# --- env ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
POLICY_URL = os.getenv("POLICY_URL", "https://example.com/policy")
TZ = os.getenv("TZ", "Asia/Almaty")
DB_PATH = os.getenv("DB_PATH", "bot.db")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # string

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env")

# --- db helpers ---
CREATE_TABLE_SQL = """CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER,
    tg_username TEXT,
    name TEXT,
    company TEXT,
    role TEXT,
    email TEXT,
    call_dt_local TEXT,
    consent INTEGER,
    created_at TEXT
);
"""

INSERT_SQL = """INSERT INTO leads (tg_user_id, tg_username, name, company, role, email, call_dt_local, consent, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()

async def save_lead(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            INSERT_SQL,
            (
                data.get("tg_user_id"),
                data.get("tg_username"),
                data.get("name"),
                data.get("company"),
                data.get("role"),
                data.get("email"),
                data.get("call_dt_local"),
                1 if data.get("consent") else 0,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        await db.commit()

# --- FSM ---
class Form(StatesGroup):
    name = State()
    company = State()
    role = State()
    email = State()
    call_dt = State()
    policy = State()

# --- validators ---
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

def valid_email(s: str) -> bool:
    return bool(EMAIL_RE.match(s.strip()))

def parse_call_dt(s: str):
    # Формат: ДД.ММ.ГГ - ЧЧ.ММ, напр. 25.08.25 - 14.30
    s = s.strip()
    try:
        return datetime.strptime(s, "%d.%m.%y - %H.%M")
    except ValueError:
        return None

# --- bot setup ---
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

async def notify_admin(payload: dict):
    if not ADMIN_CHAT_ID:
        return
    # Сформируем красивое сообщение (HTML)
    text = (
        f"<b>Новая заявка</b>\n"
        f"Имя: <b>{payload.get('name')}</b>\n"
        f"Компания: <b>{payload.get('company')}</b>\n"
        f"Роль: <b>{payload.get('role')}</b>\n"
        f"Email: <b>{payload.get('email')}</b>\n"
        f"Дата/время звонка: <b>{payload.get('call_dt_local')}</b>\n"
        f"Согласие с ПДн: <b>{'Да' if payload.get('consent') else 'Нет'}</b>\n\n"
        f"TG user: <code>{payload.get('tg_user_id')}</code> (@{payload.get('tg_username')})\n"
        f"Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ({TZ})"
    )
    try:
        await bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=text, parse_mode="HTML")
    except Exception as e:
        # Логируем в консоль, чтобы в Render Logs было видно
        print(f"[notify_admin] failed: {e}")

@dp.message(CommandStart())
async def on_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Добро пожаловать в Технологии Киберугроз! Как Вас зовут?")
    await state.set_state(Form.name)

@dp.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Пожалуйста, укажите имя текстом.")
        return
    await state.update_data(name=name)
    await message.answer(f"Здравствуйте, {name}! Какую компанию Вы представляете?")
    await state.set_state(Form.company)

@dp.message(Form.company)
async def get_company(message: Message, state: FSMContext):
    company = message.text.strip()
    if not company:
        await message.answer("Пожалуйста, укажите компанию текстом.")
        return
    await state.update_data(company=company)
    await message.answer("Спасибо, какова ваша роль в компании?")
    await state.set_state(Form.role)

@dp.message(Form.role)
async def get_role(message: Message, state: FSMContext):
    role = message.text.strip()
    if not role:
        await message.answer("Пожалуйста, укажите вашу роль текстом.")
        return
    await state.update_data(role=role)
    await message.answer("На какой мейл выслать Вам приглашение на звонок?")
    await state.set_state(Form.email)

@dp.message(Form.email)
async def get_email(message: Message, state: FSMContext):
    email = message.text.strip()
    if not valid_email(email):
        await message.answer("Похоже, в email есть ошибка. Пример: name@example.com\nПопробуйте снова.")
        return
    await state.update_data(email=email)
    await message.answer("Введите дату и время звонка в формате ДД.ММ.ГГ - ЧЧ.ММ (например: 25.08.25 - 14.30).")
    await state.set_state(Form.call_dt)

@dp.message(Form.call_dt)
async def get_call_dt(message: Message, state: FSMContext):
    dt = parse_call_dt(message.text)
    if not dt:
        await message.answer("Не удалось распознать дату. Формат: ДД.ММ.ГГ - ЧЧ.ММ (например: 25.08.25 - 14.30).")
        return
    await state.update_data(call_dt_local=dt.strftime("%Y-%m-%d %H:%M"))
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="Открыть политику", url=POLICY_URL))
    kb.row(InlineKeyboardButton(text="Далее", callback_data="consent_next"))
    await message.answer(
        "Прочтите политику сбора ПДн (ссылка выше) и согласитесь с ней нажатием «Далее».",
        reply_markup=kb.as_markup(),
    )
    await state.set_state(Form.policy)

@dp.callback_query(F.data == "consent_next")
async def on_consent(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    lead_payload = {
        "tg_user_id": cb.from_user.id,
        "tg_username": cb.from_user.username,
        "name": data.get("name"),
        "company": data.get("company"),
        "role": data.get("role"),
        "email": data.get("email"),
        "call_dt_local": data.get("call_dt_local"),
        "consent": True,
    }
    await save_lead(lead_payload)
    await notify_admin(lead_payload)  # <-- отправка админу
    await state.clear()
    await cb.message.answer("Спасибо, мы вышлем вам приглашение на звонок.")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
