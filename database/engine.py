from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config import DB_URL

# Async SQLAlchemy engine
engine = create_async_engine(DB_URL, echo=False)

# Async session maker
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def init_models():
    # Automatically creates all tables defined in models.py
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
