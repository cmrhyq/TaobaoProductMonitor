"""
SQLAlchemy ORM models.
Maps to the existing database schema (users, products, price_history, monitor_rules, notification_log).
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, Index, Boolean
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    products = relationship("Product", back_populates="user", lazy="dynamic")


class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    platform = Column(String(50), nullable=False, default="淘宝")
    product_url = Column(Text, nullable=False)
    product_name = Column(String(500), nullable=False)
    product_tk = Column(String(100), nullable=True)
    item_id = Column(String(100), nullable=True)
    monitor_status = Column(Integer, nullable=False, default=10)
    notify_email = Column(String(200), nullable=False)
    initial_price = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    lowest_price = Column(Float, nullable=True)
    last_check_at = Column(DateTime, nullable=True)
    check_count = Column(Integer, nullable=False, default=0)
    fail_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="products")
    price_history = relationship("PriceHistory", back_populates="product", lazy="dynamic")
    rules = relationship("MonitorRule", back_populates="product", lazy="dynamic")
    notifications = relationship("NotificationLog", back_populates="product", lazy="dynamic")

    __table_args__ = (
        Index("idx_products_user_id", "user_id"),
        Index("idx_products_monitor_status", "monitor_status"),
        Index("idx_products_item_id", "item_id"),
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    price = Column(Float, nullable=False)
    fetch_method = Column(String(50), nullable=False, default="api")
    is_valid = Column(Integer, nullable=False, default=1)
    recorded_at = Column(DateTime, default=datetime.now)

    product = relationship("Product", back_populates="price_history")

    __table_args__ = (
        Index("idx_price_history_product_id", "product_id"),
        Index("idx_price_history_recorded_at", "recorded_at"),
    )


class MonitorRule(Base):
    __tablename__ = "monitor_rules"

    rule_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    rule_type = Column(String(50), nullable=False, default="absolute_drop")
    threshold_value = Column(Float, nullable=True)
    threshold_percent = Column(Float, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.now)

    product = relationship("Product", back_populates="rules")

    __table_args__ = (
        Index("idx_monitor_rules_product_id", "product_id"),
    )


class NotificationLog(Base):
    __tablename__ = "notification_log"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    rule_id = Column(Integer, ForeignKey("monitor_rules.rule_id"), nullable=True)
    notify_type = Column(String(50), nullable=False, default="email")
    notify_target = Column(String(200), nullable=False)
    notify_content = Column(Text, nullable=True)
    notify_status = Column(Integer, nullable=False, default=1)
    sent_at = Column(DateTime, default=datetime.now)

    product = relationship("Product", back_populates="notifications")

    __table_args__ = (
        Index("idx_notification_log_product_id", "product_id"),
    )
