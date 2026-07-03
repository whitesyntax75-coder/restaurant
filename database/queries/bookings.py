from sqlalchemy import select, update, func, and_, or_
from database.engine import async_session
from database.models import Booking, Restaurant, User, Review
from datetime import date, datetime, time

async def db_create_booking(user_id: int, restaurant_id: int, booking_date: date, booking_time: time, guests_count: int) -> Booking:
    async with async_session() as session:
        async with session.begin():
            booking = Booking(
                user_id=user_id,
                restaurant_id=restaurant_id,
                booking_date=booking_date,
                booking_time=booking_time,
                guests_count=guests_count,
                status='pending'
            )
            session.add(booking)
            await session.commit()
            return booking

async def db_get_booking_by_id(booking_id: int) -> Booking:
    async with async_session() as session:
        query = select(Booking).where(Booking.id == booking_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

async def db_update_booking_status(booking_id: int, status: str, rejection_reason: str = None, reminder_job_id: str = None) -> bool:
    async with async_session() as session:
        async with session.begin():
            booking = await session.get(Booking, booking_id)
            if booking:
                booking.status = status
                if rejection_reason is not None:
                    booking.rejection_reason = rejection_reason
                if reminder_job_id is not None:
                    booking.reminder_job_id = reminder_job_id
                await session.commit()
                return True
            return False

async def db_list_user_bookings(user_id: int) -> list[Booking]:
    async with async_session() as session:
        # Load user bookings along with restaurant info
        query = select(Booking).where(Booking.user_id == user_id).order_by(Booking.booking_date.desc(), Booking.booking_time.desc())
        result = await session.execute(query)
        return list(result.scalars().all())

async def db_list_restaurant_bookings(restaurant_id: int, status: str = None) -> list[Booking]:
    async with async_session() as session:
        query = select(Booking).where(Booking.restaurant_id == restaurant_id)
        if status:
            query = query.where(Booking.status == status)
        query = query.order_by(Booking.booking_date.asc(), Booking.booking_time.asc())
        result = await session.execute(query)
        return list(result.scalars().all())

async def db_get_overlapping_bookings_count(restaurant_id: int, booking_date: date, booking_time: time) -> int:
    async with async_session() as session:
        # Define 1-hour overlap window. An overlap happens if booking is within 1 hour of another.
        # For simplicity, we check bookings on the same date where the time difference is less than 1 hour.
        # Since SQL time math is DB-dependent, we will fetch bookings for the day and check overlaps in python,
        # or do a simple time boundary query. Let's do time boundary query:
        # overlap if booking_time - 1h < b.booking_time < booking_time + 1h
        
        # Calculate time boundaries
        dt = datetime.combine(date.today(), booking_time)
        start_dt = dt - timedelta(minutes=59)
        end_dt = dt + timedelta(minutes=59)
        
        query = select(func.count(Booking.id)).where(
            Booking.restaurant_id == restaurant_id,
            Booking.booking_date == booking_date,
            Booking.status.in_(['pending', 'confirmed']),
            Booking.booking_time >= start_dt.time(),
            Booking.booking_time <= end_dt.time()
        )
        result = await session.execute(query)
        return result.scalar() or 0

# Helper import for overlap
from datetime import timedelta

async def db_get_stats() -> dict:
    async with async_session() as session:
        users_count = await session.scalar(select(func.count(User.user_id)))
        rests_count = await session.scalar(select(func.count(Restaurant.id)))
        
        today = date.today()
        today_bookings = await session.scalar(select(func.count(Booking.id)).where(Booking.booking_date == today))
        
        # Current month bookings
        first_day_of_month = date(today.year, today.month, 1)
        month_bookings = await session.scalar(select(func.count(Booking.id)).where(Booking.booking_date >= first_day_of_month))
        
        # Top restaurants (ordered by booking count)
        top_query = select(
            Restaurant.name,
            func.count(Booking.id).label("booking_count")
        ).join(Booking).group_by(Restaurant.id).order_by(func.count(Booking.id).desc()).limit(5)
        top_result = await session.execute(top_query)
        top_rests = [{"name": row.name, "count": row.booking_count} for row in top_result.fetchall()]
        
        return {
            "users_total": users_count or 0,
            "restaurants_total": rests_count or 0,
            "bookings_today": today_bookings or 0,
            "bookings_month": month_bookings or 0,
            "top_restaurants": top_rests
        }
