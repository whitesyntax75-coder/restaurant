from sqlalchemy import Column, Integer, BigInteger, String, Boolean, ForeignKey, Date, Time, Text, DateTime, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from database.engine import Base

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=False)
    role = Column(String(20), default='user')
    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    restaurants = relationship("Restaurant", back_populates="admin")
    bookings = relationship("Booking", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    
    __table_args__ = (
        CheckConstraint(role.in_(['user', 'restaurant_admin', 'super_admin']), name='check_role_valid'),
    )

class Restaurant(Base):
    __tablename__ = 'restaurants'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    cuisine_type = Column(String(100), nullable=False)
    address = Column(Text, nullable=False)
    phone = Column(String(20), nullable=False)
    avg_price = Column(Integer, nullable=False)
    total_tables = Column(Integer, nullable=False)
    admin_id = Column(BigInteger, ForeignKey('users.user_id'))
    is_approved = Column(Boolean, default=False)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    admin = relationship("User", back_populates="restaurants")
    bookings = relationship("Booking", back_populates="restaurant")
    categories = relationship("MenuCategory", back_populates="restaurant", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="restaurant")
    
    __table_args__ = (
        CheckConstraint(total_tables > 0, name='check_total_tables_positive'),
    )

class Booking(Base):
    __tablename__ = 'bookings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'))
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'))
    booking_date = Column(Date, nullable=False)
    booking_time = Column(Time, nullable=False)
    guests_count = Column(Integer, nullable=False)
    status = Column(String(20), default='pending')
    rejection_reason = Column(Text, nullable=True)
    reminder_job_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="bookings")
    restaurant = relationship("Restaurant", back_populates="bookings")
    review = relationship("Review", uselist=False, back_populates="booking")

    __table_args__ = (
        CheckConstraint(guests_count > 0, name='check_guests_positive'),
        CheckConstraint(status.in_(['pending', 'confirmed', 'rejected', 'cancelled', 'completed']), name='check_status_valid'),
    )

class MenuCategory(Base):
    __tablename__ = 'menu_categories'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey('restaurants.id', ondelete='CASCADE'))
    name = Column(String(100), nullable=False)

    # Relationships
    restaurant = relationship("Restaurant", back_populates="categories")
    items = relationship("MenuItem", back_populates="category", cascade="all, delete-orphan")

class MenuItem(Base):
    __tablename__ = 'menu_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey('menu_categories.id', ondelete='CASCADE'))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    photo_file_id = Column(String(255), nullable=True)
    is_available = Column(Boolean, default=True)

    # Relationships
    category = relationship("MenuCategory", back_populates="items")

    __table_args__ = (
        CheckConstraint(price > 0, name='check_price_positive'),
    )

class Review(Base):
    __tablename__ = 'reviews'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey('bookings.id'), unique=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'))
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'))
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    booking = relationship("Booking", back_populates="review")
    user = relationship("User", back_populates="reviews")
    restaurant = relationship("Restaurant", back_populates="reviews")

    __table_args__ = (
        CheckConstraint(rating.between(1, 5), name='check_rating_between_1_5'),
    )
