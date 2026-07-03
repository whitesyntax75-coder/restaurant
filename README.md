# 🤖 RESTAURANTBOT — SYSTEM PROMPT & SPECIFICATION

You are an expert Python developer specializing in Telegram bots. Your task is to build a production-ready, asynchronous Telegram bot named **RestaurantBot** using **aiogram 3.x**, **PostgreSQL** (via `asyncpg` or `SQLAlchemy`), and **Redis** for FSM storage. The bot must strictly adhere to the architecture, menus, and business logic detailed below.

---

## 🛠 TECH STACK & PRODUCTION ARCHITECTURE

* **Language:** Python 3.10+ (Asynchronous clean code style).
* **Framework:** `aiogram 3.x` (using Routers, Filters, and Custom States).
* **Database:** PostgreSQL (All queries must be **asynchronous** to prevent blocking).
* **FSM Storage:** Redis (`RedisStorage`) to persist states across bot restarts.
* **Scheduler:** `APScheduler` mapped with `Asia/Tashkent` timezone for booking reminders.
* **Environment:** Configuration via `.env` (`BOT_TOKEN`, `SUPER_ADMIN_ID`, `DB_URL`, `REDIS_URL`).

---

## 🗂 DATABASE SCHEMA (POSTGRESQL)

```sql
-- 1. Users table
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    full_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' -- 'user', 'restaurant_admin', 'super_admin'
);

-- 2. Restaurants table
CREATE TABLE restaurants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    cuisine_type VARCHAR(100) NOT NULL,
    address TEXT NOT NULL,
    phone VARCHAR(20) NOT NULL,
    avg_price INT NOT NULL,
    total_tables INT NOT NULL,
    admin_id BIGINT REFERENCES users(user_id),
    is_approved BOOLEAN DEFAULT FALSE
);

-- 3. Bookings table
CREATE TABLE bookings (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    restaurant_id INT REFERENCES restaurants(id),
    booking_date DATE NOT NULL,
    booking_time TIME NOT NULL,
    guests_count INT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'confirmed', 'rejected'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Menu Categories
CREATE TABLE menu_categories (
    id SERIAL PRIMARY KEY,
    restaurant_id INT REFERENCES restaurants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL
);

-- 5. Menu Items
CREATE TABLE menu_items (
    id SERIAL PRIMARY KEY,
    category_id INT REFERENCES menu_categories(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price INT NOT NULL
);

-- 6. Ratings & Comments
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    restaurant_id INT REFERENCES restaurants(id),
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 📱 USER INTERFACE & MENUS (FLOW AND KEYBOARDS)

### 1. Registration Flow (For Unregistered Users)

* **Trigger:** `/start`
* **Action:** Bot checks if `user_id` exists in `users` table. If not, enters `RegistrationState`.
* **Step 1:** "Ismingizni kiriting:" -> Saves name.
* **Step 2:** "Telefon raqamingizni yuboring:" -> Keyboard: `[📱 Telefon raqamni yuborish (request_contact=True)]`.
* **Completion:** Saves to DB. Redirects to **Main Menu** based on role.

---

### 2. 👥 CLIENT (USER) MENU STRUCTURE

#### **🏠 Asosiy Menu (Main Menu)**

* `🔍 Restoran Izlash` | `📅 Mening Bronlarim`
* `✍️ Fikr va Baho Qoldirish` | `📞 Yordam / Aloqa`

---

#### **Sub-Menus & Logic (Client):**

* **🔍 Restoran Izlash:**
  * Inline list of unique `cuisine_type` (e.g., *Milliy Taomlar, Fast Food, Turk Taomlari*).
  * Clicking a category shows approved restaurants in that category.
  * Selecting a restaurant shows its Profile: **Nomi, Manzili, O'rtacha narxi, Reytingi (calculated from reviews)**.
  * **Inline Actions:** `[📅 Stol Band Qilish]` | `[🍽 Menyuni Ko'rish]` | `[🔙 Orqaga]`

* **📅 Stol Band Qilish (Booking Flow):**
  * *Step 1:* Inline calendar (or text format) to choose date (Only today and next 7 days).
  * *Step 2:* Choose time (Format: HH:MM, validate within 09:00 - 23:00).
  * *Step 3:* Enter number of guests (Input validation: Integer > 0).
  * *Action:* Inserts into DB as `pending`. Sends an **Immediate Alert** to the Restaurant Admin with `[Tasdiqlash]` / `[Rad Etish]` inline buttons. Tells user: "Sizning so'rovingiz adminga yuborildi."

* **🍽 Menyuni Ko'rish (EVOS / MaxWay Style):**
  * Fetches `menu_categories` for that restaurant. Displays as inline buttons.
  * Selecting a category displays all `menu_items` sequentially with details:
  > **🍔 [Taom Nomi]**
  > 📝 Tarkibi: [Description]
  > 💵 Narxi: [Price] UZS
  * Includes a `[🔙 Toifalarga qaytish]` button.

* **📅 Mening Bronlarim:**
  * Lists all active and past bookings for the user showing: *Restoran nomi, Sana, Vaqt, Holati (Kutilmoqda 🟡 / Tasdiqlandi 🟢 / Rad etildi 🔴)*.

* **✍️ Fikr va Baho Qoldirish:**
  * Shows a list of restaurants the user has previously booked and completed visits to.
  * *Step 1:* Choose Rating via inline stars: `[⭐ 1]` `[⭐ 2]` `[⭐ 3]` `[⭐ 4]` `[⭐ 5]`.
  * *Step 2:* "Restoran haqida o'z fikringizni matn ko'rinishida yozing (yoki /skip yuboring):"

---

### 3. 🏪 RESTAURANT ADMIN MENU STRUCTURE

#### **🏠 Admin Menu**

* `📈 Yangi Bron So'rovlari` | `📊 Barcha Bronlar Ro'yxati`
* `🛠 Restoran Profilini Tahrirlash` | `🍱 Menyuni Boshqarish`

---

#### **Sub-Menus & Logic (Restaurant Admin):**

* **📈 Yangi Bron So'rovlari:**
  * Shows list of `pending` bookings.
  * Each booking card has: *Mijoz ismi, Tel, Sana, Vaqt, Mehmonlar*.
  * **Actions:** `[✅ Tasdiqlash]` | `[❌ Rad etish]`.
  * *Trigger:* Clicking `Tasdiqlash` changes DB status to `confirmed`. Automatically sends a message to the Client: "Tabriklaymiz! Sizning [Sana] [Vaqt] dagi broningiz tasdiqlandi! 🟢".
  * *Trigger:* Clicking `Rad etish` prompts admin for a reason, changes status to `rejected`, and alerts the client: "Afsuski, sizning broningiz rad etildi. Sababi: [Reason] 🔴".

* **🍱 Menyuni Boshqarish:**
  * Options: `➕ Kategoriya Qo'shish` | `➕ Taom Qo'shish` | `❌ Taomni O'chirish`.
  * Allows dynamic asynchronous management of the restaurant's menu without touching the database manually.

* **🛠 Restoran Profilini Tahrirlash:**
  * Modify Address, Phone, Total Tables, or Average Price.

---

### 4. 👑 SUPER ADMIN MENU STRUCTURE

#### **🏠 Super Admin Menu**

* `⏳ Kutilayotgan Restoranlar` | `📊 Umumiy Statistika`

---

#### **Sub-Menus & Logic (Super Admin):**

* **⏳ Kutilayotgan Restoranlar (Verification System):**
  * When a user wants to register a restaurant, they submit details. It comes here as `is_approved = FALSE`.
  * Super admin sees: *Restoran nomi, Turi, Admin ID, Tel, Manzil*.
  * **Actions:** `[✅ Tasdiqlash (Approve)]` | `[❌ Haqiqiy emas (Reject)]`.
  * Approving updates `is_approved = TRUE`, and elevates that specific user's role to `restaurant_admin` in the `users` table, unlocking their Admin Menu.

---

## ⏰ AUTOMATION & SYSTEM IMPROVEMENTS

1. **Timezone Lock:** All scheduling using `APScheduler` and time computations must explicitly use the `Asia/Tashkent` timezone object.
2. **Smart Reminders:** When a booking is `confirmed`, schedule an automated job using `APScheduler` to send a Telegram message to the client exactly **30 minutes before** their scheduled `booking_time`:
> "🔔 **Eslatma!** Bugun soat [Vaqt] da [Restoran Nomi] restoranida joyingiz band qilingan. Sizni kutib qolamiz!"

---

## 🎯 IMPLEMENTATION STEPS FOR THE GENERATED CODE

1. Create a clean project structure: `main.py`, `config.py`, `database.py`, `handlers/` (user, admin, super_admin, common), `keyboards/`, `states.py`, and `middlewares/`.
2. Implement native error handling inside middleware to log errors without breaking the user experience.
3. Include a `seed_data()` function executed once on startup if the tables are empty, populating dummy data for categories (like *Burgerlar*, *Lavashlar*) and items with accurate pricing to demonstrate full functionality immediately.

Generate the full code using clean, PEP 8 compliant, highly maintainable async Python structures.
