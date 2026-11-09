import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.tracker import STATUSES

ALLOWED_STATUSES = ", ".join(f"'{status}'" for status in STATUSES)


class Base(DeclarativeBase):
    """Base of every table. Every constraint has an explicit name, so migrations stay stable."""


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApplicationRecord(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(f"status IN ({ALLOWED_STATUSES})", name="ck_applications_status"),
        Index("ix_applications_user_id_id", "user_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_applications_user_id_users", ondelete="CASCADE"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    job_title: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, server_default="")
    cv_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    letter_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    photo: Mapped[bytes | None] = mapped_column(LargeBinary)
    cv_pdf: Mapped[bytes] = mapped_column(LargeBinary)
    letter_pdf: Mapped[bytes] = mapped_column(LargeBinary)
