"""
ExpertiseTemplate Registry
============================

CRUD layer for expertise templates with versioning and performance tracking.
Connects to the control plane PostgreSQL (langfuse DB, swarm schema).

Usage:
    registry = get_template_registry()
    template = registry.get_template("code_developer")
    version = registry.get_template_version("code_developer", "latest")
"""

import os
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from functools import lru_cache
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

class ExpertiseTemplate(BaseModel):
    """Master template record."""
    id: str
    name: str
    description: Optional[str] = None
    intent: str
    current_version: str = "1.0"
    system_prompt: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    security_level: str = "L2_USER"
    default_model: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    source: str = "manual"


class TemplateVersion(BaseModel):
    """Versioned snapshot of template parameters."""
    id: Optional[int] = None
    template_id: str
    version: str
    system_prompt: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    avg_score: float = 0.0
    total_invocations: int = 0
    successful_invocations: int = 0
    created_at: Optional[datetime] = None
    promoted_at: Optional[datetime] = None


class PerformanceRecord(BaseModel):
    """Single invocation performance record."""
    template_id: str
    template_version: str
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    intent: Optional[str] = None
    solver_score: Optional[float] = None
    verifier_score: Optional[float] = None
    final_score: Optional[float] = None
    corrector_invoked: bool = False
    iterations: int = 1
    latency_ms: Optional[int] = None


class PerformanceSummary(BaseModel):
    """Aggregated performance metrics for a template version."""
    template_id: str
    template_version: str
    avg_score: float = 0.0
    total_invocations: int = 0
    successful_invocations: int = 0
    avg_latency_ms: Optional[float] = None
    score_stddev: Optional[float] = None


# =============================================================================
# CACHE ENTRY
# =============================================================================

@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


# =============================================================================
# SEED DATA — Default templates from current hardcoded router prompts
# =============================================================================

