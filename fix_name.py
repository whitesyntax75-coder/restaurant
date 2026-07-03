import sqlite3
conn = sqlite3.connect('restaurantbot.db')
conn.execute("UPDATE restaurants SET name='ALI DONER'")
conn.commit()
rows = conn.execute("SELECT id, name FROM restaurants").fetchall()
print("Yangilangan:", rows)
conn.close()
