from sqlalchemy import select, update
from database.engine import async_session
from database.models import User

async def db_add_user(user_id: int, username: str, full_name: str, phone_number: str, role: str = 'user') -> User:
    async with async_session() as session:
        async with session.begin():
            # Check if user exists
            query = select(User).where(User.user_id == user_id)
            result = await session.execute(query)
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    user_id=user_id,
                    username=username,
                    full_name=full_name,
                    phone_number=phone_number,
                    role=role
                )
                session.add(user)
            else:
                user.username = username
                user.full_name = full_name
                user.phone_number = phone_number
            await session.commit()
            return user

async def db_get_user(user_id: int) -> User:
    async with async_session() as session:
        query = select(User).where(User.user_id == user_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

async def db_block_user(user_id: int, is_blocked: bool) -> bool:
    async with async_session() as session:
        async with session.begin():
            query = update(User).where(User.user_id == user_id).values(is_blocked=is_blocked)
            result = await session.execute(query)
            await session.commit()
            return result.rowcount > 0
