# 🍽️ RestaurantBot - Stol Bron Qilish Tizimi

Ushbu loyiha restoranlar uchun mijozlar tomonidan onlayn stol band qilish (bron), menyuni ko'rish, restoranlarga baho berish va fikr qoldirish imkonini beruvchi to'laqonli Telegram bot hisoblanadi.

## 🛠 Texnologiyalar (Stack)
- **Dasturlash tili:** Python 3
- **Bot Framework:** [aiogram 3.x](https://docs.aiogram.dev/) (Telegram API bilan ishlash uchun zamonaviy asinxron kutubxona)
- **Ma'lumotlar bazasi:** SQLite3 (`restaurantbot.db` orqali lokal va yengil saqlash tizimi)
- **Vazifalarni rejalashtiruvchi:** APScheduler (Mijozlarga bron qilingan vaqtni eslatuvchi avtomatik xabarlar yuborish uchun)

## 🗂 Ma'lumotlar Bazasi Tuzilishi (Jadvallar)
Bot ishlashi uchun SQLite'da quyidagi jadvallardan foydalaniladi:
1. `users`: Barcha foydalanuvchilar, mijozlar va adminlarni saqlaydi.
2. `restaurants`: Tasdiqlangan va tasdiqlanmagan restoranlar ro'yxati (lokatsiya, narx, telefon va h.k).
3. `bookings`: Mijozlarning stol bronlari (sanasi, vaqti, mehmonlar soni va holati - pending/confirmed/rejected).
4. `menu_categories`: Har bir restoranga tegishli menyu toifalari (masalan, Burgerlar, Lavashlar).
5. `menu_items`: Aniq taomlar va ularning to'liq tarkibi (description) hamda narxlari.
6. `ratings`: Mijozlarning restoranlarga bergan 1 dan 5 gacha bo'lgan baholari.
7. `comments`: Mijozlarning restoran haqidagi izohlari.

## 🚀 Asosiy Imkoniyatlar (Features)

### 👥 Mijozlar uchun:
- **Ro'yxatdan o'tish:** Telefon raqami va ismini kiritish orqali.
- **Restoran tanlash:** Taomlar turiga (Cuisine) ko'ra restoran izlash.
- **Stol bron qilish:** Kerakli sana, vaqt (faqat ish soatlarida) va mehmonlar sonini tanlash.
- **Menyuni ko'rish:** Restoranlarning EVOS yoki MaxWay uslubidagi chiroyli, tavsifi va narxi keltirilgan to'liq menyusini ko'rish imkoniyati.
- **Baho va izoh:** Tashrif buyurilgan restoranlarga yulduzchalar va xabar orqali izoh qoldirish.

### 🏪 Restoran Adminlari uchun:
- **O'z restoranini qo'shish:** Nomi, turi, stollar soni, o'rtacha narxi va manzilini yuborish.
- **Bronlarni boshqarish:** Yangi tushgan buyurtmalarni tasdiqlash yoki bekor qilish. Barcha bronlarni to'liq (izoh va kontaktlari bilan) ko'rish.
- **Profilni tahrirlash:** Restoran ma'lumotlarini o'zgartirish.

### 👑 Super Admin (Boshqaruvchi) uchun:
- **Tasdiqlash tizimi:** Yangi qo'shilgan restoranlarni tekshirib, tizimga ruxsat berish (Approve) yoki rad etish.

## ⚙️ Ishga tushirish (Local va Deploy)
1. **Lokal ishga tushirish:** Kutubxonalarni o'rnatish (`pip install aiogram apscheduler`), token sozlamalarini to'g'rilash va `python main.py` orqali ishga tushirish. Bot birinchi marta yonganda avtomatik ravishda `seed_data()` orqali ma'lumotlar bazasiga standart restoranlarni (SHRIFT X, DJIGAR) va ularning menyularini kiritadi.
2. **Serverga yuklash (Deploy):** Loyiha `Procfile` yordamida Railway yoki shunga o'xshash bulutli serverlarga bevosita GitHub orqali joylanishiga (deploy) to'liq moslashtirilgan.

## ⚠️ Tizimning Kamchiliklari va Optimallashtirish (Production uchun)

Bot hozirgi holatida kichik va o
ta hajmdagi restoranlar uchun yaxshi ishlaydi. Biroq, foydalanuvchilar soni kopayganda (optimal ishlashi uchun) quyidagi kamchiliklarni tog
ilash tavsiya etiladi:

### 1. Malumotlar Bazasi (SQLite -> PostgreSQL)
- **Muammo:** Hozirda SQLite ishlatilmoqda. Agar minglab foydalanuvchilar bir vaqtda botdan foydalansa, SQLite database is locked xatosini berishi mumkin.
- **Yechim:** Ishonchli, tezkor va xavfsiz bolgan **PostgreSQL** malumotlar bazasiga o	ish va syncpg yoki SQLAlchemy orqali asinxron (bloklanmaydigan) so
ovlar yozish kerak.

### 2. Holatlarni Saqlash (MemoryStorage -> Redis)
- **Muammo:** Foydalanuvchi malumot kiritayotganda (FSM states) malumotlar bot xotirasida (MemoryStorage) saqlanadi. Agar Railway serveri ochib yonsa yoki kod yangilansa, barcha mijozlarning oxiriga yetkazilmagan jarayonlari (masalan, ovqat tanlab turgan joyi) ochib ketadi.
- **Yechim:** **Redis** xotirasini ulash (RedisStorage). Bu ham tezlikni oshiradi, ham bot ochib yonganda mijozlar qolgan joyidan davom etishini taminlaydi.

### 3. Kod Xavfsizligi (.env)
- **Muammo:** Bot tokeni va Super Admin IDlari kabi maxfiy malumotlar tog
idan-tog
i main.py kodining ichida yozilgan.
- **Yechim:** Ushbu malumotlarni .env faylga kochirish va kodga os.getenv() orqali chaqirish kerak.

### 4. Savat (Cart) va Yetkazib berish (Delivery) yoqligi
- **Muammo:** Botda chiroyli va toliq menyu bor, lekin mijozlar faqat stol band qila oladi. Ular menyudan taom tanlab, Savatga (Cart) qoshib, uylariga yetkazib berishni buyurtma qila olishmaydi.
- **Yechim:** Savat va Tolov (Click/Payme) integratsiyasini qoshib, tolaqonli yetkazib berish (Delivery) xizmatini yolga qoyish.

### 5. Bloklanadigan DB so
ovlari (Synchronous DB)
- **Muammo:** sqlite3 kutubxonasi Asinxron emas. Ya
i bazaga yozish vaqtida bot qolgan mijozlarni biroz kutib turishga majbur qiladi.
- **Yechim:** Asinxron kutubxonalarga (masalan, iosqlite yoki syncpg) o	ish orqali botning bir vaqtda o
 minglab xabarlarni qotmasdan qayta ishlashiga erishish mumkin.

### 6. Vaqt mintaqasi (Timezone)
- **Muammo:** APScheduler yordamida yuboriladigan eslatmalar (reminders) serverning vaqtiga qarab ketib qolishi mumkin (UTC). 
- **Yechim:** Barcha sana va vaqt amaliyotlarini aniq Asia/Tashkent vaqt mintaqasida ishlashini qatiy belgilab qoyish.
