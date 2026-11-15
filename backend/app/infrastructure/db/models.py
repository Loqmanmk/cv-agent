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

from app.domain.document import MAX_CV_BYTES
from app.domain.email_tokens import TOKEN_PURPOSES
from app.domain.oauth import PROVIDERS
from app.domain.plans import PLANS, USAGE_KINDS
from app.domain.profile import CV_LANGUAGES, GENDERS
from app.domain.tracker import STATUSES


def allowed(values: tuple[str, ...]) -> str:
    """The SQL list of the allowed values of a text column, for a CHECK constraint."""
    return ", ".join(f"'{value}'" for value in values)


class Base(DeclarativeBase):
    """Base of every table. Every constraint has an explicit name, so migrations stay stable."""


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        CheckConstraint(f"plan IN ({allowed(PLANS)})", name="ck_users_plan"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    plan: Mapped[str] = mapped_column(Text, server_default="free")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApplicationRecord(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(f"status IN ({allowed(STATUSES)})", name="ck_applications_status"),
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


class UserSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
        CheckConstraint("expires_at > created_at", name="ck_sessions_expiry_after_creation"),
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_sessions_user_id_users", ondelete="CASCADE"),
    )
    token_hash: Mapped[str] = mapped_column(Text)
    csrf_token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProfileRecord(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(f"gender IN ({allowed(GENDERS)})", name="ck_profiles_gender"),
        CheckConstraint(
            f"cv_language IN ({allowed(CV_LANGUAGES)})", name="ck_profiles_cv_language"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_profiles_user_id_users", ondelete="CASCADE"),
        primary_key=True,
    )
    address: Mapped[str] = mapped_column(Text, server_default="")
    city: Mapped[str] = mapped_column(Text, server_default="")
    gender: Mapped[str] = mapped_column(Text, server_default="m")
    cv_language: Mapped[str] = mapped_column(Text, server_default="fr")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        CheckConstraint(f"kind IN ({allowed(USAGE_KINDS)})", name="ck_usage_events_kind"),
        Index("ix_usage_events_user_id_kind_created_at", "user_id", "kind", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_usage_events_user_id_users", ondelete="CASCADE"),
    )
    kind: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailToken(Base):
    __tablename__ = "email_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_email_tokens_token_hash"),
        CheckConstraint(f"purpose IN ({allowed(TOKEN_PURPOSES)})", name="ck_email_tokens_purpose"),
        CheckConstraint("expires_at > created_at", name="ck_email_tokens_expiry_after_creation"),
        Index("ix_email_tokens_user_id_purpose", "user_id", "purpose"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_email_tokens_user_id_users", ondelete="CASCADE"),
    )
    purpose: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SavedCvRecord(Base):
    __tablename__ = "saved_cvs"
    __table_args__ = (
        CheckConstraint(
            f"octet_length(content) BETWEEN 1 AND {MAX_CV_BYTES}", name="ck_saved_cvs_content_size"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_saved_cvs_user_id_users", ondelete="CASCADE"),
        primary_key=True,
    )
    filename: Mapped[str] = mapped_column(Text)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OAuthIdentity(Base):
    __tablename__ = "oauth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_oauth_identities_provider_subject"),
        CheckConstraint(f"provider IN ({allowed(PROVIDERS)})", name="ck_oauth_identities_provider"),
        Index("ix_oauth_identities_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_oauth_identities_user_id_users", ondelete="CASCADE"),
    )
    provider: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
