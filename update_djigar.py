import sqlite3
conn = sqlite3.connect('restaurantbot.db')
conn.execute("UPDATE restaurants SET phone=? WHERE name=?", ('+998938273311', 'DJIGAR'))
conn.commit()
r = conn.execute("SELECT name, phone, address FROM restaurants WHERE name=?", ('DJIGAR',)).fetchone()
print('Yangilandi:', r)
conn.close()
