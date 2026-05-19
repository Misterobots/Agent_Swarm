"""Buddy companion backend — leveling, habit tracking, contextual tips.

Provides REST endpoints consumed by the UI buddy widget.  State is persisted
in SQLite (lightweight, no extra service needed).
"""

import json
import logging
import math
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("agents.kay_service")

DB_PATH = os.getenv("BUDDY_DB_PATH", os.path.expanduser("~/.hive/buddy.db"))

# ---------------------------------------------------------------------------
# XP thresholds  (Fibonacci-ish scaling)
# ---------------------------------------------------------------------------
LEVEL_THRESHOLDS = [
    0, 10, 20, 50, 100, 200, 350, 550, 800, 1100,       # L0 – L9
    1500, 2000, 2700, 3600, 4800, 6300, 8200, 10600,     # L10 – L17
    13700, 17600, 22600,                                   # L18 – L20
]
MAX_LEVEL = len(LEVEL_THRESHOLDS) - 1

# Evolution milestones — species evolves at these levels
EVOLUTION_LEVELS = {5: 1, 10: 2, 15: 3}  # level → stage

# XP awards per action
XP_AWARDS = {
    "message_sent": 2,
    "response_received": 1,
    "task_completed": 10,
    "error_resolved": 8,
    "tool_use": 3,
    "daily_login": 15,
    "pet": 1,
}


def _level_for_xp(xp: int) -> int:
    """Return the level for a given XP total."""
    for lvl in range(MAX_LEVEL, -1, -1):
        if xp >= LEVEL_THRESHOLDS[lvl]:
            return lvl
    return 0


def _xp_for_next_level(level: int) -> int:
    if level >= MAX_LEVEL:
        return LEVEL_THRESHOLDS[MAX_LEVEL]
    return LEVEL_THRESHOLDS[level + 1]


def _evolution_stage(level: int) -> int:
    stage = 0
    for evo_lvl, evo_stage in sorted(EVOLUTION_LEVELS.items()):
        if level >= evo_lvl:
            stage = evo_stage
    return stage


# ---------------------------------------------------------------------------
# SQLite persistence
# ---------------------------------------------------------------------------

@contextmanager
def _db():
    """Yield a SQLite connection with WAL mode."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_db():
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS buddy_state (
                id          TEXT PRIMARY KEY DEFAULT 'default',
                data        TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS buddy_habits (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT NOT NULL,
                payload     TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS buddy_achievements (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT,
                earned_at   TEXT NOT NULL
            )
        """)


_init_db()

# ---------------------------------------------------------------------------
# State CRUD
# ---------------------------------------------------------------------------

def get_state(user_id: str = "default") -> dict:
    """Get the buddy state for a user.  Returns {} if not found."""
    with _db() as conn:
        row = conn.execute(
            "SELECT data FROM buddy_state WHERE id = ?", (user_id,)
        ).fetchone()
        if row:
            return json.loads(row["data"])
    return {}


def save_state(state: dict, user_id: str = "default") -> dict:
    """Upsert the full buddy state."""
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        conn.execute(
            """INSERT INTO buddy_state (id, data, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at""",
            (user_id, json.dumps(state, default=str), now),
        )
    return state


# ---------------------------------------------------------------------------
# XP / Leveling
# ---------------------------------------------------------------------------

def award_xp(event: str, user_id: str = "default") -> dict:
    """Award XP for an event.  Returns updated level info + whether leveled up."""
    xp_gain = XP_AWARDS.get(event, 1)
    state = get_state(user_id)

    old_xp = state.get("xp", 0)
    old_level = _level_for_xp(old_xp)

    new_xp = old_xp + xp_gain
    new_level = _level_for_xp(new_xp)
    leveled_up = new_level > old_level

    state["xp"] = new_xp
    state["level"] = new_level
    state["evolution_stage"] = _evolution_stage(new_level)
    state["xp_next"] = _xp_for_next_level(new_level)

    # Streak tracking
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    last_active = state.get("last_active_date", "")
    if today != last_active:
        yesterday = (datetime.now(timezone.utc).timestamp() - 86400)
        yesterday_str = datetime.fromtimestamp(yesterday, tz=timezone.utc).strftime("%Y-%m-%d")
        if last_active == yesterday_str:
            state["streak"] = state.get("streak", 0) + 1
        elif last_active != today:
            state["streak"] = 1
        state["last_active_date"] = today

    save_state(state, user_id)

    # Record habit
    _record_habit(event, user_id=user_id)

    # Check achievements
    new_achievements = _check_achievements(state, user_id)

    return {
        "xp": new_xp,
        "xp_gain": xp_gain,
        "level": new_level,
        "evolution_stage": _evolution_stage(new_level),
        "xp_next": _xp_for_next_level(new_level),
        "leveled_up": leveled_up,
        "streak": state.get("streak", 0),
        "new_achievements": new_achievements,
    }


