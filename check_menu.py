import sqlite3
conn = sqlite3.connect('restaurantbot.db')
rest = conn.execute('SELECT id FROM restaurants WHERE name=?', ('DJIGAR',)).fetchone()
print('DJIGAR id:', rest)
if rest:
    cats = conn.execute('SELECT id, name FROM menu_categories WHERE restaurant_id=?', (rest[0],)).fetchall()
    print('Kategoriyalar soni:', len(cats))
    for cat in cats:
        items = conn.execute('SELECT name, price FROM menu_items WHERE category_id=?', (cat[0],)).fetchall()
        print(f'  Kategoriya: {cat[1]}')
        for item in items:
            print(f'    - {item[0]}: {item[1]}')
conn.close()
