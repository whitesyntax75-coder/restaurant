"""
🍽️ RestaurantBot - Stol Bron Qilish Tizimi
============================================
Muallif: 10 yillik aiogram tajribasi asosida
Versiya: 2.0.0
Framework: aiogram 3.x
Database: SQLite

O'rnatish:
    pip install aiogram apscheduler

Ishga tushirish:
    python main.py
"""

import asyncio
import calendar
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from logging import FileHandler, StreamHandler, basicConfig, getLogger
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── SOZLAMALAR ────────────────────────────────────────────────────────────────

BOT_TOKEN = "8855624248:AAFBK746GnZ_ei7wD7GGvTbu6cMvejxENv4"          # @BotFather dan olingan token
DB_PATH = "restaurantbot.db"
SUPER_ADMIN_IDS = [7904389988]              # Super-admin Telegram ID'lari

basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        StreamHandler(),
        FileHandler("restaurantbot.log", encoding="utf-8"),
    ],
)
logger = getLogger(__name__)

# ─── FSM HOLATLARI ─────────────────────────────────────────────────────────────

class CustomerReg(StatesGroup):
    full_name = State()
    phone     = State()

class RestaurantReg(StatesGroup):
    name = State()
    phone = State()
    cuisine_type = State()
    tables_count = State()
    price_min    = State()
    price_max    = State()
    address      = State()
    location     = State()

class BookingFSM(StatesGroup):
    choose_cuisine    = State()
    choose_restaurant = State()
    choose_date       = State()
    choose_time       = State()
    guests_count      = State()
    note              = State()
    confirm           = State()

class EditRestaurant(StatesGroup):
    field = State()
    value = State()
    location = State()

class MenuViewFSM(StatesGroup):
    choose_restaurant = State()

class RatingFSM(StatesGroup):
    choose_restaurant = State()
    give_rating = State()

class CommentFSM(StatesGroup):
    choose_restaurant = State()
    write_comment = State()