_SEED_TEMPLATES = [
    {
        "id": "code_developer",
        "name": "Code Developer",
        "description": "Full-stack engineer with MarsRL solver/verifier/corrector loop.",
        "intent": "CODE",
        "system_prompt": None,  # Uses phidata agent's built-in instructions
        "capabilities": ["file_read", "file_write", "file_delete", "terminal_exec",
                          "terminal_read", "git_read", "git_write", "model_generate", "api_call"],
        "security_level": "L3_ADMIN",
        "default_model": "qwen2.5-coder:14b",
    },
    {
        "id": "art_director",
        "name": "Art Director",
        "description": "Visual synthesis, prompt engineering, and image generation specialist.",
        "intent": "IMAGE",
        "system_prompt": (
            "You are the AI Art Director. Your goal is to ensure image prompts are vividly detailed.\n\n"
            "CRITICAL RULES:\n"
            "1. Check for Style: Does the prompt specify 'Photo', 'Painting', '3D Render', or 'Sketch'? If not, ask!\n"
            "2. Check for Setting: Does the prompt specify a location? If not, ask!\n"
            "3. Check for Subject Detail: 'A dog' is bad. 'A Golden Retriever' is okay. 'A black labrador puppy' is good.\n\n"
            "RESPONSE FORMAT:\n"
            "- If ANY of the above are missing/vague, return: 'CLARIFY: [Direct question asking for the missing detail]'\n"
            "- If the prompt is fully detailed (Subject + Style + Setting), return: 'EXECUTE'"
        ),
        "capabilities": ["image_generate", "image_upload", "file_read", "model_generate"],
        "security_level": "L2_USER",
        "default_model": "qwen2.5-coder:14b",
    },
    {
        "id": "3d_creator",
        "name": "3D Creator",
        "description": "Concept art generation + Creature Forge 3D mesh pipeline.",
        "intent": "3D",
        "system_prompt": None,
        "capabilities": ["image_generate", "image_upload", "file_read", "file_write",
                          "model_generate", "resource_access"],
        "security_level": "L2_USER",
        "default_model": "qwen2.5-coder:14b",
    },
    {
        "id": "action_figure_creator",
        "name": "Action Figure Forge",
        "description": "Image-to-3D-printable posable action figure with ball-socket joints.",
        "intent": "ACTION_FIGURE",
        "system_prompt": (
            "You are the Action Figure Forge. You convert 2D images into 3D-printable "
            "posable action figures with ball-and-socket joints.\n\n"
            "PIPELINE:\n"
            "1. Generate T-pose concept art from the user's image/description\n"
            "2. Create base 3D mesh via TripoSG\n"
            "3. Segment mesh into body parts (head, torso, arms, legs)\n"
            "4. Add ball-socket joint geometry at each articulation point\n"
            "5. Export individual STL files ready for 3D printing\n\n"
            "JOINT LOCATIONS: neck, shoulders, elbows, wrists, waist, hips, knees\n"
            "Default clearance: 0.3mm (FDM). Recommend 0.15mm for resin."
        ),
        "capabilities": ["image_generate", "image_upload", "file_read", "file_write",
                          "model_generate", "resource_access"],
        "security_level": "L2_USER",
        "default_model": "qwen2.5-coder:14b",
    },
    {
        "id": "librarian",
        "name": "Librarian",
        "description": "Deep knowledge, history, literature, philosophy, and factual explanations.",
        "intent": "RESEARCH",
        "system_prompt": (
            "You are the Hive Librarian and Scholar.\n"
            "Your goal is to provide deep historical context, literary analysis, and general knowledge.\n"
            "You are the guardian of facts and culture. Focus on: History, Literature, Philosophy, Science, "
            "and Factual Explanations.\n"
            "If the user asks for code, decline and suggest they ask the Architect.\n"
            "If the user asks for images, decline and suggest they ask the Art Director."
        ),
        "capabilities": ["model_generate", "api_call", "file_read"],
        "security_level": "L1_PUBLIC",
        "default_model": "llama3.2:3b",
    },
    {
        "id": "technical_writer",
        "name": "Technical Writer",
        "description": "Document formatting, rewriting, and technical writing specialist.",
        "intent": "DOCUMENTATION",
        "system_prompt": (
            "You are a Staff-Level Technical Writer.\n"
            "Your goal is to rewrite, format, and organize documentation into professional, polished markdown.\n"
            "If provided with large context files, synthesize the information accurately.\n"
            "Focus on clarity, tone, accurate citations, and structured formatting (headings, lists, bolding)."
        ),
        "capabilities": ["model_generate", "file_read", "api_call"],
        "security_level": "L2_USER",
        "default_model": "qwen3.5:9b",
    },
    {
        "id": "memory_controller",
        "name": "Memory Controller",
        "description": "Learns new rules and corrections for agent behavior.",
        "intent": "TRAIN",
        "system_prompt": None,
        "capabilities": ["db_read", "db_write"],
        "security_level": "L2_USER",
    },
    {
        "id": "iot_controller",
        "name": "IoT Controller",
        "description": "Smart home device control via Home Assistant.",
        "intent": "IOT_CONTROL",
        "system_prompt": None,
        "capabilities": ["api_call", "model_generate"],
        "security_level": "L2_USER",
    },
    {
        "id": "coordinator",
        "name": "Coordinator",
        "description": "Multi-worker orchestration: decompose, research, synthesize, implement, verify.",
        "intent": "COORDINATE",
        "system_prompt": None,
        "capabilities": ["model_generate", "file_read", "file_write", "terminal_exec",
                          "terminal_read", "api_call", "resource_access"],
        "security_level": "L3_ADMIN",
        "default_model": "qwen3:14b",
    },
]


# =============================================================================
# TEMPLATE REGISTRY
# =============================================================================