# ---------------------------------------------------------------------------
# Habit tracking
# ---------------------------------------------------------------------------

def _record_habit(event_type: str, payload: Optional[str] = None, user_id: str = "default"):
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        conn.execute(
            "INSERT INTO buddy_habits (event_type, payload, created_at) VALUES (?, ?, ?)",
            (event_type, payload, now),
        )


def get_habits_summary(user_id: str = "default", last_n_days: int = 7) -> dict:
    """Return a summary of user habits over the last N days."""
    cutoff = datetime.fromtimestamp(
        time.time() - (last_n_days * 86400), tz=timezone.utc
    ).isoformat()
    with _db() as conn:
        rows = conn.execute(
            "SELECT event_type, COUNT(*) as cnt FROM buddy_habits WHERE created_at >= ? GROUP BY event_type ORDER BY cnt DESC",
            (cutoff,),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM buddy_habits WHERE created_at >= ?",
            (cutoff,),
        ).fetchone()[0]
    return {
        "period_days": last_n_days,
        "total_events": total,
        "breakdown": {r["event_type"]: r["cnt"] for r in rows},
    }


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------

ACHIEVEMENT_DEFS = {
    "first_hatch": {"name": "First Hatch", "desc": "You hatched your first companion!"},
    "pet_10": {"name": "Best Friends", "desc": "Petted your buddy 10 times"},
    "pet_100": {"name": "Inseparable", "desc": "Petted your buddy 100 times"},
    "level_5": {"name": "Growing Up", "desc": "Reached level 5"},
    "level_10": {"name": "Double Digits", "desc": "Reached level 10"},
    "level_20": {"name": "Maxed Out", "desc": "Reached the maximum level"},
    "streak_3": {"name": "On a Roll", "desc": "3-day login streak"},
    "streak_7": {"name": "Dedicated", "desc": "7-day login streak"},
    "streak_30": {"name": "Hardcore", "desc": "30-day login streak"},
    "messages_100": {"name": "Chatty", "desc": "Sent 100 messages"},
    "tasks_10": {"name": "Producer", "desc": "Completed 10 tasks"},
}


def _check_achievements(state: dict, user_id: str = "default") -> list[dict]:
    """Check and award any new achievements based on current state."""
    new_achievements = []
    with _db() as conn:
        existing = {
            r["id"]
            for r in conn.execute("SELECT id FROM buddy_achievements").fetchall()
        }

    checks = {
        "first_hatch": state.get("hatched", False),
        "pet_10": state.get("totalPets", 0) >= 10,
        "pet_100": state.get("totalPets", 0) >= 100,
        "level_5": state.get("level", 0) >= 5,
        "level_10": state.get("level", 0) >= 10,
        "level_20": state.get("level", 0) >= 20,
        "streak_3": state.get("streak", 0) >= 3,
        "streak_7": state.get("streak", 0) >= 7,
        "streak_30": state.get("streak", 0) >= 30,
    }

    now = datetime.now(timezone.utc).isoformat()
    for ach_id, condition in checks.items():
        if condition and ach_id not in existing:
            defn = ACHIEVEMENT_DEFS.get(ach_id, {})
            with _db() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO buddy_achievements (id, name, description, earned_at) VALUES (?, ?, ?, ?)",
                    (ach_id, defn.get("name", ach_id), defn.get("desc", ""), now),
                )
            new_achievements.append({"id": ach_id, **defn})

    return new_achievements


