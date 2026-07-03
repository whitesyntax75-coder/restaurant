import sqlite3
import os

# Update database
conn = sqlite3.connect('restaurantbot.db')
conn.execute("UPDATE restaurants SET name='ALI DONER'")
conn.commit()
conn.close()
print('DB updated.')

# Update main.py
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('SHRIFT X', 'ALI DONER')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('main.py updated.')
