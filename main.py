import asyncio
import os
from datetime import datetime

import aiosqlite
from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ===== KEEP ALIVE =====
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

DB_NAME = "fleet.db"

# ===== DB INIT =====
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            truck TEXT,
            action TEXT,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS trucks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            truck TEXT UNIQUE,
            status TEXT DEFAULT 'road'
        )
        """)
        await db.commit()

# ===== PARSER =====
async def parse_message(text):
    import re
    text = text.lower().strip()

    match = re.search(r"\b#?\d+\b", text)
    if not match:
        return None

    truck = match.group()

    if "done" in text or "fixed" in text:
        action = "done"
    elif "plan" in text:
        action = "planned"
    else:
        action = "issue"

    note = text.replace(truck, "").strip()
    return truck, action, note

# ===== START =====
@dp.message(lambda m: m.text == "/start")
async def start(message: types.Message):
    await message.answer("🚛 BOT IS WORKING")

# ===== HANDLE MESSAGE =====
@dp.message(lambda m: m.text and not m.text.startswith("/"))
async def handle_message(message: types.Message):

    parsed = await parse_message(message.text)
    if not parsed:
        await message.answer("❌ Format noto‘g‘ri")
        return

    truck, action, note = parsed

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO logs (truck, action, note) VALUES (?, ?, ?)",
            (truck, action, note)
        )
        await db.commit()

    await message.answer(f"✅ {truck} → {action}")

# ===== REPORT =====
async def daily_report():

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
        SELECT truck, action FROM logs
        WHERE DATE(created_at)=DATE('now')
        """)
        rows = await cursor.fetchall()

    text = "📊 DAILY REPORT\n\n"

    for t, a in rows:
        text += f"{t} → {a}\n"

    if CHAT_ID:
        await bot.send_message(CHAT_ID, text)

# ===== COMMAND =====
@dp.message(lambda m: m.text == "/report")
async def report_cmd(message: types.Message):
    await daily_report()

# ===== SCHEDULE =====
scheduler.add_job(daily_report, "cron", hour=17, minute=0)

# ===== MAIN =====
async def main():
    keep_alive()
    await init_db()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