# ─── DATABASE ──────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY,
            tg_id       INTEGER UNIQUE NOT NULL,
            role        TEXT NOT NULL DEFAULT 'customer',  -- customer | restaurant | superadmin
            full_name   TEXT,
            phone       TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS restaurants (
            id              INTEGER PRIMARY KEY,
            owner_tg_id     INTEGER UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            cuisine_type    TEXT NOT NULL,
            tables_count    INTEGER NOT NULL,
            price_min       INTEGER NOT NULL,
            price_max       INTEGER NOT NULL,
            phone           TEXT NOT NULL,
            address         TEXT NOT NULL,
            latitude        REAL,
            longitude       REAL,
            is_approved     INTEGER NOT NULL DEFAULT 0,  -- 0=pending | 1=approved | 2=rejected
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_tg_id) REFERENCES users(tg_id)
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id              INTEGER PRIMARY KEY,
            customer_tg_id  INTEGER NOT NULL,
            restaurant_id   INTEGER NOT NULL REFERENCES restaurants(id),
            booking_date    TEXT NOT NULL,
            booking_time    TEXT NOT NULL,
            guests_count    INTEGER NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',  -- pending|confirmed|rejected|cancelled
            note            TEXT,
            reminder_sent   INTEGER NOT NULL DEFAULT 0,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_tg_id) REFERENCES users(tg_id)
        );

        CREATE TABLE IF NOT EXISTS menu_categories (
            id              INTEGER PRIMARY KEY,
            restaurant_id   INTEGER NOT NULL REFERENCES restaurants(id),
            name            TEXT NOT NULL,
            emoji           TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS menu_items (
            id              INTEGER PRIMARY KEY,
            category_id     INTEGER NOT NULL REFERENCES menu_categories(id),
            name            TEXT NOT NULL,
            price           INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ratings (
            id              INTEGER PRIMARY KEY,
            customer_tg_id  INTEGER NOT NULL,
            restaurant_id   INTEGER NOT NULL REFERENCES restaurants(id),
            rating          INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(customer_tg_id, restaurant_id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id              INTEGER PRIMARY KEY,
            customer_tg_id  INTEGER NOT NULL,
            restaurant_id   INTEGER NOT NULL REFERENCES restaurants(id),
            text            TEXT NOT NULL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_tg_id) REFERENCES users(tg_id)
        );
    """)
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")


def seed_data():
    """Boshlang'ich restoran va menyu ma'lumotlarini qo'shish"""
    conn = get_db()
    # Agar allaqachon restoran bor bo'lsa, o'tkazib yuborish
    existing = conn.execute("SELECT id FROM restaurants LIMIT 1").fetchone()
    if existing:
        conn.close()
        return

    # Super admin foydalanuvchi sifatida
    admin_id = SUPER_ADMIN_IDS[0]
    conn.execute(
        "INSERT OR IGNORE INTO users (tg_id, role, full_name, phone) VALUES (?,?,?,?)",
        (admin_id, "superadmin", "Super Admin", "+998999108050"),
    )

    # ─── SHRIFT X restoran ────────────────────────────────────────────────────────
    conn.execute("""
        INSERT INTO restaurants
        (owner_tg_id, name, cuisine_type, tables_count,
         price_min, price_max, phone, address, is_approved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (admin_id, "SHRIFT X", "🍔 Fast Food", 10,
          12000, 40000, "+998999108050",
          "Guliston shahri"))

    rest_id = conn.execute("SELECT id FROM restaurants WHERE owner_tg_id=?", (admin_id,)).fetchone()[0]

    # Menyu kategoriyalari va mahsulotlar
    menu_data = {
        ("Lavashlar", "🌯"): [
            ("Standart Lavash", 25000),
            ("Big Lavash", 28000),
            ("Sirli Lavash", 32000),
        ],
        ("Gamburger & Haggi", "🍔"): [
            ("Standart Gamburger", 18000),
            ("Katta Gamburger", 20000),
            ("Standart Haggi", 25000),
        ],
        ("Donerlar", "🥙"): [
            ("Standart Doner", 25000),
            ("Sirli Doner", 30000),
        ],
        ("Hot-doglar", "🌭"): [
            ("Tim Hot Dog", 12000),
            ("Kanada Hot Dog", 14000),
            ("Korolevskiy Hot Dog", 16000),
        ],
        ("Tovuq & Fri", "🍟"): [
            ("File (Tovuq filesi)", 30000),
            ("Fri", 12000),
            ("File + Fri (Kombinatsiya)", 40000),
        ],
    }

    for (cat_name, emoji), items in menu_data.items():
        conn.execute(
            "INSERT INTO menu_categories (restaurant_id, name, emoji) VALUES (?,?,?)",
            (rest_id, cat_name, emoji),
        )
        cat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for item_name, price in items:
            conn.execute(
                "INSERT INTO menu_items (category_id, name, price) VALUES (?,?,?)",
                (cat_id, item_name, price),
            )

    # ─── DJIGAR restoran ──────────────────────────────────────────────────────────
    djigar_dummy_id = 1111111111
    conn.execute(
        "INSERT OR IGNORE INTO users (tg_id, role, full_name, phone) VALUES (?,?,?,?)",
        (djigar_dummy_id, "restaurant", "DJIGAR Admin", "+998938273311"),
    )
    conn.execute("""
        INSERT INTO restaurants
        (owner_tg_id, name, cuisine_type, tables_count,
         price_min, price_max, phone, address, is_approved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (djigar_dummy_id, "DJIGAR", "🥩 Grill", 15,
          3000, 24000, "+998938273311",
          "Saxovatning yonida, Guliston shahri"))

    djigar_id = conn.execute("SELECT id FROM restaurants WHERE owner_tg_id=?", (djigar_dummy_id,)).fetchone()[0]

    djigar_menu = {
        ("Shashliqlar", "🍖"): [
            ("Napoleon shashliq", 19000),
            ("Qanot shashliqi", 17000),
            ("Baliq filesi shashliqi", 19000),
            ("DJIGAR jigar shashliqi", 15000),
            ("Mol gosht bolagi", 19000),
        ],
        ("Hot-doglar", "🌭"): [
            ("Hot-dog (qoy goshti)", 24000),
            ("Hot-dog (mol goshti)", 24000),
            ("Hot-dog (maydalangan)", 19000),
        ],
        ("Ichimliklar", "🥛"): [
            ("Choy bardak", 3000),
            ("Ayron 0.45", 8000),
            ("Ayron 0.6", 10000),
            ("Choy limon bilan", 10000),
        ],
    }

    for (cat_name, emoji), items in djigar_menu.items():
        conn.execute(
            "INSERT INTO menu_categories (restaurant_id, name, emoji) VALUES (?,?,?)",
            (djigar_id, cat_name, emoji),
        )
        cat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for item_name, price in items:
            conn.execute(
                "INSERT INTO menu_items (category_id, name, price) VALUES (?,?,?)",
                (cat_id, item_name, price),
            )

    conn.commit()
    conn.close()
    logger.info("✅ Seed data qo'shildi")

# ─── DB YORDAMCHI FUNKSIYALAR ──────────────────────────────────────────────────

def db_get_user(tg_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def db_create_user(tg_id: int, role: str, full_name: str, phone: str):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (tg_id, role, full_name, phone) VALUES (?,?,?,?)",
        (tg_id, role, full_name, phone),
    )
    conn.commit()
    conn.close()


def db_get_restaurant_by_owner(tg_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM restaurants WHERE owner_tg_id=?", (tg_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def db_get_restaurant_by_id(rid: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM restaurants WHERE id=?", (rid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def db_create_restaurant(data: dict):
    conn = get_db()
    conn.execute(
        """INSERT OR REPLACE INTO restaurants
           (owner_tg_id, name, cuisine_type, tables_count,
            price_min, price_max, phone, address, latitude, longitude, is_approved)
           VALUES (:owner_tg_id,:name,:cuisine_type,:tables_count,
                   :price_min,:price_max,:phone,:address,:latitude,:longitude,0)""",
        data,
    )
    conn.execute(
        "UPDATE users SET role='restaurant' WHERE tg_id=?", (data["owner_tg_id"],)
    )
    conn.commit()
    conn.close()


def db_list_cuisines() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT cuisine_type FROM restaurants WHERE is_approved=1 ORDER BY cuisine_type"
    ).fetchall()
    conn.close()
    return [r["cuisine_type"] for r in rows]


def db_list_restaurants_by_cuisine(cuisine: str) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM restaurants WHERE cuisine_type=? AND is_approved=1",
        (cuisine,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_list_approved_restaurants() -> list:
    conn = get_db()
    rows = conn.execute("SELECT * FROM restaurants WHERE is_approved=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_list_pending_restaurants() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT r.*, u.full_name AS owner_name FROM restaurants r "
        "JOIN users u ON u.tg_id=r.owner_tg_id WHERE r.is_approved=0"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_approve_restaurant(rid: int, status: int):
    conn = get_db()
    conn.execute("UPDATE restaurants SET is_approved=? WHERE id=?", (status, rid))
    conn.commit()
    conn.close()


def db_create_booking(
    customer_tg_id: int, restaurant_id: int,
    date: str, time: str, guests: int, note: str
) -> int:
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO bookings
           (customer_tg_id, restaurant_id, booking_date, booking_time, guests_count, note)
           VALUES (?,?,?,?,?,?)""",
        (customer_tg_id, restaurant_id, date, time, guests, note),
    )
    booking_id = cur.lastrowid
    conn.commit()
    conn.close()
    return booking_id


def db_get_booking(booking_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("""
        SELECT b.*,
               r.name AS rest_name, r.phone AS rest_phone,
               r.owner_tg_id,
               u.full_name AS customer_name, u.phone AS customer_phone
        FROM bookings b
        JOIN restaurants r ON r.id = b.restaurant_id
        JOIN users u ON u.tg_id = b.customer_tg_id
        WHERE b.id=?
    """, (booking_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def db_update_booking_status(booking_id: int, status: str):
    conn = get_db()
    conn.execute(
        "UPDATE bookings SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (status, booking_id),
    )
    conn.commit()
    conn.close()


def db_customer_bookings(tg_id: int) -> list:
    conn = get_db()
    rows = conn.execute("""
        SELECT b.*, r.name AS rest_name, r.cuisine_type
        FROM bookings b
        JOIN restaurants r ON r.id=b.restaurant_id
        WHERE b.customer_tg_id=?
        ORDER BY b.booking_date DESC, b.booking_time DESC
        LIMIT 20
    """, (tg_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_restaurant_bookings(owner_tg_id: int, status_filter: str) -> list:
    conn = get_db()
    rows = conn.execute("""
        SELECT b.*, u.full_name AS customer_name, u.phone AS customer_phone
        FROM bookings b
        JOIN restaurants r ON r.id=b.restaurant_id
        JOIN users u ON u.tg_id=b.customer_tg_id
        WHERE r.owner_tg_id=? AND b.status=?
        ORDER BY b.booking_date, b.booking_time
    """, (owner_tg_id, status_filter)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_restaurant_stats(owner_tg_id: int) -> dict:
    conn = get_db()
    r = conn.execute("SELECT * FROM restaurants WHERE owner_tg_id=?", (owner_tg_id,)).fetchone()
    if not r:
        conn.close()
        return {}
    stats = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='pending'   THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='confirmed' THEN 1 ELSE 0 END) as confirmed,
            SUM(CASE WHEN status='rejected'  THEN 1 ELSE 0 END) as rejected,
            SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) as cancelled
        FROM bookings WHERE restaurant_id=?
    """, (r["id"],)).fetchone()
    conn.close()
    return {**dict(r), **dict(stats)}


def db_reminders_due() -> list:
    """Bron vaqtidan 1 soat oldingi, hali eslatma yuborilmagan tasdiqlangan bronlar"""
    now = datetime.now()
    target = now + timedelta(hours=1)
    date_str = target.strftime("%Y-%m-%d")
    time_str = target.strftime("%H:%M")
    conn = get_db()
    rows = conn.execute("""
        SELECT b.*, r.name AS rest_name, r.phone AS rest_phone
        FROM bookings b
        JOIN restaurants r ON r.id=b.restaurant_id
        WHERE b.booking_date=? AND b.booking_time=?
          AND b.status='confirmed' AND b.reminder_sent=0
    """, (date_str, time_str)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_mark_reminder_sent(booking_id: int):
    conn = get_db()
    conn.execute("UPDATE bookings SET reminder_sent=1 WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()


def db_global_stats() -> dict:
    conn = get_db()
    row = conn.execute("""
        SELECT
            (SELECT COUNT(*) FROM users WHERE role='customer')            AS customers,
            (SELECT COUNT(*) FROM restaurants WHERE is_approved=1)        AS restaurants,
            (SELECT COUNT(*) FROM restaurants WHERE is_approved=0)        AS pending_rests,
            (SELECT COUNT(*) FROM bookings)                               AS bookings_total,
            (SELECT COUNT(*) FROM bookings WHERE status='confirmed')      AS bookings_confirmed
    """).fetchone()
    conn.close()
    return dict(row)

def db_get_menu(restaurant_id: int) -> list:
    conn = get_db()
    categories = conn.execute(
        "SELECT * FROM menu_categories WHERE restaurant_id=? ORDER BY id",
        (restaurant_id,),
    ).fetchall()
    result = []
    for cat in categories:
        items = conn.execute(
            "SELECT * FROM menu_items WHERE category_id=? ORDER BY id",
            (cat["id"],),
        ).fetchall()
        result.append({"category": dict(cat), "items": [dict(i) for i in items]})
    conn.close()
    return result


def db_add_rating(tg_id: int, restaurant_id: int, rating: int):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO ratings (customer_tg_id, restaurant_id, rating) VALUES (?,?,?)",
        (tg_id, restaurant_id, rating),
    )
    conn.commit()
    conn.close()


def db_get_avg_rating(restaurant_id: int) -> dict:
    conn = get_db()
    row = conn.execute(
        "SELECT AVG(rating) as avg_rating, COUNT(*) as count FROM ratings WHERE restaurant_id=?",
        (restaurant_id,),
    ).fetchone()
    conn.close()
    return {"avg": round(row["avg_rating"], 1) if row["avg_rating"] else 0, "count": row["count"]}


def db_add_comment(tg_id: int, restaurant_id: int, text: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO comments (customer_tg_id, restaurant_id, text) VALUES (?,?,?)",
        (tg_id, restaurant_id, text),
    )
    conn.commit()
    conn.close()


def db_get_comments(restaurant_id: int, limit: int = 15) -> list:
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, u.full_name
        FROM comments c
        JOIN users u ON u.tg_id = c.customer_tg_id
        WHERE c.restaurant_id=?
        ORDER BY c.created_at DESC
        LIMIT ?
    """, (restaurant_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── KLAVIATURALAR ─────────────────────────────────────────────────────────────

def kb_main_customer() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍽 Restoran tanlash"), KeyboardButton(text="📜 Menyu")],
            [KeyboardButton(text="⭐ Baho berish"), KeyboardButton(text="💬 Izohlar")],
            [KeyboardButton(text="📋 Bronlarim"), KeyboardButton(text="👤 Profilim")],
            [KeyboardButton(text="📍 Lokatsiya"), KeyboardButton(text="📞 Aloqa")],
        ],
        resize_keyboard=True,
    )


def kb_main_restaurant() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Bronlar"), KeyboardButton(text="🏠 Mening restoranim")],
            [KeyboardButton(text="✏️ Profil tahrirlash"), KeyboardButton(text="📈 Statistika")],
        ],
        resize_keyboard=True,
    )


def kb_main_superadmin() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛂 Kutayotgan restoranlar"), KeyboardButton(text="📊 Statistika")],
        ],
        resize_keyboard=True,
    )


def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑‍🍳 Mijoz sifatida kirish",    callback_data="role_customer")],
        [InlineKeyboardButton(text="🏠 Restoran egasi sifatida",   callback_data="role_restaurant")],
    ])


def kb_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def kb_location() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Lokatsiyani ulashish", request_location=True)],
            [KeyboardButton(text="⏭ O'tkazib yuborish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def kb_back() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Ortga")]],
        resize_keyboard=True,
    )


def kb_cuisine_choice() -> InlineKeyboardMarkup:
    cuisines = [
        "🥘 O'zbek", "🍕 Italyan", "🍜 Xitoy", "🍔 Fast Food",
        "🥩 Grill", "🌮 Meksikan", "🍣 Yapon", "🫕 Sharq", "Boshqa",
    ]
    buttons = []
    row = []
    for c in cuisines:
        row.append(InlineKeyboardButton(text=c, callback_data=f"newcuisine_{c}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_cuisines(cuisines: list) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"cuisine_{c}")] for c in cuisines]
    buttons.append([InlineKeyboardButton(text="🔍 Barcha restoranlar", callback_data="cuisine_all")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_restaurants(restaurants: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"🍴 {r['name']}  |  {r['price_min']//1000}K–{r['price_max']//1000}K so'm",
            callback_data=f"rest_{r['id']}"
        )]
        for r in restaurants
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_inline_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    months_uz = [
        "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
        "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
    ]
    days_uz = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
    today = datetime.now().date()
    buttons: list[list[InlineKeyboardButton]] = []

    # Header: ← Oy Yil →
    buttons.append([
        InlineKeyboardButton(text="◀️", callback_data=f"calprev_{year}_{month}"),
        InlineKeyboardButton(text=f"{months_uz[month]} {year}", callback_data="cal_noop"),
        InlineKeyboardButton(text="▶️", callback_data=f"calnext_{year}_{month}"),
    ])
    # Hafta kunlari
    buttons.append([
        InlineKeyboardButton(text=d, callback_data="cal_noop") for d in days_uz
    ])
    # Kunlar
    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="cal_noop"))
            else:
                date_obj = datetime(year, month, day).date()
                if date_obj < today:
                    row.append(InlineKeyboardButton(text=f"·{day}·", callback_data="cal_noop"))
                else:
                    row.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"calday_{year}_{month}_{day}",
                    ))
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_time_slots() -> InlineKeyboardMarkup:
    """09:00 dan 22:00 gacha, har 30 daqiqa"""
    slots = []
    h, m = 9, 0
    while (h, m) <= (22, 0):
        slots.append(f"{h:02d}:{m:02d}")
        m += 30
        if m >= 60:
            m, h = 0, h + 1
    buttons = []
    row = []
    for s in slots:
        row.append(InlineKeyboardButton(text=s, callback_data=f"time_{s}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_booking_action(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"bconfirm_{booking_id}"),
        InlineKeyboardButton(text="❌ Rad etish",  callback_data=f"breject_{booking_id}"),
    ]])


def kb_cancel_booking(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚫 Bronni bekor qilish", callback_data=f"bcancel_{booking_id}"),
    ]])


# ─── YORDAMCHI FUNKSIYALAR ─────────────────────────────────────────────────────

STATUS_EMOJI = {
    "pending":   "⏳",
    "confirmed": "✅",
    "rejected":  "❌",
    "cancelled": "🚫",
}
STATUS_TEXT = {
    "pending":   "Kutilmoqda",
    "confirmed": "Tasdiqlangan",
    "rejected":  "Rad etilgan",
    "cancelled": "Bekor qilingan",
}


def format_booking_short(b: dict) -> str:
    e = STATUS_EMOJI.get(b["status"], "?")
    s = STATUS_TEXT.get(b["status"], b["status"])
    return (
        f"{e} <b>#{b['id']}</b> — {b['booking_date']} {b['booking_time']}\n"
        f"   🏠 {b['rest_name']} | 👥 {b['guests_count']} kishi\n"
        f"   Holat: {s}\n"
    )


def format_booking_full(b: dict, show_customer: bool = False) -> str:
    e = STATUS_EMOJI.get(b["status"], "?")
    s = STATUS_TEXT.get(b["status"], b["status"])
    text = (
        f"🆔 <b>Bron #{b['id']}</b>\n"
        f"📅 Sana: {b['booking_date']}  🕐 {b['booking_time']}\n"
        f"👥 Mehmonlar: {b['guests_count']} kishi\n"
        f"📌 Holat: {e} {s}\n"
    )
    if b.get("note"):
        text += f"📝 Izoh: {b['note']}\n"
    if show_customer:
        text += f"👤 Mijoz: {b['customer_name']}  📞 {b['customer_phone']}\n"
    return text


# ─── ROUTER ────────────────────────────────────────────────────────────────────

router = Router()

# ── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    tg_id = msg.from_user.id

    # Super admin
    if tg_id in SUPER_ADMIN_IDS:
        conn = get_db()
        conn.execute(
            "INSERT OR IGNORE INTO users (tg_id, role, full_name, phone) VALUES (?,?,?,?)",
            (tg_id, "superadmin", "Super Admin", "+998000000000"),
        )
        conn.commit()
        conn.close()
        await msg.answer(
            "👑 <b>Super Admin paneli</b>\nXush kelibsiz!",
            reply_markup=kb_main_superadmin(),
        )
        return

    user = db_get_user(tg_id)
    if not user:
        await msg.answer(
            "🍽️ <b>RestaurantBot</b> — Stol Bron Qilish Tizimi\n\n"
            "Siz kim sifatida foydalanmoqchisiz?",
            reply_markup=kb_start(),
        )
        return

    if user["role"] == "restaurant":
        rest = db_get_restaurant_by_owner(tg_id)
        extra = ""
        if rest and rest["is_approved"] == 0:
            extra = "\n\n⏳ Restoraningiz hali tasdiqlanmagan."
        elif rest and rest["is_approved"] == 2:
            extra = "\n\n❌ Restoraningiz rad etilgan."
        await msg.answer(
            f"👋 Xush kelibsiz, <b>{user['full_name']}</b>!{extra}",
            reply_markup=kb_main_restaurant(),
        )
    else:
        await msg.answer(
            f"👋 Xush kelibsiz, <b>{user['full_name']}</b>!\n"
            "Stol bron qilish uchun quyidagi tugmalardan foydalaning.",
            reply_markup=kb_main_customer(),
        )

# ── ROL TANLASH ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "role_customer")
async def role_customer(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "👤 <b>Mijoz bo'lib ro'yxatdan o'tish</b>\n\nIsmingizni kiriting:"
    )
    await state.set_state(CustomerReg.full_name)


@router.callback_query(F.data == "role_restaurant")
async def role_restaurant(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🏠 <b>Restoran egasi bo'lib ro'yxatdan o'tish</b>\n\nIsmingizni kiriting:"
    )
    await state.update_data(pending_role="restaurant")
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (tg_id, role) VALUES (?,?)",
        (call.from_user.id, "restaurant"),
    )
    conn.commit()
    conn.close()
    await state.set_state(CustomerReg.full_name)
    await state.update_data(pending_role="restaurant")

# ── MIJOZ RO'YXATDAN O'TISH ──────────────────────────────────────────────────

@router.message(CustomerReg.full_name)
async def customer_name(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.clear()
        await cmd_start(msg, state)
        return
    name = msg.text.strip()
    if len(name) < 3:
        await msg.answer("❗ Ism-familya kamida 3 ta harf bo'lishi kerak. Qaytadan kiriting:")
        return
    await state.update_data(full_name=name)
    await msg.answer("📱 Telefon raqamingizni ulashing:", reply_markup=kb_phone())
    await state.set_state(CustomerReg.phone)


@router.message(CustomerReg.phone, F.contact)
async def customer_phone(msg: Message, state: FSMContext):
    data = await state.get_data()
    phone = msg.contact.phone_number
    tg_id = msg.from_user.id
    role = data.get("pending_role", "customer")

    db_create_user(tg_id, role, data["full_name"], phone)
    await state.clear()

    if role == "restaurant":
        await msg.answer(
            f"✅ <b>Ro'yxatdan o'tdingiz!</b>\n\n"
            f"👤 {data['full_name']}  📞 {phone}\n\n"
            "Endi restoraningizni ro'yxatdan o'tkazaylik.\n\n"
            "🏠 Restoran nomini kiriting:",
            reply_markup=kb_back(),
        )
        await state.update_data(owner_tg_id=tg_id)
        await state.set_state(RestaurantReg.name)
    else:
        await msg.answer(
            f"✅ <b>Ro'yxatdan o'tdingiz!</b>\n\n"
            f"👤 {data['full_name']}  📞 {phone}\n\n"
            "Endi stol bron qilishingiz mumkin! 🎉",
            reply_markup=kb_main_customer(),
        )


@router.message(CustomerReg.phone)
async def customer_phone_fallback(msg: Message):
    await msg.answer("❗ Iltimos, <b>tugmani bosib</b> telefon raqamingizni ulashing:", reply_markup=kb_phone())

# ── RESTORAN RO'YXATDAN O'TISH ───────────────────────────────────────────────

@router.message(RestaurantReg.name)
async def rest_reg_name(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.clear()
        await cmd_start(msg, state)
        return
    await state.update_data(name=msg.text.strip())
    await msg.answer(
        "🍜 Oshxona turini tanlang:",
        reply_markup=kb_cuisine_choice(),
    )
    await state.set_state(RestaurantReg.cuisine_type)


@router.callback_query(RestaurantReg.cuisine_type, F.data.startswith("newcuisine_"))
async def rest_reg_cuisine(call: CallbackQuery, state: FSMContext):
    cuisine = call.data.replace("newcuisine_", "")
    await state.update_data(cuisine_type=cuisine)
    await call.message.edit_text(f"✅ Oshxona turi: <b>{cuisine}</b>\n\n🪑 Stollar sonini kiriting:")
    await state.set_state(RestaurantReg.tables_count)


@router.message(RestaurantReg.tables_count)
async def rest_reg_tables(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.set_state(RestaurantReg.name)
        await msg.answer("Restoran nomini kiriting:", reply_markup=kb_back())
        return
    if not msg.text.strip().isdigit() or int(msg.text.strip()) < 1:
        await msg.answer("❗ Musbat raqam kiriting (masalan: 15):")
        return
    await state.update_data(tables_count=int(msg.text.strip()))
    await msg.answer("💰 Minimal narxni kiriting (so'mda, masalan: <code>50000</code>):", reply_markup=kb_back())
    await state.set_state(RestaurantReg.price_min)


@router.message(RestaurantReg.price_min)
async def rest_reg_price_min(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.set_state(RestaurantReg.tables_count)
        await msg.answer("Stollar sonini kiriting:", reply_markup=kb_back())
        return
    if not msg.text.strip().isdigit():
        await msg.answer("❗ Faqat raqam kiriting:")
        return
    await state.update_data(price_min=int(msg.text.strip()))
    await msg.answer("💰 Maksimal narxni kiriting (so'mda, masalan: <code>300000</code>):", reply_markup=kb_back())
    await state.set_state(RestaurantReg.price_max)


@router.message(RestaurantReg.price_max)
async def rest_reg_price_max(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.set_state(RestaurantReg.price_min)
        await msg.answer("Minimal narxni kiriting:", reply_markup=kb_back())
        return
    if not msg.text.strip().isdigit():
        await msg.answer("❗ Faqat raqam kiriting:")
        return
    await state.update_data(price_max=int(msg.text.strip()))
    await msg.answer("📞 Restoran telefon raqami:", reply_markup=kb_back())
    await state.set_state(RestaurantReg.phone)


@router.message(RestaurantReg.phone)
async def rest_reg_phone(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.set_state(RestaurantReg.price_max)
        await msg.answer("Maksimal narxni kiriting:", reply_markup=kb_back())
        return
    await state.update_data(phone=msg.text.strip())
    await msg.answer("📍 Manzil (ko'cha, bino, shahar):", reply_markup=kb_back())
    await state.set_state(RestaurantReg.address)


@router.message(RestaurantReg.address)
async def rest_reg_address(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.set_state(RestaurantReg.phone)
        await msg.answer("Telefon raqamini kiriting:", reply_markup=kb_back())
        return
    await state.update_data(address=msg.text.strip())
    await msg.answer(
        "📍 Lokatsiyani ulashing (ixtiyoriy):",
        reply_markup=kb_location(),
    )
    await state.set_state(RestaurantReg.location)


@router.message(RestaurantReg.location)
async def rest_reg_location(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.set_state(RestaurantReg.address)
        await msg.answer("Manzilni kiriting:", reply_markup=kb_back())
        return

    lat, lon = None, None
    if msg.location:
        lat, lon = msg.location.latitude, msg.location.longitude

    data = await state.get_data()
    tg_id = msg.from_user.id

    db_create_restaurant({
        "owner_tg_id": tg_id,
        "name":         data["name"],
        "cuisine_type": data["cuisine_type"],
        "tables_count": data["tables_count"],
        "price_min":    data["price_min"],
        "price_max":    data["price_max"],
        "phone":        data["phone"],
        "address":      data["address"],
        "latitude":     lat,
        "longitude":    lon,
    })
    await state.clear()

    await msg.answer(
        "✅ <b>Arizangiz qabul qilindi!</b>\n\n"
        f"🏠 {data['name']} | {data['cuisine_type']}\n"
        f"🪑 {data['tables_count']} stol\n"
        f"💰 {data['price_min']:,} — {data['price_max']:,} so'm\n\n"
        "Super admin tez orada ko'rib chiqadi va xabar beradi. ⏳",
        reply_markup=kb_main_restaurant(),
    )

    # Super adminlarga xabar
    for admin_id in SUPER_ADMIN_IDS:
        try:
            await msg.bot.send_message(
                admin_id,
                f"🆕 <b>Yangi restoran arizasi!</b>\n\n"
                f"🏠 {data['name']} ({data['cuisine_type']})\n"
                f"🪑 {data['tables_count']} stol\n"
                f"💰 {data['price_min']:,} — {data['price_max']:,} so'm\n"
                f"📞 {data['phone']}\n"
                f"📍 {data['address']}",
                reply_markup=kb_main_superadmin(),
            )
        except Exception:
            pass

# ── SUPER ADMIN ──────────────────────────────────────────────────────────────

@router.message(F.text == "🛂 Kutayotgan restoranlar")
async def admin_pending(msg: Message):
    if msg.from_user.id not in SUPER_ADMIN_IDS:
        return
    rests = db_list_pending_restaurants()
    if not rests:
        await msg.answer("✅ Kutayotgan ariza yo'q.", reply_markup=kb_main_superadmin())
        return
    for r in rests:
        text = (
            f"🏠 <b>{r['name']}</b>  |  {r['cuisine_type']}\n"
            f"🪑 {r['tables_count']} stol\n"
            f"💰 {r['price_min']:,} — {r['price_max']:,} so'm\n"
            f"📞 {r['phone']}\n"
            f"📍 {r['address']}\n"
            f"👤 Egasi: {r['owner_name']}"
        )
        await msg.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"restapprove_{r['id']}"),
                InlineKeyboardButton(text="❌ Rad etish",  callback_data=f"restreject_{r['id']}"),
            ]]),
        )


@router.callback_query(F.data.startswith("restapprove_"))
async def admin_approve(call: CallbackQuery):
    if call.from_user.id not in SUPER_ADMIN_IDS:
        return
    rid = int(call.data.split("_")[1])
    db_approve_restaurant(rid, 1)
    r = db_get_restaurant_by_id(rid)
    await call.message.edit_text(f"✅ <b>{r['name']}</b> tasdiqlandi!")
    try:
        await call.bot.send_message(
            r["owner_tg_id"],
            "🎉 <b>Restoraningiz tasdiqlandi!</b>\nEndi mijozlar stol bron qila oladi.",
            reply_markup=kb_main_restaurant(),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("restreject_"))
async def admin_reject(call: CallbackQuery):
    if call.from_user.id not in SUPER_ADMIN_IDS:
        return
    rid = int(call.data.split("_")[1])
    db_approve_restaurant(rid, 2)
    r = db_get_restaurant_by_id(rid)
    await call.message.edit_text(f"❌ <b>{r['name']}</b> rad etildi.")
    try:
        await call.bot.send_message(
            r["owner_tg_id"],
            "❌ <b>Restoraningiz rad etildi.</b>\nBatafsil ma'lumot uchun admin bilan bog'laning.",
        )
    except Exception:
        pass


@router.message(F.text == "📊 Statistika")
async def global_stats(msg: Message):
    tg_id = msg.from_user.id
    if tg_id in SUPER_ADMIN_IDS:
        s = db_global_stats()
        await msg.answer(
            "📊 <b>Umumiy statistika</b>\n\n"
            f"👤 Mijozlar: {s['customers']}\n"
            f"🏠 Faol restoranlar: {s['restaurants']}\n"
            f"⏳ Kutayotgan arizalar: {s['pending_rests']}\n"
            f"📋 Jami bronlar: {s['bookings_total']}\n"
            f"✅ Tasdiqlangan bronlar: {s['bookings_confirmed']}",
            reply_markup=kb_main_superadmin(),
        )
        return

    # Restoran statistikasi
    user = db_get_user(tg_id)
    if not user or user["role"] != "restaurant":
        return
    stats = db_restaurant_stats(tg_id)
    if not stats:
        await msg.answer("❗ Restoran topilmadi.")
        return
    await msg.answer(
        f"📈 <b>{stats['name']} — Statistika</b>\n\n"
        f"📋 Jami bronlar: {stats['total'] or 0}\n"
        f"⏳ Kutilmoqda: {stats['pending'] or 0}\n"
        f"✅ Tasdiqlangan: {stats['confirmed'] or 0}\n"
        f"❌ Rad etilgan: {stats['rejected'] or 0}\n"
        f"🚫 Bekor qilingan: {stats['cancelled'] or 0}",
        reply_markup=kb_main_restaurant(),
    )

# ── MIJOZ: STOL BRON QILISH ──────────────────────────────────────────────────

@router.message(F.text == "🍽 Restoran tanlash")
async def customer_choose_start(msg: Message, state: FSMContext):
    user = db_get_user(msg.from_user.id)
    if not user or user["role"] != "customer":
        await msg.answer("❗ Avval ro'yxatdan o'ting. /start")
        return
    cuisines = db_list_cuisines()
    if not cuisines:
        await msg.answer("😔 Hozircha faol restoranlar yo'q.")
        return
    await msg.answer(
        "🍜 <b>Oshxona turini tanlang</b> yoki barcha restoranlarni ko'ring:",
        reply_markup=kb_cuisines(cuisines),
    )
    await state.set_state(BookingFSM.choose_cuisine)


@router.callback_query(BookingFSM.choose_cuisine, F.data.startswith("cuisine_"))
async def choose_cuisine(call: CallbackQuery, state: FSMContext):
    cuisine = call.data.replace("cuisine_", "")
    if cuisine == "all":
        rests = db_list_approved_restaurants()
    else:
        rests = db_list_restaurants_by_cuisine(cuisine)

    if not rests:
        await call.message.edit_text("😔 Bu tur bo'yicha restoran topilmadi.")
        await state.clear()
        return

    await state.update_data(cuisine=cuisine)
    await call.message.edit_text(
        "🏠 <b>Restoran tanlang:</b>",
        reply_markup=kb_restaurants(rests),
    )
    await state.set_state(BookingFSM.choose_restaurant)


@router.callback_query(BookingFSM.choose_restaurant, F.data.startswith("rest_"))
async def choose_restaurant(call: CallbackQuery, state: FSMContext):
    rid = int(call.data.split("_")[1])
    rest = db_get_restaurant_by_id(rid)
    if not rest:
        await call.answer("Restoran topilmadi!", show_alert=True)
        return

    await state.update_data(restaurant_id=rid, restaurant_name=rest["name"])

    text = (
        f"🏠 <b>{rest['name']}</b>\n"
        f"🍜 {rest['cuisine_type']}\n"
        f"🪑 Stollar: {rest['tables_count']}\n"
        f"💰 {rest['price_min']:,} — {rest['price_max']:,} so'm\n"
        f"📞 {rest['phone']}\n"
        f"📍 {rest['address']}\n\n"
        "📅 Sanani tanlang:"
    )
    now = datetime.now()
    await call.message.edit_text(text, reply_markup=kb_inline_calendar(now.year, now.month))

    # Lokatsiya alohida yuborish
    if rest["latitude"] and rest["longitude"]:
        try:
            await call.bot.send_location(call.from_user.id, rest["latitude"], rest["longitude"])
        except Exception:
            pass

    await state.set_state(BookingFSM.choose_date)


# Kalendar navigatsiya
@router.callback_query(F.data.startswith("calprev_"))
async def cal_prev(call: CallbackQuery):
    _, year, month = call.data.split("_")
    year, month = int(year), int(month)
    month -= 1
    if month < 1:
        month, year = 12, year - 1
    await call.message.edit_reply_markup(reply_markup=kb_inline_calendar(year, month))


@router.callback_query(F.data.startswith("calnext_"))
async def cal_next(call: CallbackQuery):
    _, year, month = call.data.split("_")
    year, month = int(year), int(month)
    month += 1
    if month > 12:
        month, year = 1, year + 1
    await call.message.edit_reply_markup(reply_markup=kb_inline_calendar(year, month))


@router.callback_query(F.data == "cal_noop")
async def cal_noop(call: CallbackQuery):
    await call.answer()


@router.callback_query(BookingFSM.choose_date, F.data.startswith("calday_"))
async def choose_date(call: CallbackQuery, state: FSMContext):
    _, year, month, day = call.data.split("_")
    date_str = f"{year}-{int(month):02d}-{int(day):02d}"
    await state.update_data(booking_date=date_str)
    await call.message.edit_text(
        f"📅 Sana: <b>{date_str}</b>\n\n⏰ Vaqtni tanlang:",
        reply_markup=kb_time_slots(),
    )
    await state.set_state(BookingFSM.choose_time)


@router.callback_query(BookingFSM.choose_time, F.data.startswith("time_"))
async def choose_time(call: CallbackQuery, state: FSMContext):
    time_str = call.data.replace("time_", "")
    await state.update_data(booking_time=time_str)
    await call.message.delete()
    await call.message.answer(
        f"⏰ Vaqt: <b>{time_str}</b>\n\n👥 Nechta kishi bo'lasizlar?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3")],
                [KeyboardButton(text="4"), KeyboardButton(text="5"), KeyboardButton(text="6+")],
                [KeyboardButton(text="⬅️ Ortga")],
            ],
            resize_keyboard=True,
        ),
    )
    await state.set_state(BookingFSM.guests_count)


@router.message(BookingFSM.guests_count)
async def choose_guests(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        data = await state.get_data()
        now = datetime.now()
        await msg.answer("📅 Sanani tanlang:", reply_markup=kb_inline_calendar(now.year, now.month))
        await state.set_state(BookingFSM.choose_date)
        return
    text = msg.text.strip()
    guests = 6 if text == "6+" else (int(text) if text.isdigit() and int(text) > 0 else None)
    if guests is None:
        await msg.answer("❗ Raqam kiriting.")
        return
    await state.update_data(guests_count=guests)
    await msg.answer(
        "📝 Izoh qo'shmoqchimisiz?\n"
        "<i>Masalan: deraza yonida, alohida xona, to'y</i>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="⏭ O'tkazib yuborish")],
                [KeyboardButton(text="⬅️ Ortga")],
            ],
            resize_keyboard=True,
        ),
    )
    await state.set_state(BookingFSM.note)


@router.message(BookingFSM.note)
async def booking_note(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.set_state(BookingFSM.guests_count)
        await msg.answer("Mehmonlar sonini kiriting:", reply_markup=kb_back())
        return
    note = None if msg.text in ["⏭ O'tkazib yuborish"] else msg.text.strip()
    await state.update_data(note=note)

    data = await state.get_data()
    rest = db_get_restaurant_by_id(data["restaurant_id"])
    summary = (
        f"📋 <b>Bron ma'lumotlari:</b>\n\n"
        f"🏠 Restoran: {rest['name']}\n"
        f"📅 Sana: {data['booking_date']}\n"
        f"⏰ Vaqt: {data['booking_time']}\n"
        f"👥 Mehmonlar: {data['guests_count']} kishi\n"
    )
    if note:
        summary += f"📝 Izoh: {note}\n"
    summary += "\nTasdiqlaysizmi?"

    await msg.answer(
        summary,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Tasdiqlash"), KeyboardButton(text="❌ Bekor qilish")],
            ],
            resize_keyboard=True,
        ),
    )
    await state.set_state(BookingFSM.confirm)


@router.message(BookingFSM.confirm)
async def booking_confirm(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("🚫 Bron bekor qilindi.", reply_markup=kb_main_customer())
        return
    if msg.text != "✅ Tasdiqlash":
        return

    data = await state.get_data()
    tg_id = msg.from_user.id
    rest = db_get_restaurant_by_id(data["restaurant_id"])
    user = db_get_user(tg_id)

    booking_id = db_create_booking(
        tg_id, data["restaurant_id"],
        data["booking_date"], data["booking_time"],
        data["guests_count"], data.get("note") or "",
    )
    await state.clear()

    await msg.answer(
        f"🎉 <b>Bron so'rovingiz yuborildi!</b>\n\n"
        f"🆔 Bron ID: #{booking_id}\n"
        f"🏠 {rest['name']}\n"
        f"📅 {data['booking_date']}  ⏰ {data['booking_time']}\n"
        f"👥 {data['guests_count']} kishi\n\n"
        "Restoran administratori tez orada tasdiqlaydi. ⏳",
        reply_markup=kb_main_customer(),
    )

    # Restoran adminga xabar
    notif = (
        f"🔔 <b>Yangi bron so'rovi!</b>\n\n"
        f"🆔 #{booking_id}\n"
        f"👤 {user['full_name']}  📞 {user['phone']}\n"
        f"📅 {data['booking_date']}  ⏰ {data['booking_time']}\n"
        f"👥 {data['guests_count']} kishi\n"
    )
    if data.get("note"):
        notif += f"📝 {data['note']}\n"

    try:
        await msg.bot.send_message(
            rest["owner_tg_id"], notif,
            reply_markup=kb_booking_action(booking_id),
        )
    except Exception as e:
        logger.warning(f"Adminga xabar yuborib bo'lmadi: {e}")

# ── RESTORAN ADMIN: BRONLARNI BOSHQARISH ─────────────────────────────────────

@router.message(F.text == "📊 Bronlar")
async def restaurant_bookings(msg: Message):
    user = db_get_user(msg.from_user.id)
    if not user or user["role"] != "restaurant":
        return
    rest = db_get_restaurant_by_owner(msg.from_user.id)
    if not rest or rest["is_approved"] != 1:
        await msg.answer("❗ Restoraningiz hali tasdiqlanmagan.")
        return

    pending = db_restaurant_bookings(msg.from_user.id, "pending")
    confirmed = db_restaurant_bookings(msg.from_user.id, "confirmed")

    if not pending and not confirmed:
        await msg.answer("📭 Bronlar yo'q.", reply_markup=kb_main_restaurant())
        return

    if pending:
        await msg.answer(f"⏳ <b>Kutayotgan so'rovlar ({len(pending)}):</b>")
        for b in pending[:10]:
            await msg.answer(
                format_booking_full(b, show_customer=True),
                reply_markup=kb_booking_action(b["id"]),
            )

    if confirmed:
        text = f"✅ <b>Tasdiqlangan bronlar ({len(confirmed)}):</b>\n\n"
        for b in confirmed[:15]:
            text += (
                f"• #{b['id']}  {b['booking_date']} {b['booking_time']}\n"
                f"  {b['customer_name']} ({b['customer_phone']})  👥{b['guests_count']}\n"
            )
        await msg.answer(text, reply_markup=kb_main_restaurant())


@router.callback_query(F.data.startswith("bconfirm_"))
async def confirm_booking_cb(call: CallbackQuery):
    booking_id = int(call.data.split("_")[1])
    booking = db_get_booking(booking_id)
    if not booking:
        await call.answer("Bron topilmadi!", show_alert=True)
        return
    # Faqat restoran egasi yoki super admin tasdiqlaydi
    if call.from_user.id not in SUPER_ADMIN_IDS and booking["owner_tg_id"] != call.from_user.id:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return
    db_update_booking_status(booking_id, "confirmed")
    await call.message.edit_text(
        call.message.text + "\n\n✅ <b>Tasdiqlandi!</b>"
    )
    try:
        await call.bot.send_message(
            booking["customer_tg_id"],
            f"🎉 <b>Broningiz tasdiqlandi!</b>\n\n"
            f"🆔 #{booking_id}\n"
            f"🏠 {booking['rest_name']}\n"
            f"📅 {booking['booking_date']}  ⏰ {booking['booking_time']}\n"
            f"👥 {booking['guests_count']} kishi\n\n"
            f"📞 Qo'shimcha: {booking['rest_phone']}",
        )
    except Exception:
        pass
    await call.answer("✅ Tasdiqlandi!")


@router.callback_query(F.data.startswith("breject_"))
async def reject_booking_cb(call: CallbackQuery):
    booking_id = int(call.data.split("_")[1])
    booking = db_get_booking(booking_id)
    if not booking:
        await call.answer("Bron topilmadi!", show_alert=True)
        return
    if call.from_user.id not in SUPER_ADMIN_IDS and booking["owner_tg_id"] != call.from_user.id:
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return
    db_update_booking_status(booking_id, "rejected")
    await call.message.edit_text(call.message.text + "\n\n❌ <b>Rad etildi.</b>")
    try:
        await call.bot.send_message(
            booking["customer_tg_id"],
            f"😔 <b>Broningiz rad etildi.</b>\n\n"
            f"🆔 #{booking_id}\n"
            f"🏠 {booking['rest_name']}\n"
            f"📅 {booking['booking_date']}  ⏰ {booking['booking_time']}\n\n"
            "Boshqa vaqt yoki restoran tanlashingiz mumkin.",
        )
    except Exception:
        pass
    await call.answer("❌ Rad etildi!")

# ── MIJOZ: BRONLARIM ─────────────────────────────────────────────────────────

@router.message(F.text == "📋 Bronlarim")
async def my_bookings(msg: Message):
    user = db_get_user(msg.from_user.id)
    if not user or user["role"] != "customer":
        return
    bookings = db_customer_bookings(msg.from_user.id)
    if not bookings:
        await msg.answer("📭 Sizda hali bronlar yo'q.", reply_markup=kb_main_customer())
        return

    text = "📋 <b>Mening bronlarim:</b>\n\n"
    for b in bookings:
        text += format_booking_short(b) + "\n"
    await msg.answer(text, reply_markup=kb_main_customer())

    # Pending bronlar uchun bekor qilish tugmasi
    for b in bookings:
        if b["status"] == "pending":
            await msg.answer(
                f"#{b['id']} bronni bekor qilmoqchimisiz?",
                reply_markup=kb_cancel_booking(b["id"]),
            )


@router.callback_query(F.data.startswith("bcancel_"))
async def cancel_booking_cb(call: CallbackQuery):
    booking_id = int(call.data.split("_")[1])
    booking = db_get_booking(booking_id)
    if not booking or booking["customer_tg_id"] != call.from_user.id:
        await call.answer("Bron topilmadi!", show_alert=True)
        return
    db_update_booking_status(booking_id, "cancelled")
    await call.message.edit_text(f"🚫 Bron #{booking_id} bekor qilindi.")
    try:
        await call.bot.send_message(
            booking["owner_tg_id"],
            f"ℹ️ Mijoz <b>#{booking_id}</b> bronini bekor qildi.\n"
            f"👤 {booking['customer_name']}  📅 {booking['booking_date']} {booking['booking_time']}",
        )
    except Exception:
        pass
    await call.answer()

# ── MIJOZ: PROFIL ────────────────────────────────────────────────────────────

@router.message(F.text == "👤 Profilim")
async def my_profile(msg: Message):
    tg_id = msg.from_user.id
    user = db_get_user(tg_id)
    if not user:
        await msg.answer("❗ Avval ro'yxatdan o'ting. /start")
        return

    if user["role"] == "restaurant":
        rest = db_get_restaurant_by_owner(tg_id)
        status_map = {0: "⏳ Kutilmoqda", 1: "✅ Faol", 2: "❌ Rad etilgan"}
        text = (
            f"🏠 <b>Restoran Profili</b>\n\n"
            f"👤 Egasi: {user['full_name']}\n"
            f"📞 Tel: {user['phone']}\n"
        )
        if rest:
            text += (
                f"🏠 Restoran: {rest['name']}\n"
                f"🍜 {rest['cuisine_type']}\n"
                f"🪑 Stollar: {rest['tables_count']}\n"
                f"💰 {rest['price_min']:,} — {rest['price_max']:,} so'm\n"
                f"📞 {rest['phone']}\n"
                f"📍 {rest['address']}\n"
                f"📌 Holat: {status_map.get(rest['is_approved'], '?')}\n"
            )
        await msg.answer(text, reply_markup=kb_main_restaurant())
        if rest and rest["latitude"] and rest["longitude"]:
            await msg.answer_location(rest["latitude"], rest["longitude"])
    else:
        conn = get_db()
        total     = conn.execute("SELECT COUNT(*) FROM bookings WHERE customer_tg_id=?", (tg_id,)).fetchone()[0]
        confirmed = conn.execute("SELECT COUNT(*) FROM bookings WHERE customer_tg_id=? AND status='confirmed'", (tg_id,)).fetchone()[0]
        conn.close()
        await msg.answer(
            f"👤 <b>Mijoz Profili</b>\n\n"
            f"📛 Ism: {user['full_name']}\n"
            f"📞 Tel: {user['phone']}\n"
            f"📋 Jami bronlar: {total}\n"
            f"✅ Tasdiqlangan: {confirmed}\n"
            f"📅 Ro'yxatdan o'tgan: {user['created_at'][:10]}",
            reply_markup=kb_main_customer(),
        )

# ── RESTORAN: PROFIL TAHRIRLASH ──────────────────────────────────────────────

@router.message(F.text == "✏️ Profil tahrirlash")
async def edit_profile_menu(msg: Message, state: FSMContext):
    user = db_get_user(msg.from_user.id)
    if not user or user["role"] != "restaurant":
        return
    await msg.answer(
        "✏️ <b>Qaysi ma'lumotni o'zgartirmoqchisiz?</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏷 Nom",         callback_data="editrest_name"),
             InlineKeyboardButton(text="📞 Telefon",     callback_data="editrest_phone")],
            [InlineKeyboardButton(text="📍 Manzil",      callback_data="editrest_address"),
             InlineKeyboardButton(text="🪑 Stollar soni",callback_data="editrest_tables")],
            [InlineKeyboardButton(text="💰 Narxlar",     callback_data="editrest_price"),
             InlineKeyboardButton(text="📍 Manzil (lokatsiya)", callback_data="editrest_location")],
        ]),
    )
    await state.set_state(EditRestaurant.field)


@router.callback_query(EditRestaurant.field, F.data.startswith("editrest_"))
async def edit_field_selected(call: CallbackQuery, state: FSMContext):
    field = call.data.replace("editrest_", "")
    if field == "location":
        await call.message.delete()
        await call.message.answer(
            "📍 Yangi manzilni (lokatsiyani) ulashing:",
            reply_markup=kb_location(),
        )
        await state.set_state(EditRestaurant.location)
        return
    prompts = {
        "name":    "Yangi nom kiriting:",
        "phone":   "Yangi telefon raqami kiriting:",
        "address": "Yangi manzil kiriting:",
        "tables":  "Yangi stollar sonini kiriting:",
        "price":   "Yangi narx oralig'ini kiriting\n<i>Format: 50000-300000</i>",
    }
    await call.message.edit_text(prompts.get(field, "Yangi qiymat:"))
    await state.update_data(edit_field=field)
    await state.set_state(EditRestaurant.value)


@router.message(EditRestaurant.value)
async def edit_field_value(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.clear()
        await msg.answer("Tahrirlash bekor qilindi.", reply_markup=kb_main_restaurant())
        return
    data = await state.get_data()
    field = data["edit_field"]
    tg_id = msg.from_user.id
    conn = get_db()

    if field == "name":
        conn.execute("UPDATE restaurants SET name=? WHERE owner_tg_id=?", (msg.text.strip(), tg_id))
    elif field == "phone":
        conn.execute("UPDATE restaurants SET phone=? WHERE owner_tg_id=?", (msg.text.strip(), tg_id))
    elif field == "address":
        conn.execute("UPDATE restaurants SET address=? WHERE owner_tg_id=?", (msg.text.strip(), tg_id))
    elif field == "tables":
        if not msg.text.strip().isdigit():
            conn.close()
            await msg.answer("❗ Faqat raqam kiriting:")
            return
        conn.execute("UPDATE restaurants SET tables_count=? WHERE owner_tg_id=?", (int(msg.text.strip()), tg_id))
    elif field == "price":
        try:
            mn, mx = map(int, msg.text.strip().split("-"))
            conn.execute("UPDATE restaurants SET price_min=?, price_max=? WHERE owner_tg_id=?", (mn, mx, tg_id))
        except Exception:
            conn.close()
            await msg.answer("❗ Format: <code>50000-300000</code>")
            return

    conn.commit()
    conn.close()
    await state.clear()
    await msg.answer("✅ Ma'lumot yangilandi!", reply_markup=kb_main_restaurant())


@router.message(EditRestaurant.location)
async def edit_location_value(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.clear()
        await msg.answer("Tahrirlash bekor qilindi.", reply_markup=kb_main_restaurant())
        return
    if msg.text == "⏭ O'tkazib yuborish":
        await state.clear()
        await msg.answer("Tahrirlash bekor qilindi.", reply_markup=kb_main_restaurant())
        return
    if not msg.location:
        await msg.answer("❗ Iltimos, lokatsiyani tugma orqali ulashing:", reply_markup=kb_location())
        return
    lat = msg.location.latitude
    lon = msg.location.longitude
    tg_id = msg.from_user.id
    conn = get_db()
    conn.execute(
        "UPDATE restaurants SET latitude=?, longitude=? WHERE owner_tg_id=?",
        (lat, lon, tg_id),
    )
    conn.commit()
    conn.close()
    await state.clear()
    await msg.answer("✅ Manzil (lokatsiya) yangilandi!", reply_markup=kb_main_restaurant())

# ── MIJOZ: MENYU ─────────────────────────────────────────────────────────────

@router.message(F.text == "📜 Menyu")
async def show_menu(msg: Message):
    user = db_get_user(msg.from_user.id)
    if not user or user["role"] not in ("customer", "superadmin"):
        return
    rests = db_list_approved_restaurants()
    if not rests:
        await msg.answer("😔 Hozircha faol restoranlar yo'q.")
        return
    if len(rests) == 1:
        rest = rests[0]
        await send_restaurant_menu(msg, rest["id"], rest["name"])
    else:
        buttons = [
            [InlineKeyboardButton(text=r["name"], callback_data=f"menu_{r['id']}")]
            for r in rests
        ]
        await msg.answer(
            "🏠 <b>Qaysi restoran menyusini ko'rmoqchisiz?</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )


async def send_restaurant_menu(msg, rest_id: int, rest_name: str):
    menu = db_get_menu(rest_id)
    rating = db_get_avg_rating(rest_id)
    stars = "⭐" * round(rating["avg"]) if rating["avg"] else "—"
    text = f"📜 <b>{rest_name} — Menyu</b>\n"
    text += f"⭐ Reyting: {rating['avg']} / 5  ({rating['count']} ovoz)\n\n"
    if not menu:
        text += "Menyu hali qo'shilmagan."
    else:
        for section in menu:
            cat = section["category"]
            text += f"{cat['emoji']} <b>{cat['name']}</b>\n"
            for item in section["items"]:
                text += f"  • {item['name']}: <b>{item['price']:,} so'm</b>\n"
            text += "\n"
    await msg.answer(text)


@router.callback_query(F.data.startswith("menu_"))
async def menu_callback(call: CallbackQuery):
    rest_id = int(call.data.split("_")[1])
    rest = db_get_restaurant_by_id(rest_id)
    if not rest:
        await call.answer("Restoran topilmadi!", show_alert=True)
        return
    await call.message.delete()
    await send_restaurant_menu(call.message, rest_id, rest["name"])


# ── MIJOZ: BAHO BERISH ────────────────────────────────────────────────────────

@router.message(F.text == "⭐ Baho berish")
async def rate_start(msg: Message, state: FSMContext):
    user = db_get_user(msg.from_user.id)
    if not user or user["role"] != "customer":
        await msg.answer("❗ Avval mijoz sifatida ro'yxatdan o'ting. /start")
        return
    rests = db_list_approved_restaurants()
    if not rests:
        await msg.answer("😔 Hozircha faol restoranlar yo'q.")
        return
    buttons = [
        [InlineKeyboardButton(text=r["name"], callback_data=f"rate_rest_{r['id']}")]
        for r in rests
    ]
    await msg.answer(
        "🏠 <b>Qaysi restoranga baho bermoqchisiz?</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await state.set_state(RatingFSM.choose_restaurant)


@router.callback_query(RatingFSM.choose_restaurant, F.data.startswith("rate_rest_"))
async def rate_choose_rest(call: CallbackQuery, state: FSMContext):
    rest_id = int(call.data.split("_")[2])
    await state.update_data(rating_rest_id=rest_id)
    rating_buttons = [[
        InlineKeyboardButton(text="⭐ 1", callback_data="rating_1"),
        InlineKeyboardButton(text="⭐ 2", callback_data="rating_2"),
        InlineKeyboardButton(text="⭐ 3", callback_data="rating_3"),
        InlineKeyboardButton(text="⭐ 4", callback_data="rating_4"),
        InlineKeyboardButton(text="⭐ 5", callback_data="rating_5"),
    ]]
    await call.message.edit_text(
        "⭐ <b>Bahongizni tanlang (1-5 yulduz):</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rating_buttons),
    )
    await state.set_state(RatingFSM.give_rating)


@router.callback_query(RatingFSM.give_rating, F.data.startswith("rating_"))
async def rate_give(call: CallbackQuery, state: FSMContext):
    rating = int(call.data.split("_")[1])
    data = await state.get_data()
    rest_id = data["rating_rest_id"]
    db_add_rating(call.from_user.id, rest_id, rating)
    avg = db_get_avg_rating(rest_id)
    await state.clear()
    stars = "⭐" * rating
    await call.message.edit_text(
        f"{stars} <b>Rahmat! Bahongiz qabul qilindi.</b>\n\n"
        f"Umumiy reyting: <b>{avg['avg']} / 5</b> ({avg['count']} ovoz)"
    )
    await call.answer("✅ Baho berildi!")


# ── MIJOZ: IZOHLAR ────────────────────────────────────────────────────────────

@router.message(F.text == "💬 Izohlar")
async def comments_start(msg: Message, state: FSMContext):
    user = db_get_user(msg.from_user.id)
    if not user or user["role"] not in ("customer", "superadmin"):
        return
    rests = db_list_approved_restaurants()
    if not rests:
        await msg.answer("😔 Hozircha faol restoranlar yo'q.")
        return
    buttons = [
        [InlineKeyboardButton(text=r["name"], callback_data=f"cmt_rest_{r['id']}")]
        for r in rests
    ]
    await msg.answer(
        "💬 <b>Qaysi restoran izohlari?</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await state.set_state(CommentFSM.choose_restaurant)


@router.callback_query(CommentFSM.choose_restaurant, F.data.startswith("cmt_rest_"))
async def comments_choose(call: CallbackQuery, state: FSMContext):
    rest_id = int(call.data.split("_")[2])
    rest = db_get_restaurant_by_id(rest_id)
    comments = db_get_comments(rest_id)
    await state.update_data(comment_rest_id=rest_id)

    text = f"💬 <b>{rest['name']} — Izohlar</b>\n\n"
    if not comments:
        text += "Hali hech qanday izoh yo'q. Birinchi bo'lib izoh qoldiring!\n"
    else:
        for c in comments[:10]:
            text += f"👤 <b>{c['full_name']}</b>\n{c['text']}\n\n"

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✍️ Izoh qoldirish", callback_data=f"write_cmt_{rest_id}"),
        ]]),
    )


@router.callback_query(F.data.startswith("write_cmt_"))
async def write_comment_start(call: CallbackQuery, state: FSMContext):
    rest_id = int(call.data.split("_")[2])
    user = db_get_user(call.from_user.id)
    if not user or user["role"] != "customer":
        await call.answer("Avval mijoz sifatida ro'yxatdan o'ting!", show_alert=True)
        return
    await state.update_data(comment_rest_id=rest_id)
    await call.message.edit_text("✍️ <b>Izohingizni yozing:</b>")
    await state.set_state(CommentFSM.write_comment)


@router.message(CommentFSM.write_comment)
async def save_comment(msg: Message, state: FSMContext):
    if msg.text == "⬅️ Ortga":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=kb_main_customer())
        return
    data = await state.get_data()
    rest_id = data["comment_rest_id"]
    db_add_comment(msg.from_user.id, rest_id, msg.text.strip())
    await state.clear()
    await msg.answer("✅ <b>Izohingiz qabul qilindi!</b> Rahmat 🙏", reply_markup=kb_main_customer())


# ── MIJOZ: LOKATSIYA ──────────────────────────────────────────────────────────

@router.message(F.text == "📍 Lokatsiya")
async def show_location(msg: Message):
    user = db_get_user(msg.from_user.id)
    if not user or user["role"] not in ("customer", "superadmin"):
        return
    rests = db_list_approved_restaurants()
    approved_with_location = [r for r in rests if r.get("latitude") and r.get("longitude")]
    if not approved_with_location:
        await msg.answer(
            "📍 <b>Restoran manzili:</b>\n\n"
            "🏪 ALI DONER\n"
            "📞 99-910-80-50\n"
            "📍 Toshkent shahri\n\n"
            "<i>GPS lokatsiyasi hali qo'shilmagan.</i>"
        )
        return
    for rest in approved_with_location:
        await msg.answer(f"📍 <b>{rest['name']}</b> — {rest['address']}")
        await msg.bot.send_location(msg.from_user.id, rest["latitude"], rest["longitude"])


# ── MIJOZ: ALOQA ──────────────────────────────────────────────────────────────

@router.message(F.text == "📞 Aloqa")
async def show_contact(msg: Message):
    await msg.answer(
        "📞 <b>Bog'lanish ma'lumotlari</b>\n\n"
        "🏪 <b>ALI DONER</b>\n\n"
        "📞 Buyurtma va yetkazib berish:\n"
        "   <b>99-910-80-50</b>\n\n"
        "⏰ Ish vaqti: 09:00 — 22:00\n"
        "📍 Manzil: Toshkent shahri\n\n"
        "🚗 <b>Dastavka (yetkazib berish) mavjud!</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📞 Qo'ng'iroq qilish", url="tel:+998999108050"),
        ]]),
    )


# ── ESLATMA SCHEDULER ────────────────────────────────────────────────────────

async def send_reminders(bot: Bot):
    """Har 5 daqiqada ishlaydi — bron vaqtidan 1 soat oldin eslatma yuboradi"""
    bookings = db_reminders_due()
    for b in bookings:
        try:
            await bot.send_message(
                b["customer_tg_id"],
                f"⏰ <b>Eslatma!</b>\n\n"
                f"Bugun broningiz <b>1 soatdan so'ng</b> boshlanadi:\n\n"
                f"🏠 {b['rest_name']}\n"
                f"📅 {b['booking_date']}  ⏰ {b['booking_time']}\n"
                f"👥 {b['guests_count']} kishi\n"
                f"📞 {b['rest_phone']}",
            )
            db_mark_reminder_sent(b["id"])
            logger.info(f"Eslatma yuborildi: booking #{b['id']}")
        except Exception as e:
            logger.error(f"Eslatma xatosi (#{b['id']}): {e}")

# ── YORDAM ───────────────────────────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(msg: Message):
    user = db_get_user(msg.from_user.id)
    if user and user["role"] == "restaurant":
        text = (
            "🏠 <b>Restoran egasi uchun yordam:</b>\n\n"
            "📊 <b>Bronlar</b> — yangi so'rovlar va tasdiqlangan bronlar\n"
            "🏠 <b>Mening restoranim</b> — profil ma'lumotlari va lokatsiya\n"
            "✏️ <b>Profil tahrirlash</b> — nom, telefon, manzil, narxlarni o'zgartirish\n"
            "📈 <b>Statistika</b> — bronlar bo'yicha hisobot\n\n"
            "<i>Yangi bron kelganda sizga avtomatik xabar yuboriladi.</i>"
        )
    elif user and user["role"] == "superadmin":
        text = (
            "👑 <b>Super Admin uchun yordam:</b>\n\n"
            "🛂 <b>Kutayotgan restoranlar</b> — arizalarni ko'rib chiqish\n"
            "📊 <b>Statistika</b> — umumiy tizim statistikasi\n"
        )
    else:
        text = (
            "👤 <b>Mijoz uchun yordam:</b>\n\n"
            "🍽 <b>Restoran tanlash</b> — oshxona turi bo'yicha restoran qidirish\n"
            "📋 <b>Bronlarim</b> — bronlar tarixi va holati, bekor qilish\n"
            "👤 <b>Profilim</b> — shaxsiy ma'lumotlar\n\n"
            "<i>Broningiz tasdiqlanganidan so'ng, boshlanishidan 1 soat oldin eslatma olasiz.</i>"
        )
    await msg.answer(text)

# ── NOMAʼLUM XABAR ───────────────────────────────────────────────────────────

@router.message()
async def unknown(msg: Message):
    user = db_get_user(msg.from_user.id)
    if not user:
        await msg.answer("Salom! Boshlash uchun /start bosing.")
        return
    if user["role"] == "restaurant":
        await msg.answer("❓ Quyidagi tugmalardan foydalaning:", reply_markup=kb_main_restaurant())
    elif msg.from_user.id in SUPER_ADMIN_IDS:
        await msg.answer("❓ Tugmalardan foydalaning:", reply_markup=kb_main_superadmin())
    else:
        await msg.answer("❓ Quyidagi tugmalardan foydalaning:", reply_markup=kb_main_customer())

# ─── MAIN ──────────────────────────────────────────────────────────────────────

async def main():
    init_db()
    seed_data()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Eslatma scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, "interval", minutes=5, args=[bot])
    scheduler.start()

    logger.info("🚀 RestaurantBot ishga tushdi!")
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())