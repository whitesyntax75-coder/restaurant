from sqlalchemy import select, update, func
from database.engine import async_session
from database.models import Restaurant, Review, User

async def db_add_restaurant(name: str, cuisine_type: str, address: str, phone: str, avg_price: int, total_tables: int, admin_id: int) -> Restaurant:
    async with async_session() as session:
        async with session.begin():
            # Check if restaurant exists for this owner
            query = select(Restaurant).where(Restaurant.admin_id == admin_id)
            result = await session.execute(query)
            restaurant = result.scalar_one_or_none()
            if not restaurant:
                restaurant = Restaurant(
                    name=name,
                    cuisine_type=cuisine_type,
                    address=address,
                    phone=phone,
                    avg_price=avg_price,
                    total_tables=total_tables,
                    admin_id=admin_id,
                    is_approved=False
                )
                session.add(restaurant)
            else:
                restaurant.name = name
                restaurant.cuisine_type = cuisine_type
                restaurant.address = address
                restaurant.phone = phone
                restaurant.avg_price = avg_price
                restaurant.total_tables = total_tables
                restaurant.is_approved = False  # Reset approval on edit
                restaurant.rejection_reason = None
            await session.commit()
            return restaurant

async def db_get_restaurant_by_id(restaurant_id: int) -> Restaurant:
    async with async_session() as session:
        query = select(Restaurant).where(Restaurant.id == restaurant_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

async def db_get_restaurant_by_owner(admin_id: int) -> Restaurant:
    async with async_session() as session:
        query = select(Restaurant).where(Restaurant.admin_id == admin_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

async def db_list_approved_restaurants() -> list[Restaurant]:
    async with async_session() as session:
        query = select(Restaurant).where(Restaurant.is_approved == True).order_by(Restaurant.id)
        result = await session.execute(query)
        return list(result.scalars().all())

async def db_list_restaurants_by_cuisine(cuisine_type: str) -> list[Restaurant]:
    async with async_session() as session:
        query = select(Restaurant).where(Restaurant.cuisine_type == cuisine_type, Restaurant.is_approved == True).order_by(Restaurant.id)
        result = await session.execute(query)
        return list(result.scalars().all())

async def db_approve_restaurant(restaurant_id: int, is_approved: bool, rejection_reason: str = None) -> bool:
    async with async_session() as session:
        async with session.begin():
            restaurant = await session.get(Restaurant, restaurant_id)
            if restaurant:
                restaurant.is_approved = is_approved
                restaurant.rejection_reason = rejection_reason
                if is_approved:
                    # Update owner role to restaurant_admin
                    user = await session.get(User, restaurant.admin_id)
                    if user:
                        user.role = 'restaurant_admin'
                await session.commit()
                return True
            return False

async def db_list_pending_restaurants() -> list[Restaurant]:
    async with async_session() as session:
        query = select(Restaurant).where(Restaurant.is_approved == False, Restaurant.rejection_reason == None).order_by(Restaurant.id)
        result = await session.execute(query)
        return list(result.scalars().all())

async def db_get_cuisine_types() -> list[str]:
    async with async_session() as session:
        query = select(Restaurant.cuisine_type).where(Restaurant.is_approved == True).distinct()
        result = await session.execute(query)
        return list(result.scalars().all())

async def db_get_restaurant_rating(restaurant_id: int) -> dict:
    async with async_session() as session:
        query = select(
            func.coalesce(func.avg(Review.rating), 0.0).label("avg_rating"),
            func.count(Review.id).label("review_count")
        ).where(Review.restaurant_id == restaurant_id)
        result = await session.execute(query)
        row = result.fetchone()
        return {
            "avg": round(row.avg_rating, 1) if row else 0.0,
            "count": row.review_count if row else 0
        }
