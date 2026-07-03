from sqlalchemy import select, update, delete
from database.engine import async_session
from database.models import MenuCategory, MenuItem

async def db_add_menu_category(restaurant_id: int, name: str) -> MenuCategory:
    async with async_session() as session:
        async with session.begin():
            category = MenuCategory(restaurant_id=restaurant_id, name=name)
            session.add(category)
            await session.commit()
            return category

async def db_get_menu_categories(restaurant_id: int) -> list[MenuCategory]:
    async with async_session() as session:
        query = select(MenuCategory).where(MenuCategory.restaurant_id == restaurant_id).order_by(MenuCategory.id)
        result = await session.execute(query)
        return list(result.scalars().all())

async def db_add_menu_item(category_id: int, name: str, description: str, price: int, photo_file_id: str = None) -> MenuItem:
    async with async_session() as session:
        async with session.begin():
            item = MenuItem(
                category_id=category_id,
                name=name,
                description=description,
                price=price,
                photo_file_id=photo_file_id,
                is_available=True
            )
            session.add(item)
            await session.commit()
            return item

async def db_get_menu_items(category_id: int, only_available: bool = True) -> list[MenuItem]:
    async with async_session() as session:
        query = select(MenuItem).where(MenuItem.category_id == category_id)
        if only_available:
            query = query.where(MenuItem.is_available == True)
        query = query.order_by(MenuItem.id)
        result = await session.execute(query)
        return list(result.scalars().all())

async def db_get_full_menu(restaurant_id: int, only_available: bool = True) -> list[dict]:
    async with async_session() as session:
        # Get categories
        categories = await db_get_menu_categories(restaurant_id)
        full_menu = []
        for cat in categories:
            items = await db_get_menu_items(cat.id, only_available)
            full_menu.append({
                "category": cat,
                "items": items
            })
        return full_menu

async def db_update_menu_item_availability(item_id: int, is_available: bool) -> bool:
    async with async_session() as session:
        async with session.begin():
            item = await session.get(MenuItem, item_id)
            if item:
                item.is_available = is_available
                await session.commit()
                return True
            return False

async def db_delete_menu_item(item_id: int) -> bool:
    async with async_session() as session:
        async with session.begin():
            # Doing a soft-delete (setting availability to False) is better for historical bookings
            item = await session.get(MenuItem, item_id)
            if item:
                item.is_available = False
                await session.commit()
                return True
            return False
