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

@app.route('/')def home():return "Bot is alive"

def run():app.run(host='0.0.0.0', port=8080)

def keep_alive():t = Thread(target=run)t.start()

===== CONFIG =====

BOT_TOKEN = os.getenv("BOT_TOKEN")CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)dp = Dispatcher()scheduler = AsyncIOScheduler()

DB_NAME = "fleet.db"

===== DB INIT =====

async def init_db():async with aiosqlite.connect(DB_NAME) as db:await db.execute("""CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT,truck TEXT,action TEXT,note TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    await db.execute("""
    CREATE TABLE IF NOT EXISTS trucks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        truck TEXT UNIQUE,
        status TEXT DEFAULT 'road'
    )
    """)
    await db.commit()

===== INSERT ALL TRUCKS =====

async def insert_trucks():trucks = ["1","01","#01BR","#029","101","184","250","322","325","412","500","612","617","771","801","802","807","808","809","810","811","812","813","814","819","820","821","822","823","824","825","826","827","828","829","831","832","833","834","835","836","837","838","840","841","842","844","845","851","852","854","856","857","858","859","863","864","865","867","870","871","872","878","879","880","881","882","883","884","885","886","887","888","889","890","891","892","893","894","895","897","898","899","912","915","916","917","918","919","920","921","922","923","925","926","927","928","929","930","932","933","934","935","936","937","938","939","940","941","942","943","944","945","946","947","948","950","1318","1363","1412","1417","1434","1602","1808","2020","2122","2428","3602","4036","8215","20021","25166","25167","25169","25170","25172","25174","25187","25188"]

async with aiosqlite.connect(DB_NAME) as db:
    for t in trucks:
        await db.execute(
            "INSERT OR IGNORE INTO trucks (truck) VALUES (?)",
            (t,)
        )
    await db.commit()

===== PARSER =====

async def parse_message(text):import retext = text.lower().strip()

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

===== START =====

@dp.message(lambda m: m.text == "/start")async def start(message: types.Message):await message.answer("🚛 FAIR & FAST SYSTEM READY")

===== HANDLE MESSAGE =====

@dp.message(lambda m: m.text and not m.text.startswith("/"))async def handle_message(message: types.Message):

lines = message.text.split("\n")
results = []

async with aiosqlite.connect(DB_NAME) as db:
    for line in lines:

        parsed = await parse_message(line)
        if not parsed:
            continue

        truck, action, note = parsed

        # STATUS
        for word in ["shop", "yard", "hometime", "road"]:
            if word in line.lower():
                await db.execute(
                    "UPDATE trucks SET status=? WHERE truck=?",
                    (word, truck)
                )
                results.append(f"📍 {truck} → {word}")
                break

        # LOG
        await db.execute("""
            INSERT INTO logs (truck, action, note)
            VALUES (?, ?, ?)
        """, (truck, action, note))

        results.append(f"✅ {truck} → {action}")

    await db.commit()

await message.answer("\n".join(results) if results else "❌ Hech narsa topilmadi")

===== REPORT =====

async def daily_report():

async with aiosqlite.connect(DB_NAME) as db:
    cursor = await db.execute("""
    SELECT truck, action, note FROM logs
    WHERE DATE(created_at)=DATE('now')
    """)
    rows = await cursor.fetchall()

    cursor2 = await db.execute("SELECT truck, status FROM trucks")
    status_rows = await cursor2.fetchall()

issues, planned, done = [], [], []

for t, a, n in rows:
    if a == "issue":
        issues.append((t, n))
    elif a == "planned":
        planned.append((t, n))
    elif a == "done":
        done.append((t, n))

done_set = {t for t, _ in done}
active = [(t, n) for t, n in issues if t not in done_set]

status_map = {}
for t, s in status_rows:
    status_map.setdefault(s, []).append(t)

text = "📊 FAIR & FAST REPORT\n"
text += f"🗓 {datetime.now().strftime('%d-%b-%Y')}\n\n"

text += "⚙️ ON PROCESS:\n"
for t, n in active:
    text += f"{t} — {n}\n"

text += "\n📅 PLANNED:\n"
for t, n in planned:
    text += f"{t} — {n}\n"

text += "\n✅ DONE:\n"
for t, _ in done:
    text += f"{t}\n"

text += "\n📍 STATUS:\n"
for s, trucks in status_map.items():
    text += f"\n{s.upper()}:\n"
    text += " ".join(trucks[:10]) + "\n"

await bot.send_message(CHAT_ID, text)

===== ALERT =====

async def smart_alert():

async with aiosqlite.connect(DB_NAME) as db:
    cursor = await db.execute("""
    SELECT truck, note FROM logs
    WHERE action='issue'
    AND datetime(created_at) <= datetime('now', '-2 day')
    """)
    old_issues = await cursor.fetchall()

    cursor2 = await db.execute("""
    SELECT truck FROM trucks WHERE status='shop'
    """)
    shop_trucks = [r[0] for r in await cursor2.fetchall()]

if not old_issues and not shop_trucks:
    return

text = "🚨 ALERT\n\n"

if old_issues:
    text += "⚠️ OVERDUE:\n"
    for t, n in old_issues:
        text += f"{t} — {n}\n"

if shop_trucks:
    text += "\n🛠 SHOP:\n"
    for t in shop_trucks:
        text += f"{t}\n"

await bot.send_message(CHAT_ID, text)

===== COMMAND =====

@dp.message(lambda m: m.text == "/report")async def report_cmd(message: types.Message):await daily_report()

===== SCHEDULE =====

scheduler.add_job(daily_report, "cron", hour=17, minute=0)scheduler.add_job(smart_alert, "cron", hour=12, minute=0)

===== MAIN =====

async def main():keep_alive()await init_db()await insert_trucks()  # ❗ 1 marta keyin o‘chirscheduler.start()await dp.start_polling(bot)

if name == "main":asyncio.run(main())
