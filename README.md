# 🤖 RESTAURANTBOT — TO'LIQ TEXNIK TOPSHIRIQ (System Prompt / PRD) v2.0

Siz aiogram 3.x, PostgreSQL va Redis asosida production-ready, asinxron Telegram bot — **RestaurantBot** — yozadigan tajribali Python dasturchisiz. Quyidagi arxitektura, ma'lumotlar bazasi, holatlar (FSM) va biznes-mantiqqa qat'iy rioya qiling.

> Ushbu versiya asl hujjatdagi quyidagi kamchiliklarni tuzatadi: stol sig'imi tekshiruvi yo'qligi, bron to'qnashuvlari, soxta sharhlar imkoniyati, scheduler'ning restart'da ishlarni yo'qotishi, pagination yo'qligi, FSM state'lar noaniqligi, va middleware/xatolarni boshqarish yetarli darajada ochilmaganligi.

---

## 🛠 TECH STACK

- **Til:** Python 3.11+
- **Framework:** aiogram 3.x (Router, Filter, Magic Filter `F`, FSMContext)
- **DB:** PostgreSQL — asinxron, `asyncpg` + `SQLAlchemy 2.0 (async ORM)` yoki toza `asyncpg` + `Alembic` migratsiyalari bilan
- **FSM Storage:** Redis (`RedisStorage`) — restart'da state saqlanishi uchun
- **Scheduler:** `APScheduler` + **`SQLAlchemyJobStore` (Postgres'ga bog'langan)** — bu MUHIM tuzatish: jobstore yozilmasa, bot restart bo'lganda barcha eslatmalar yo'qoladi. Timezone: `Asia/Tashkent`.
- **Konfiguratsiya:** `.env` orqali — `BOT_TOKEN`, `SUPER_ADMIN_ID`, `DB_URL`, `REDIS_URL`, `PAGE_SIZE=8`
- **Logging:** `logging` moduli + fayl/konsolga chiqish, xatolar uchun alohida logger
- **Anti-spam:** Throttling middleware (bir foydalanuvchi soniyasiga 1 ta so'rov)

---

## 🗂 DATABASE SCHEMA (TUZATILGAN)

```sql
-- 1. Users
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    full_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('user','restaurant_admin','super_admin')),
    is_blocked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Restaurants
CREATE TABLE restaurants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    cuisine_type VARCHAR(100) NOT NULL,
    address TEXT NOT NULL,
    phone VARCHAR(20) NOT NULL,
    avg_price INT NOT NULL,
    total_tables INT NOT NULL CHECK (total_tables > 0),
    admin_id BIGINT REFERENCES users(user_id),
    is_approved BOOLEAN DEFAULT FALSE,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_restaurants_cuisine ON restaurants(cuisine_type) WHERE is_approved = TRUE;

-- 3. Bookings
CREATE TABLE bookings (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    restaurant_id INT REFERENCES restaurants(id),
    booking_date DATE NOT NULL,
    booking_time TIME NOT NULL,
    guests_count INT NOT NULL CHECK (guests_count > 0),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','confirmed','rejected','cancelled','completed')),
    rejection_reason TEXT,
    reminder_job_id VARCHAR(64),  -- APScheduler job id, bekor qilinsa job ham o'chiriladi
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_bookings_restaurant_date ON bookings(restaurant_id, booking_date, booking_time)
    WHERE status IN ('pending','confirmed');  -- to'qnashuvlarni tez tekshirish uchun

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
    price INT NOT NULL CHECK (price > 0),
    photo_file_id VARCHAR(255),   -- Telegram file_id, rasm bilan ko'rsatish uchun
    is_available BOOLEAN DEFAULT TRUE
);

-- 6. Reviews — endi FAQAT tugagan bron orqali qoldiriladi (soxta sharhlarning oldini oladi)
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    booking_id INT UNIQUE REFERENCES bookings(id),   -- bir bron = bitta sharh
    user_id BIGINT REFERENCES users(user_id),
    restaurant_id INT REFERENCES restaurants(id),
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Nega o'zgardi:**
- `reviews.booking_id` qo'shildi va `UNIQUE` qilindi — endi faqat haqiqatan tashrif buyurgan (`status='completed'`) foydalanuvchi va har bir bron uchun bitta marta sharh qoldira oladi.
- `bookings.reminder_job_id` — bron bekor qilinsa yoki rad etilsa, tegishli APScheduler jobini ham bekor qilish uchun.
- Indekslar qo'shildi — bron to'qnashuvini tekshirish va restoran qidirishni tezlashtirish uchun.

---

## 🔁 BRON TO'QNASHUVI VA SIG'IM NAZORATI (yangi, asl hujjatda yo'q edi)

Booking yaratishdan oldin bot majburiy tekshiradi:

1. **Sana/vaqt validatsiyasi:** faqat bugundan +7 kungacha, vaqt 09:00–23:00 oralig'ida, va agar sana=bugun bo'lsa, vaqt hozirgi vaqtdan kamida 30 daqiqa keyin bo'lishi kerak.
2. **Sig'im nazorati:** Har bir vaqt oralig'i (masalan, 1 soatlik slot) uchun shu restoranda band qilingan (`pending`+`confirmed`) bronlar sonini `total_tables` bilan solishtiradi. Agar limit to'lgan bo'lsa — "Kechirasiz, bu vaqtga barcha stollar band. Boshqa vaqt tanlang" deb javob beradi va foydalanuvchiga bo'sh vaqt oraliqlarini taklif qiladi.
3. Faqat shundan keyin `pending` sifatida DB'ga yoziladi.

---

## 📱 FSM STATES (aniq belgilangan)

```python
class RegistrationState(StatesGroup):
    waiting_name = State()
    waiting_phone = State()

class BookingState(StatesGroup):
    choosing_restaurant = State()
    choosing_date = State()
    choosing_time = State()
    entering_guests = State()
    confirming = State()

class ReviewState(StatesGroup):
    choosing_booking = State()
    choosing_rating = State()
    entering_comment = State()

class RestaurantRegisterState(StatesGroup):  # yangi — asl hujjatda oqim ochiq qoldirilgan edi
    entering_name = State()
    entering_cuisine = State()
    entering_address = State()
    entering_phone = State()
    entering_avg_price = State()
    entering_tables = State()

class MenuManageState(StatesGroup):
    adding_category_name = State()
    choosing_category_for_item = State()
    entering_item_name = State()
    entering_item_description = State()
    entering_item_price = State()
    entering_item_photo = State()

class RejectReasonState(StatesGroup):
    waiting_reason = State()
```

---

## 👥 CLIENT MENU (to'liq oqim)

### `/start` → Ro'yxatdan o'tish (agar yo'q bo'lsa)
1. "Ismingizni kiriting" → `waiting_name`
2. "📱 Telefon raqamni yuborish" tugmasi (`request_contact=True`) → `waiting_phone`
3. DB'ga yozadi, rolga qarab tegishli asosiy menyuga yo'naltiradi.

### 🏠 Asosiy menyu
`🔍 Restoran Izlash` | `📅 Mening Bronlarim` | `✍️ Fikr va Baho Qoldirish` | `📞 Yordam / Aloqa` | `🏪 Restoranimni Ro'yxatdan O'tkazish`

*(oxirgi tugma yangi — foydalanuvchi o'z restoranini qo'shishni shu yerdan boshlaydi, natija Super Admin tasdig'iga tushadi)*

- **🔍 Restoran Izlash**
  - Cuisine turlari bo'yicha inline ro'yxat → tanlangan turdagi tasdiqlangan restoranlar, **8 tadan pagination bilan** (`⬅️ 1/3 ➡️`)
  - Restoran profili: nomi, manzili, o'rtacha narxi, reytingi (o'rtacha `rating`, sharhlar soni bilan)
  - `[📅 Stol Band Qilish]` `[🍽 Menyuni Ko'rish]` `[🔙 Orqaga]`

- **📅 Stol Band Qilish** — yuqoridagi to'qnashuv/sig'im nazorati bilan. Muvaffaqiyatli yaratilgach:
  - Restoran adminiga: mijoz ismi, tel, sana, vaqt, mehmonlar soni + `[✅ Tasdiqlash]` `[❌ Rad etish]`
  - Mijozga: "So'rovingiz adminga yuborildi ⏳"

- **🍽 Menyuni Ko'rish** — kategoriyalar → taomlar (rasm bo'lsa `photo_file_id` bilan), faqat `is_available=TRUE` bo'lganlar, pagination bilan.

- **📅 Mening Bronlarim** — holat bo'yicha ranglar (🟡/🟢/🔴/⚪ bekor qilingan). Faol (`pending`/`confirmed`) bronlar uchun `[❌ Bekor qilish]` tugmasi — bosilsa status `cancelled`ga o'tadi va bog'liq eslatma jobi bekor qilinadi.

- **✍️ Fikr va Baho Qoldirish** — faqat `status='completed'` va hali `reviews`da yozuvi yo'q bronlar ro'yxatidan tanlanadi (soxta sharhning oldi olinadi). ⭐1–5 → izoh matni yoki `/skip`.

---

## 🏪 RESTORAN ADMIN MENYUSI

`📈 Yangi Bron So'rovlari` | `📊 Barcha Bronlar` | `🛠 Profilni Tahrirlash` | `🍱 Menyuni Boshqarish`

- **Tasdiqlash** → status=`confirmed`, mijozga xabar, va **shu daqiqada** `booking_time - 30 daqiqa`ga eslatma job'i APScheduler'ga qo'yiladi (`job_id` DB'ga yoziladi).
- **Rad etish** → sababni so'raydi (`RejectReasonState`) → status=`rejected`, mijozga sababi bilan xabar.
- **Barcha Bronlar** — sana bo'yicha filtrlash imkoniyati bilan, pagination.
- **Menyuni Boshqarish** — kategoriya/taom qo'shish, tahrirlash, `is_available` ni o'chirib-yoqish (o'chirish o'rniga — buyurtma tarixi buzilmasligi uchun soft-delete tavsiya etiladi).

