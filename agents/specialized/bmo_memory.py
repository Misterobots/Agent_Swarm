"""
BMO Conversation Memory — Persistent PostgreSQL-backed conversation history,
session summaries, and user profile memory for the BMO voice assistant.

Uses SQLAlchemy with sync engine (matching phi agent's sync .run() calls).
Tables auto-create on first use. 30-day rolling retention on raw messages,
permanent retention on summaries and user profiles.
"""

import logging
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, JSON,
    Index, text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logger = logging.getLogger("BMOMemory")

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

_DB_URL = os.getenv("AGNO_DB_URL")
_engine = None
_SessionFactory = None

Base = declarative_base()

RETENTION_DAYS = 30


def _get_session() -> Session:
    """Return a new DB session, lazily creating the engine + tables."""
    global _engine, _SessionFactory
    if _engine is None:
        if not _DB_URL:
            raise RuntimeError("AGNO_DB_URL not set — cannot use conversation memory")
        _engine = create_engine(_DB_URL, pool_pre_ping=True, pool_size=5)
        Base.metadata.create_all(_engine)
        _SessionFactory = sessionmaker(bind=_engine)
        logger.info("BMO memory tables initialized")
    return _SessionFactory()


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class BmoConversation(Base):
    __tablename__ = "bmo_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    role = Column(String(16), nullable=False)       # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_bmo_conv_session_created", "session_id", "created_at"),
    )


class BmoSessionSummary(Base):
    __tablename__ = "bmo_session_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, unique=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    summary = Column(Text, nullable=False)
    turn_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class BmoUserProfile(Base):
    __tablename__ = "bmo_user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, unique=True)
    facts = Column(JSON, nullable=False, default=list)   # list of fact strings
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Conversation CRUD
# ---------------------------------------------------------------------------

def save_message(session_id: str, role: str, content: str, user_id: str = "default") -> None:
    """Persist a single conversation turn."""
    db = _get_session()
    try:
        db.add(BmoConversation(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save message: {e}")
    finally:
        db.close()


def get_recent_messages(session_id: str, limit: int = 16) -> List[Dict[str, str]]:
    """Retrieve the last N messages for a session, ordered chronologically."""
    db = _get_session()
    try:
        rows = (
            db.query(BmoConversation)
            .filter(BmoConversation.session_id == session_id)
            .order_by(BmoConversation.created_at.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()  # oldest first
        return [{"role": r.role, "content": r.content} for r in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Session Summaries
# ---------------------------------------------------------------------------

def save_session_summary(session_id: str, summary: str,
                         turn_count: int, user_id: str = "default") -> None:
    """Store or update a session summary."""
    db = _get_session()
    try:
        existing = (
            db.query(BmoSessionSummary)
            .filter(BmoSessionSummary.session_id == session_id)
            .first()
        )
        if existing:
            existing.summary = summary
            existing.turn_count = turn_count
        else:
            db.add(BmoSessionSummary(
                session_id=session_id,
                user_id=user_id,
                summary=summary,
                turn_count=turn_count,
            ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save session summary: {e}")
    finally:
        db.close()


def get_recent_summaries(user_id: str = "default", limit: int = 3) -> List[str]:
    """Return the most recent session summaries for a user."""
    db = _get_session()
    try:
        rows = (
            db.query(BmoSessionSummary)
            .filter(BmoSessionSummary.user_id == user_id)
            .order_by(BmoSessionSummary.created_at.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return [r.summary for r in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# User Profile Memory
# ---------------------------------------------------------------------------

def get_user_profile(user_id: str = "default") -> List[str]:
    """Return the list of known facts about a user."""
    db = _get_session()
    try:
        profile = (
            db.query(BmoUserProfile)
            .filter(BmoUserProfile.user_id == user_id)
            .first()
        )
        if profile and profile.facts:
            return list(profile.facts)
        return []
    finally:
        db.close()


def update_user_profile(user_id: str, new_facts: List[str]) -> None:
    """Merge new facts into the user profile (deduplicates)."""
    db = _get_session()
    try:
        profile = (
            db.query(BmoUserProfile)
            .filter(BmoUserProfile.user_id == user_id)
            .first()
        )
        if profile:
            existing = set(profile.facts or [])
            existing.update(new_facts)
            profile.facts = list(existing)
        else:
            db.add(BmoUserProfile(user_id=user_id, facts=new_facts))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update user profile: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Retention Cleanup
# ---------------------------------------------------------------------------

def cleanup_old_messages(days: int = RETENTION_DAYS) -> int:
    """Delete conversation messages older than `days`. Returns count deleted."""
    db = _get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = (
            db.query(BmoConversation)
            .filter(BmoConversation.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(f"Cleaned up {count} messages older than {days} days")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"Retention cleanup failed: {e}")
        return 0
    finally:
        db.close()
