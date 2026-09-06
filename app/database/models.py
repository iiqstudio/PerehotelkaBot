from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class WishStatus(StrEnum):
    WAITING_FIRST_REVIEW = "waiting_first_review"
    WAITING_QUARANTINE = "waiting_quarantine"
    READY_FOR_DECISION = "ready_for_decision"
    RESEARCHING = "researching"
    FINAL_PAUSE = "final_pause"
    DECIDED_TO_BUY = "decided_to_buy"
    PURCHASED = "purchased"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64))
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_start: Mapped[time] = mapped_column(Time, default=time(22, 0))
    quiet_hours_end: Mapped[time] = mapped_column(Time, default=time(9, 0))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    wishes: Mapped[list["Wish"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Wish(Base):
    __tablename__ = "wishes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    estimated_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchase_type: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_alternative: Mapped[str | None] = mapped_column(Text, nullable=True)
    no_purchase_consequence: Mapped[str | None] = mapped_column(Text, nullable=True)
    criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    first_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    quarantine_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    first_review_answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    post_purchase_rating: Mapped[str | None] = mapped_column(String(32), nullable=True)
    post_purchase_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="wishes")
    options: Mapped[list["ProductOption"]] = relationship(back_populates="wish", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="wish", cascade="all, delete-orphan")


class ProductOption(Base):
    __tablename__ = "product_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    wish_id: Mapped[int] = mapped_column(ForeignKey("wishes.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    wish: Mapped[Wish] = relationship(back_populates="options")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("wish_id", "event_type", name="uq_notification_wish_event"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    wish_id: Mapped[int] = mapped_column(ForeignKey("wishes.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    wish: Mapped[Wish] = relationship(back_populates="notifications")