---

## 👑 SUPER ADMIN MENYUSI

`⏳ Kutilayotgan Restoranlar` | `📊 Umumiy Statistika` | `🚫 Foydalanuvchini Bloklash`

- **Tasdiqlash** → `is_approved=TRUE`, foydalanuvchi roli `restaurant_admin`ga o'zgaradi, xabar yuboriladi.
- **Rad etish** → sababi bilan xabar, restoran yozuvi saqlanadi (qayta yuborish imkoniyati uchun) yoki o'chiriladi — tanlov beriladi.
- **Umumiy Statistika** — jami foydalanuvchilar, restoranlar, bugungi/oylik bronlar soni, eng ko'p buyurtma qilingan restoranlar (oddiy SQL agregatsiyasi).

---

## ⏰ AVTOMATLASHTIRISH

1. Barcha vaqt hisob-kitoblari `Asia/Tashkent` bilan.
2. **Eslatma ishonchliligi:** APScheduler `SQLAlchemyJobStore` bilan ishga tushiriladi — bot qayta ishga tushganda ham rejalashtirilgan eslatmalar yo'qolmaydi. `main.py` startup'ida barcha `confirmed` va kelajakdagi bronlar uchun job mavjudligini tekshirib, yo'q bo'lsa qayta yaratadi (idempotent reconciliation).
3. Booking vaqti o'tib ketgan `confirmed` bronlar avtomatik `completed` statusga o'tkaziladi (kunlik cron job, soat 03:00da) — shundan keyingina onlar sharh qoldirish ro'yxatida ko'rinadi.
4. Eslatma matni:
   > 🔔 Eslatma! Bugun soat [Vaqt] da [Restoran Nomi] restoranida joyingiz band qilingan. Sizni kutib qolamiz!