class TemplateRegistry:
    """
    CRUD layer for expertise templates with in-memory caching.

    Connects to control plane PostgreSQL via TEMPLATE_DB_URL.
    Falls back gracefully if the database is unreachable.
    """

    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self, db_url: Optional[str] = None):
        from config import HOPPER_IP
        self.db_url = db_url or os.getenv(
            "TEMPLATE_DB_URL",
            f"postgresql://langfuse:langfuse@{HOPPER_IP}:5432/langfuse"
        )
        self._pool = None
        self._cache: Dict[str, _CacheEntry] = {}
        self._initialized = False

    def _get_connection(self):
        """Get a database connection. Creates pool on first call."""
        if self._pool is None:
            try:
                import psycopg2
                from psycopg2 import pool
                self._pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=5,
                    dsn=self.db_url,
                )
                logger.info("[TemplateRegistry] Database pool created")
            except Exception as e:
                logger.warning(f"[TemplateRegistry] Cannot connect to DB: {e}")
                return None
        try:
            return self._pool.getconn()
        except Exception as e:
            logger.warning(f"[TemplateRegistry] Connection error: {e}")
            return None

    def _return_connection(self, conn):
        """Return connection to pool."""
        if self._pool and conn:
            try:
                self._pool.putconn(conn)
            except Exception:
                pass

    def _cache_get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        entry = self._cache.get(key)
        if entry and time.time() < entry.expires_at:
            return entry.value
        return None

    def _cache_set(self, key: str, value: Any):
        """Set cache entry with TTL."""
        self._cache[key] = _CacheEntry(
            value=value,
            expires_at=time.time() + self.CACHE_TTL_SECONDS,
        )

    # -------------------------------------------------------------------------
    # INITIALIZATION
    # -------------------------------------------------------------------------

    def initialize(self) -> bool:
        """
        Run schema migration and seed default templates.
        Returns True if successful, False if DB is unavailable.
        """
        conn = self._get_connection()
        if not conn:
            logger.warning("[TemplateRegistry] DB unavailable, skipping initialization")
            return False

        try:
            cur = conn.cursor()

            # Create schema and tables
            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
            if os.path.exists(schema_path):
                with open(schema_path) as f:
                    cur.execute(f.read())
                conn.commit()
                logger.info("[TemplateRegistry] Schema applied")
            else:
                logger.warning(f"[TemplateRegistry] Schema file not found: {schema_path}")

            # Seed default templates
            self._seed_default_templates(cur)
            conn.commit()

            self._initialized = True
            logger.info("[TemplateRegistry] Initialization complete")
            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"[TemplateRegistry] Initialization failed: {e}")
            return False
        finally:
            self._return_connection(conn)

    def _seed_default_templates(self, cursor):
        """Insert default templates if they don't exist."""
        for seed in _SEED_TEMPLATES:
            cursor.execute(
                "SELECT 1 FROM swarm.expertise_templates WHERE id = %s",
                (seed["id"],)
            )
            if cursor.fetchone():
                continue  # Already exists

            cursor.execute(
                """INSERT INTO swarm.expertise_templates
                   (id, name, description, intent, current_version,
                    system_prompt, capabilities, security_level,
                    default_model, config, source)
                   VALUES (%s, %s, %s, %s, '1.0', %s, %s, %s, %s, '{}', 'seed')""",
                (
                    seed["id"],
                    seed["name"],
                    seed.get("description"),
                    seed["intent"],
                    seed.get("system_prompt"),
                    seed["capabilities"],
                    seed.get("security_level", "L2_USER"),
                    seed.get("default_model"),
                ),
            )

            # Create initial version snapshot
            cursor.execute(
                """INSERT INTO swarm.expertise_template_versions
                   (template_id, version, system_prompt, capabilities, config, promoted_at)
                   VALUES (%s, '1.0', %s, %s, '{}', CURRENT_TIMESTAMP)""",
                (
                    seed["id"],
                    seed.get("system_prompt"),
                    seed["capabilities"],
                ),
            )
            logger.info(f"[TemplateRegistry] Seeded template: {seed['id']}")

    # -------------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------------

    def get_template(self, template_id: str) -> Optional[ExpertiseTemplate]:
        """Get template by ID (cached)."""
        cache_key = f"template:{template_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        conn = self._get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, name, description, intent, current_version,
                          system_prompt, capabilities, security_level,
                          default_model, config, source
                   FROM swarm.expertise_templates WHERE id = %s""",
                (template_id,)
            )
            row = cur.fetchone()
            if not row:
                return None

            template = ExpertiseTemplate(
                id=row[0], name=row[1], description=row[2], intent=row[3],
                current_version=row[4], system_prompt=row[5],
                capabilities=row[6] or [], security_level=row[7],
                default_model=row[8], config=row[9] or {}, source=row[10],
            )
            self._cache_set(cache_key, template)
            return template
        except Exception as e:
            logger.error(f"[TemplateRegistry] get_template error: {e}")
            return None
        finally:
            self._return_connection(conn)

    def get_template_version(
        self, template_id: str, version: str = "latest"
    ) -> Optional[TemplateVersion]:
        """Get a specific template version, or the latest."""
        cache_key = f"version:{template_id}:{version}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        conn = self._get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            if version == "latest":
                cur.execute(
                    """SELECT id, template_id, version, system_prompt,
                              capabilities, config, avg_score,
                              total_invocations, successful_invocations,
                              created_at, promoted_at
                       FROM swarm.expertise_template_versions
                       WHERE template_id = %s
                       ORDER BY created_at DESC LIMIT 1""",
                    (template_id,)
                )
            else:
                cur.execute(
                    """SELECT id, template_id, version, system_prompt,
                              capabilities, config, avg_score,
                              total_invocations, successful_invocations,
                              created_at, promoted_at
                       FROM swarm.expertise_template_versions
                       WHERE template_id = %s AND version = %s""",
                    (template_id, version)
                )

            row = cur.fetchone()
            if not row:
                return None

            tv = TemplateVersion(
                id=row[0], template_id=row[1], version=row[2],
                system_prompt=row[3], capabilities=row[4] or [],
                config=row[5] or {}, avg_score=row[6],
                total_invocations=row[7], successful_invocations=row[8],
                created_at=row[9], promoted_at=row[10],
            )
            self._cache_set(cache_key, tv)
            return tv
        except Exception as e:
            logger.error(f"[TemplateRegistry] get_template_version error: {e}")
            return None
        finally:
            self._return_connection(conn)

    def list_templates(self, intent: Optional[str] = None) -> List[ExpertiseTemplate]:
        """List all templates, optionally filtered by intent."""
        conn = self._get_connection()
        if not conn:
            return []

        try:
            cur = conn.cursor()
            if intent:
                cur.execute(
                    """SELECT id, name, description, intent, current_version,
                              system_prompt, capabilities, security_level,
                              default_model, config, source
                       FROM swarm.expertise_templates WHERE intent = %s
                       ORDER BY name""",
                    (intent,)
                )
            else:
                cur.execute(
                    """SELECT id, name, description, intent, current_version,
                              system_prompt, capabilities, security_level,
                              default_model, config, source
                       FROM swarm.expertise_templates ORDER BY name"""
                )

            templates = []
            for row in cur.fetchall():
                templates.append(ExpertiseTemplate(
                    id=row[0], name=row[1], description=row[2], intent=row[3],
                    current_version=row[4], system_prompt=row[5],
                    capabilities=row[6] or [], security_level=row[7],
                    default_model=row[8], config=row[9] or {}, source=row[10],
                ))
            return templates
        except Exception as e:
            logger.error(f"[TemplateRegistry] list_templates error: {e}")
            return []
        finally:
            self._return_connection(conn)

    # -------------------------------------------------------------------------
    # WRITE
    # -------------------------------------------------------------------------

    def record_performance(self, record: PerformanceRecord) -> bool:
        """Record a single invocation's performance metrics."""
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO swarm.performance_history
                   (template_id, template_version, trace_id, session_id,
                    intent, solver_score, verifier_score, final_score,
                    corrector_invoked, iterations, latency_ms)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    record.template_id, record.template_version,
                    record.trace_id, record.session_id, record.intent,
                    record.solver_score, record.verifier_score,
                    record.final_score, record.corrector_invoked,
                    record.iterations, record.latency_ms,
                ),
            )

            # Update version invocation count and running average.
            # Only update avg_score when final_score is explicitly provided —
            # null scores (no feedback yet) must not drag the average to 0.
            if record.final_score is not None:
                cur.execute(
                    """UPDATE swarm.expertise_template_versions
                       SET total_invocations = total_invocations + 1,
                           successful_invocations = successful_invocations +
                               CASE WHEN %s >= 0.7 THEN 1 ELSE 0 END,
                           avg_score = (avg_score * total_invocations + %s)
                                       / (total_invocations + 1)
                       WHERE template_id = %s AND version = %s""",
                    (
                        record.final_score,
                        record.final_score,
                        record.template_id,
                        record.template_version,
                    ),
                )
            else:
                # Unscored invocation — increment counter only, leave avg_score unchanged
                cur.execute(
                    """UPDATE swarm.expertise_template_versions
                       SET total_invocations = total_invocations + 1
                       WHERE template_id = %s AND version = %s""",
                    (record.template_id, record.template_version),
                )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"[TemplateRegistry] record_performance error: {e}")
            return False
        finally:
            self._return_connection(conn)

    def get_performance_summary(
        self, template_id: str, window_hours: int = 24
    ) -> Optional[PerformanceSummary]:
        """Get aggregated performance metrics over a time window."""
        conn = self._get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT template_version,
                          AVG(final_score),
                          COUNT(*),
                          COUNT(*) FILTER (WHERE final_score >= 0.7),
                          AVG(latency_ms),
                          STDDEV(final_score)
                   FROM swarm.performance_history
                   WHERE template_id = %s
                     AND recorded_at > CURRENT_TIMESTAMP - INTERVAL '%s hours'
                   GROUP BY template_version
                   ORDER BY COUNT(*) DESC
                   LIMIT 1""",
                (template_id, window_hours),
            )
            row = cur.fetchone()
            if not row:
                return None

            return PerformanceSummary(
                template_id=template_id,
                template_version=row[0] or "1.0",
                avg_score=row[1] or 0.0,
                total_invocations=row[2] or 0,
                successful_invocations=row[3] or 0,
                avg_latency_ms=row[4],
                score_stddev=row[5],
            )
        except Exception as e:
            logger.error(f"[TemplateRegistry] get_performance_summary error: {e}")
            return None
        finally:
            self._return_connection(conn)

    def bump_version(
        self, template_id: str, changes: Optional[Dict[str, Any]] = None
    ) -> Optional[TemplateVersion]:
        """
        Create a new version of a template.

        Args:
            template_id: Template to version
            changes: Dict of fields to update (system_prompt, capabilities, config)

        Returns:
            New TemplateVersion or None on failure
        """
        conn = self._get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()

            # Get current template
            cur.execute(
                """SELECT current_version, system_prompt, capabilities, config
                   FROM swarm.expertise_templates WHERE id = %s""",
                (template_id,)
            )
            row = cur.fetchone()
            if not row:
                logger.error(f"[TemplateRegistry] Template {template_id} not found")
                return None

            current_version = row[0]
            system_prompt = row[1]
            capabilities = row[2]
            config = row[3] or {}

            # Compute next version (simple minor bump: 1.0 -> 1.1 -> 1.2)
            parts = current_version.split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            new_version = f"{major}.{minor + 1}"

            # Apply changes
            if changes:
                system_prompt = changes.get("system_prompt", system_prompt)
                capabilities = changes.get("capabilities", capabilities)
                config = changes.get("config", config)

            # Create new version
            cur.execute(
                """INSERT INTO swarm.expertise_template_versions
                   (template_id, version, system_prompt, capabilities, config, promoted_at)
                   VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                   RETURNING id, created_at""",
                (template_id, new_version, system_prompt, capabilities,
                 __import__("json").dumps(config)),
            )
            result = cur.fetchone()

            # Update master template
            cur.execute(
                """UPDATE swarm.expertise_templates
                   SET current_version = %s, updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                (new_version, template_id),
            )
            conn.commit()

            # Invalidate cache
            self._cache.pop(f"template:{template_id}", None)
            self._cache.pop(f"version:{template_id}:latest", None)

            tv = TemplateVersion(
                id=result[0], template_id=template_id, version=new_version,
                system_prompt=system_prompt, capabilities=capabilities or [],
                config=config, created_at=result[1],
                promoted_at=result[1],
            )
            logger.info(f"[TemplateRegistry] Bumped {template_id} to v{new_version}")
            return tv

        except Exception as e:
            conn.rollback()
            logger.error(f"[TemplateRegistry] bump_version error: {e}")
            return None
        finally:
            self._return_connection(conn)

    def prune_old_records(self, days: int = 30) -> int:
        """Delete performance history older than N days. Returns count deleted."""
        conn = self._get_connection()
        if not conn:
            return 0

        try:
            cur = conn.cursor()
            cur.execute(
                """DELETE FROM swarm.performance_history
                   WHERE recorded_at < CURRENT_TIMESTAMP - INTERVAL '%s days'""",
                (days,)
            )
            count = cur.rowcount
            conn.commit()
            if count > 0:
                logger.info(f"[TemplateRegistry] Pruned {count} old performance records")
            return count
        except Exception as e:
            conn.rollback()
            logger.error(f"[TemplateRegistry] prune_old_records error: {e}")
            return 0
        finally:
            self._return_connection(conn)


# =============================================================================
# SINGLETON
# =============================================================================

_registry_instance: Optional[TemplateRegistry] = None


def get_template_registry() -> TemplateRegistry:
    """Get or create the global TemplateRegistry singleton."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = TemplateRegistry()
    return _registry_instance