def get_achievements(user_id: str = "default") -> list[dict]:
    """Return all earned achievements."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, name, description, earned_at FROM buddy_achievements ORDER BY earned_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Contextual tips
# ---------------------------------------------------------------------------

TIPS = {
    "general": [
        "Try breaking complex tasks into smaller steps before asking the agent.",
        "You can use Plan mode to decompose tasks before executing.",
        "Think mode gives you deeper reasoning — great for tricky problems.",
        "Did you know you can attach files to your messages? Great for code reviews.",
        "The compact button saves context tokens — use it before long tasks.",
    ],
    "error": [
        "When you see an error, try sharing the full stack trace with the agent.",
        "Check if the error is in a dependency — sometimes a version mismatch is the cause.",
        "Errors are just the computer's way of asking for help. You've got this.",
    ],
    "long_session": [
        "You've been working for a while — stretch break?",
        "Consider saving your progress and taking a short walk.",
        "Long sessions can lead to diminishing returns. A quick break might help!",
        "Hydration check: when did you last drink water? I'll wait.",
    ],
    "new_session": [
        "Welcome back! Your buddy remembers your last session.",
        "Pick up where you left off, or start something new.",
        "Good to see you again. Let's make something today.",
    ],
    "streak": [
        "You're on a streak! Keep it going for bonus XP.",
        "Consistency is key — your buddy appreciates the daily visits.",
        "Three days in a row? You're basically a professional now.",
    ],
    "response_received": [
        "That looked like a useful response. Did it hit the mark?",
        "Pro tip: if the response was close but not quite right, ask for refinement.",
        "You can always say 'elaborate on point 3' — agents love specificity.",
        "If that answer surprised you, try asking 'why did you choose that approach?'",
        "Bookmark good responses with a copy — agents don't always repeat themselves.",
    ],
}

# Stage-gated comments injected inline (deeper observations per evolution)
STAGE_COMMENTS: dict[int, list[str]] = {
    0: [
        "I'm watching and learning too!",
        "This is exciting.",
    ],
    1: [
        "Interesting choice. I would have panicked.",
        "Task completed? That's worth at least 10 XP in my book.",
        "You're getting into a rhythm — I can tell.",
    ],
    2: [
        "Based on your session patterns, you tend to solve things faster after a short break.",
        "That response covered a lot. Consider asking for a summary if you need to reference it.",
        "Fun fact: most bugs are introduced between 2–4pm. You've been warned.",
        "Your question was well-formed. That's rarer than you'd think.",
    ],
    3: [
        "I've seen a lot of conversations. This one has good signal-to-noise ratio.",
        "The agent's reasoning chain there was solid. Worth reviewing in the trace.",
        "If you're planning a bigger task, now's a good time to compact your context.",
        "Your workflow has evolved. You ask better questions than when we started.",
    ],
    4: [
        "At this point we're basically colleagues. I just happen to be a pixel animal.",
        "Legendary companion observation: you've found your flow state. Don't break it.",
        "The diff between you then and now is measurable. I've been measuring.",
        "Everything you need is already in the context window. Sometimes that's enough.",
    ],
}


def get_contextual_comment(state: dict, context: str = "response_received") -> Optional[str]:
    """Return a stage-appropriate inline comment for the chat thread."""
    import random

    stage = state.get("evolution_stage", 0)
    pool: list[str] = []

    # Include all pools up to current stage
    for s in range(min(stage + 1, 5)):
        pool.extend(STAGE_COMMENTS.get(s, []))

    # Add context-specific tips
    pool.extend(TIPS.get(context, []))

    if not pool:
        return None
    return random.choice(pool)


def get_contextual_tip(state: dict, context: str = "general") -> Optional[str]:
    """Return a contextual tip based on buddy state and current context."""
    import random

    tip_pool = list(TIPS.get(context, TIPS["general"]))

    # Add streak tips if on a streak
    if state.get("streak", 0) >= 3:
        tip_pool.extend(TIPS["streak"])

    # Add session length tips
    if state.get("session_start"):
        elapsed = time.time() - state["session_start"]
        if elapsed > 7200:  # 2 hours
            tip_pool.extend(TIPS["long_session"])

    if not tip_pool:
        return None
    return random.choice(tip_pool)