---

## 🧱 LOYIHA STRUKTURASI

```
.
├── main.py
├── config.py
├── database/
│   ├── models.py
│   ├── engine.py
│   └── queries/
│       ├── users.py
│       ├── restaurants.py
│       ├── bookings.py
│       ├── menu.py
│       └── reviews.py
├── handlers/
│   ├── common.py          # /start, ro'yxatdan o'tish, yordam
│   ├── user/
│   │   ├── search.py
│   │   ├── booking.py
│   │   ├── my_bookings.py
│   │   └── reviews.py
│   ├── restaurant_admin/
│   │   ├── bookings.py
│   │   ├── menu.py
│   │   └── profile.py
│   └── super_admin/
│       ├── approval.py
│       └── stats.py
├── keyboards/
│   ├── user_kb.py
│   ├── admin_kb.py
│   └── super_admin_kb.py
├── states.py
├── middlewares/
│   ├── role_middleware.py     # rolga qarab handler'ga ruxsat
│   ├── throttling.py          # anti-spam
│   └── error_middleware.py    # global xatolarni ushlab, log qilib, UX buzilmasligini ta'minlaydi
├── services/
│   ├── scheduler.py           # APScheduler init + jobstore
│   └── availability.py        # sig'im/to'qnashuv tekshiruvi
├── utils/
│   └── pagination.py
├── seed_data.py
├── .env.example
└── requirements.txt
```

---

## ✅ QO'SHIMCHA TALABLAR

- Har bir DB so'rov `try/except` bilan o'ralgan, xatolar `error_middleware.py` orqali markazlashtirilgan holda log qilinadi va foydalanuvchiga tushunarli xabar ko'rsatiladi ("Xatolik yuz berdi, birozdan so'ng urinib ko'ring").
- `role_middleware` — har bir handler kirishdan oldin foydalanuvchi rolini tekshiradi; ruxsatsiz urinishlar log qilinadi.
- `seed_data()` — bo'sh jadvallarni namunaviy ma'lumotlar bilan to'ldiradi (masalan, "Milliy Taomlar" turkumida 2 ta restoran, har birida 2 kategoriya va 4-5 taom).
- Kod PEP 8 ga mos, type hint'lar bilan, har bir modul yagona mas'uliyat tamoyiliga (SRP) amal qiladi.

---

Generate the full code using this corrected specification, following clean, async, PEP 8-compliant Python architecture exactly as outlined above.
