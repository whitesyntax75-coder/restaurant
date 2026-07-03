import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8855624248:AAFBK746GnZ_ei7wD7GGvTbu6cMvejxENv4")

# Super admins IDs, comma-separated
super_admin_env = os.getenv("SUPER_ADMIN_IDS", "7904389988")
SUPER_ADMIN_IDS = [int(i.strip()) for i in super_admin_env.split(",") if i.strip()]

# Database URL. Falls back to local SQLite using aiosqlite.
# Adjusts PostgreSQL protocols for asyncpg automatically.
DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///restaurantbot.db")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Redis URL for FSM. If empty, falls back to MemoryStorage.
REDIS_URL = os.getenv("REDIS_URL", "")

# Pagination page size
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "8"))
